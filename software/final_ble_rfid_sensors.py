"""
final_ble_rfid_sensors.py — Production System: Indoor BLE Tracking
===================================================================
Integrates BLE trilateration, RFID zone detection, environmental
sensing (DHT11 + MQ-135 via Arduino), and OLED display output on
a Raspberry Pi 3B+.

Architecture:
  - Main async loop   : BLE scanning + trilateration + OLED update
  - Background thread : RFID polling (non-blocking)
  - Serial reader     : Arduino sensor data via UART

Usage:
  python software/final_ble_rfid_sensors.py

Project: Indoor BLE Tracking for Poultry Farm
Paper:   IRJASM Vol 01, Issue 01, November 2023
Authors: Arsath Maideen F, Mohammed Afsar MH, Muhammed Faarooq,
         Badhrinath S, Dr. Indra Gandhi K
"""

import asyncio
import logging
import csv
import sys
import time
import threading
from collections import deque
from datetime import datetime

import board
import busio
import RPi.GPIO as GPIO
import serial
from adafruit_ssd1306 import SSD1306_I2C
from bleak import BleakScanner
from mfrc522 import SimpleMFRC522
from PIL import Image, ImageDraw, ImageFont

# Add project root to path so config is importable
sys.path.append("..")
from config.config import (
    BEACONS, RFID_ZONES, RFID_DEFAULT_ZONE,
    BLE_SCAN_TIMEOUT, BLE_SCAN_INTERVAL, RSSI_HISTORY_SIZE, MIN_BEACONS_NEEDED,
    SERIAL_PORT, SERIAL_BAUD, SERIAL_TIMEOUT,
    OLED_WIDTH, OLED_HEIGHT,
    LOG_FILE, LOG_HEADERS,
)

# ─────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("system.log"),
    ]
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# GLOBAL SHARED STATE (thread-safe primitives)
# ─────────────────────────────────────────────
current_zone: str = RFID_DEFAULT_ZONE
rssi_history: dict = {uuid: deque(maxlen=RSSI_HISTORY_SIZE) for uuid in BEACONS}
state_lock = threading.Lock()


# ─────────────────────────────────────────────
# OLED DISPLAY INIT
# ─────────────────────────────────────────────
def init_oled() -> SSD1306_I2C:
    """Initialise the SSD1306 OLED over I2C and return the display object."""
    i2c = busio.I2C(board.SCL, board.SDA)
    disp = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c)
    disp.fill(0)
    disp.show()
    return disp


# ─────────────────────────────────────────────
# DISTANCE ESTIMATION
# ─────────────────────────────────────────────
def rssi_to_distance(rssi: float, rssi_at_1m: float, n: float) -> float:
    """
    Convert RSSI to estimated distance using the log-distance path loss model.

    Formula:  d = 10 ^ ((RSSI_at_1m - RSSI) / (10 * n))

    Args:
        rssi:       Measured RSSI value in dBm.
        rssi_at_1m: Calibrated RSSI at 1 metre (dBm), beacon-specific.
        n:          Path loss exponent (environment-dependent, typically 2.0–4.0).

    Returns:
        Estimated distance in metres.
    """
    return 10 ** ((rssi_at_1m - rssi) / (10 * n))


def get_smoothed_rssi(uuid: str, raw_rssi: int) -> float:
    """
    Add a new RSSI sample to the rolling history and return the average.

    Using a rolling average over RSSI_HISTORY_SIZE samples significantly
    reduces noise caused by multipath fading and environmental interference.

    Args:
        uuid:     Beacon UUID string.
        raw_rssi: Latest RSSI reading in dBm.

    Returns:
        Smoothed (averaged) RSSI value.
    """
    rssi_history[uuid].append(raw_rssi)
    return sum(rssi_history[uuid]) / len(rssi_history[uuid])


# ─────────────────────────────────────────────
# TRILATERATION
# ─────────────────────────────────────────────
def trilaterate(
    p1: tuple, d1: float,
    p2: tuple, d2: float,
    p3: tuple, d3: float
) -> tuple | None:
    """
    Compute 2D position using closed-form trilateration from 3 beacon distances.

    Solves the linear system derived from subtracting circle equations:
      (x - xi)^2 + (y - yi)^2 = di^2

    Args:
        p1, p2, p3: (x, y) positions of the three beacons in metres.
        d1, d2, d3: Estimated distances from each beacon in metres.

    Returns:
        (x, y) estimated position, or None if geometry is degenerate
        (collinear beacons or division-by-zero condition).
    """
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3

    A = 2 * x2 - 2 * x1
    B = 2 * y2 - 2 * y1
    C = 2 * x3 - 2 * x1
    D = 2 * y3 - 2 * y1

    E = (d1**2 - d2**2) + (x2**2 - x1**2) + (y2**2 - y1**2)
    F = (d1**2 - d3**2) + (x3**2 - x1**2) + (y3**2 - y1**2)

    denom = A * D - B * C
    if abs(denom) < 1e-9:
        log.warning("Trilateration failed: beacons are collinear (denom ≈ 0).")
        return None

    if abs(B) < 1e-9:
        log.warning("Trilateration failed: B ≈ 0, cannot solve for y.")
        return None

    x = (E * D - F * B) / denom
    y = (E - A * x) / B
    return (x, y)


# ─────────────────────────────────────────────
# BLE SCANNING + POSITION ESTIMATION
# ─────────────────────────────────────────────
async def estimate_position() -> tuple | None:
    """
    Scan for BLE beacons, smooth RSSI readings, and estimate 2D position.

    Steps:
      1. Discover nearby BLE devices via BleakScanner.
      2. Match detected UUIDs against BEACONS config.
      3. Apply rolling RSSI average per beacon.
      4. Select the 3 strongest (highest RSSI) beacon signals.
      5. Convert smoothed RSSI → distance for each beacon.
      6. Run trilateration to get (x, y).

    Returns:
        (x, y) estimated position in metres, or None if insufficient beacons.
    """
    log.info("Scanning for BLE beacons...")
    try:
        devices = await BleakScanner.discover(timeout=BLE_SCAN_TIMEOUT)
    except Exception as exc:
        log.error(f"BLE scan failed: {exc}")
        return None

    detected: dict = {}
    for device in devices:
        uuids = device.metadata.get("uuids", [])
        for uuid in uuids:
            if uuid in BEACONS:
                smoothed = get_smoothed_rssi(uuid, device.rssi)
                detected[uuid] = smoothed
                log.info(
                    f"  {BEACONS[uuid]['label']}: raw={device.rssi} dBm, "
                    f"smoothed={smoothed:.1f} dBm"
                )

    if len(detected) < MIN_BEACONS_NEEDED:
        log.warning(f"Only {len(detected)} beacon(s) detected — need {MIN_BEACONS_NEEDED}.")
        return None

    # Pick 3 strongest signals (highest RSSI = closest)
    top3 = sorted(detected.items(), key=lambda kv: kv[1], reverse=True)[:3]

    points, distances = [], []
    for uuid, rssi in top3:
        beacon   = BEACONS[uuid]
        distance = rssi_to_distance(rssi, beacon["rssi_at_1m"], beacon["n"])
        points.append(beacon["position"])
        distances.append(distance)
        log.info(f"  {beacon['label']}: distance={distance:.2f} m")

    return trilaterate(
        points[0], distances[0],
        points[1], distances[1],
        points[2], distances[2],
    )


# ─────────────────────────────────────────────
# RFID ZONE DETECTION (background thread)
# ─────────────────────────────────────────────
def rfid_polling() -> None:
    """
    Continuously poll the MFRC522 RFID reader in a background daemon thread.

    Updates the global `current_zone` variable when a known tag is detected.
    Uses specific exception handling to surface hardware failures clearly
    rather than silently swallowing errors.
    """
    global current_zone
    reader = SimpleMFRC522()
    log.info("RFID polling thread started.")

    while True:
        try:
            uid, text = reader.read()
            uid_str = str(uid).strip()
            with state_lock:
                current_zone = RFID_ZONES.get(uid_str, f"Unknown Tag ({uid_str})")
            log.info(f"[RFID] Tag detected: {current_zone}")
            time.sleep(1.0)

        except IOError as exc:
            log.error(f"[RFID] I/O error (check wiring): {exc}")
            time.sleep(2.0)
        except RuntimeError as exc:
            log.error(f"[RFID] Runtime error: {exc}")
            time.sleep(2.0)


# ─────────────────────────────────────────────
# ARDUINO SERIAL SENSOR READER
# ─────────────────────────────────────────────
def read_sensor_data(ser: serial.Serial) -> dict:
    """
    Read a line from Arduino over UART and parse temperature, humidity, AQI.

    Expected Arduino serial format:
        TEMP:27.5,HUM:65.0,AQI:120,STATUS:Moderate

    Args:
        ser: Open pyserial Serial object.

    Returns:
        Dict with keys: temp_c, humidity_pct, aqi_raw, aqi_status.
        Returns defaults (None values) if parsing fails.
    """
    defaults = {"temp_c": None, "humidity_pct": None, "aqi_raw": None, "aqi_status": "N/A"}
    try:
        line = ser.readline().decode("utf-8").strip()
        if not line:
            return defaults
        parts = dict(item.split(":") for item in line.split(","))
        return {
            "temp_c":       float(parts.get("TEMP", 0)),
            "humidity_pct": float(parts.get("HUM", 0)),
            "aqi_raw":      int(parts.get("AQI", 0)),
            "aqi_status":   parts.get("STATUS", "N/A"),
        }
    except (ValueError, KeyError, UnicodeDecodeError) as exc:
        log.warning(f"[Serial] Failed to parse sensor data: {exc}")
        return defaults


# ─────────────────────────────────────────────
# OLED DISPLAY UPDATE
# ─────────────────────────────────────────────
def update_oled(
    disp: SSD1306_I2C,
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    zone: str,
    position: tuple | None,
    sensor: dict,
) -> None:
    """
    Render current position, zone, and sensor data onto the OLED display.

    Layout (128×64):
      Line 0 (y=0):  Zone label
      Line 1 (y=16): Position (x, y) or 'Pos: Unknown'
      Line 2 (y=32): Temp + Humidity
      Line 3 (y=48): AQI status + timestamp

    Args:
        disp:     SSD1306 display object.
        image:    PIL Image for drawing.
        draw:     PIL ImageDraw context.
        font:     PIL ImageFont to use.
        zone:     Current RFID zone label.
        position: (x, y) tuple or None.
        sensor:   Dict from read_sensor_data().
    """
    draw.rectangle((0, 0, OLED_WIDTH, OLED_HEIGHT), outline=0, fill=0)
    draw.text((0,  0), f"Zone: {zone[:16]}", font=font, fill=255)

    if position:
        x, y = position
        draw.text((0, 16), f"Pos: ({x:.2f}, {y:.2f})", font=font, fill=255)
    else:
        draw.text((0, 16), "Pos: Scanning...", font=font, fill=255)

    temp = f"{sensor['temp_c']:.1f}C" if sensor["temp_c"] is not None else "N/A"
    hum  = f"{sensor['humidity_pct']:.0f}%" if sensor["humidity_pct"] is not None else "N/A"
    draw.text((0, 32), f"T:{temp} H:{hum}", font=font, fill=255)
    draw.text((0, 48), f"AQI:{sensor['aqi_status']} {time.strftime('%H:%M:%S')}", font=font, fill=255)

    disp.image(image)
    disp.show()


# ─────────────────────────────────────────────
# CSV LOGGER
# ─────────────────────────────────────────────
def log_to_csv(position: tuple | None, zone: str, sensor: dict) -> None:
    """
    Append one row of fused data to the CSV log file.

    Args:
        position: (x, y) or None.
        zone:     RFID zone label.
        sensor:   Dict from read_sensor_data().
    """
    x, y = (f"{position[0]:.3f}", f"{position[1]:.3f}") if position else ("", "")
    row = [
        datetime.now().isoformat(),
        x, y, zone,
        sensor.get("temp_c", ""),
        sensor.get("humidity_pct", ""),
        sensor.get("aqi_raw", ""),
        sensor.get("aqi_status", ""),
    ]
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(row)


# ─────────────────────────────────────────────
# MAIN ASYNC LOOP
# ─────────────────────────────────────────────
async def main() -> None:
    """
    Main entry point. Initialises all hardware, starts RFID thread,
    then runs the main scan-fuse-display loop indefinitely.
    """
    # Initialise CSV log
    with open(LOG_FILE, "w", newline="") as f:
        csv.writer(f).writerow(LOG_HEADERS)

    # Initialise OLED
    disp  = init_oled()
    image = Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
    draw  = ImageDraw.Draw(image)
    font  = ImageFont.load_default()

    # Initialise serial connection to Arduino
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=SERIAL_TIMEOUT)
        log.info(f"Serial connected: {SERIAL_PORT} @ {SERIAL_BAUD} baud")
    except serial.SerialException as exc:
        log.error(f"Could not open serial port {SERIAL_PORT}: {exc}")
        ser = None

    # Start RFID background thread
    rfid_thread = threading.Thread(target=rfid_polling, daemon=True)
    rfid_thread.start()

    log.info("System started. Running main loop...")

    try:
        while True:
            # 1. Estimate BLE position
            position = await estimate_position()

            # 2. Read sensor data from Arduino
            sensor = read_sensor_data(ser) if ser else {
                "temp_c": None, "humidity_pct": None,
                "aqi_raw": None, "aqi_status": "No Serial"
            }

            # 3. Get current RFID zone (thread-safe read)
            with state_lock:
                zone = current_zone

            # 4. Log to terminal
            pos_str = f"({position[0]:.2f}, {position[1]:.2f})" if position else "Unknown"
            log.info(
                f"Position={pos_str} | Zone={zone} | "
                f"Temp={sensor['temp_c']}°C | Hum={sensor['humidity_pct']}% | "
                f"AQI={sensor['aqi_status']}"
            )

            # 5. Update OLED
            update_oled(disp, image, draw, font, zone, position, sensor)

            # 6. Log to CSV
            log_to_csv(position, zone, sensor)

            # 7. Wait before next scan (non-blocking — won't freeze event loop)
            await asyncio.sleep(BLE_SCAN_INTERVAL)

    except KeyboardInterrupt:
        log.info("Shutdown requested by user.")
    finally:
        GPIO.cleanup()
        disp.fill(0)
        disp.show()
        if ser and ser.is_open:
            ser.close()
        log.info("Cleanup complete. Goodbye.")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(main())

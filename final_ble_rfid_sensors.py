import asyncio
from bleak import BleakScanner
from mfrc522 import SimpleMFRC522
from PIL import Image, ImageDraw, ImageFont
import RPi.GPIO as GPIO
import time
import math
import threading

# OLED display imports (I2C)
import board
import busio
from adafruit_ssd1306 import SSD1306_I2C

# OLED display setup over I2C
i2c = busio.I2C(board.SCL, board.SDA)
disp = SSD1306_I2C(128, 64, i2c)
disp.fill(0)
disp.show()

width, height = disp.width, disp.height
image = Image.new("1", (width, height))
draw = ImageDraw.Draw(image)
font = ImageFont.load_default()

# BLE beacon UUIDs and associated data
beacons = {
    "de662a08-6b61-4bc7-b54e-d3920384c8f1": {  # Beacon 1
        "position": (0, 0),
        "rssi_at_1m": -58,
        "n": 2.0
    },
    "e1c27af2-b59e-4863-9471-4718b1295922": {  # Beacon 2
        "position": (5, 0),
        "rssi_at_1m": -62,
        "n": 2.2
    },
    "7721401b-f541-4a02-a016-de0a5cc18c4e": {  # Beacon 3
        "position": (2.5, 4.3),
        "rssi_at_1m": -60,
        "n": 1.9
    }
}

reader = SimpleMFRC522()
last_zone = "No Tag"

# Function to read RFID tags continuously
def rfid_polling():
    global last_zone
    while True:
        try:
            id, text = reader.read()
            if text:
                last_zone = text.strip()
                print(f"[RFID] New Tag: {last_zone}")
            time.sleep(1)  # Slight delay to avoid constant scanning
        except Exception as e:
            print(f"[RFID] Error: {e}")
            time.sleep(1)

def rssi_to_distance(rssi, rssi_at_1m, n):
    return 10 ** ((rssi_at_1m - rssi) / (10 * n))

def trilaterate(p1, d1, p2, d2, p3, d3):
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    
    A = 2*x2 - 2*x1
    B = 2*y2 - 2*y1
    C = 2*x3 - 2*x1
    D = 2*y3 - 2*y1

    E = (d1**2 - d2**2) + (x2**2 - x1**2) + (y2**2 - y1**2)
    F = (d1**2 - d3**2) + (x3**2 - x1**2) + (y3**2 - y1**2)

    x = (E - F) / (A*D - B*C)
    y = (E - A*x) / B

    return x, y

async def estimate_position():
    devices = await BleakScanner.discover(timeout=3.0)
    rssi_data = {}

    for d in devices:
        uuids = d.metadata.get("uuids", [])
        for uuid in uuids:
            if uuid in beacons:
                rssi_data[uuid] = d.rssi

    if len(rssi_data) < 3:
        return None

    selected = list(rssi_data.items())[:3]
    points = []
    distances = []

    for uuid, rssi in selected:
        beacon_info = beacons[uuid]
        pos = beacon_info["position"]
        rssi_at_1m = beacon_info["rssi_at_1m"]
        n = beacon_info["n"]
        distance = rssi_to_distance(rssi, rssi_at_1m, n)

        points.append(pos)
        distances.append(distance)

    return trilaterate(points[0], distances[0], points[1], distances[1], points[2], distances[2])

def update_oled(rfid_zone, position):
    draw.rectangle((0, 0, width, height), outline=0, fill=0)
    draw.text((0, 0), f"RFID: {rfid_zone}", font=font, fill=255)
    if position:
        x, y = position
        draw.text((0, 20), f"Pos: ({x:.2f}, {y:.2f})", font=font, fill=255)
    else:
        draw.text((0, 20), "Pos: Unknown", font=font, fill=255)
    draw.text((0, 40), time.strftime("%H:%M:%S"), font=font, fill=255)
    disp.image(image)
    disp.show()

async def main():
    # Start RFID polling in background
    rfid_thread = threading.Thread(target=rfid_polling, daemon=True)
    rfid_thread.start()

    try:
        while True:
            print("Scanning for beacons and tags...")
            position = await estimate_position()
            print(f"Estimated Position: {position}")

            update_oled(last_zone, position)
            time.sleep(2)

    finally:
        GPIO.cleanup()
        disp.fill(0)
        disp.show()

if __name__ == "__main__":
    asyncio.run(main())

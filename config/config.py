"""
config.py — Central configuration for Indoor BLE Tracking System
=================================================================
All hardware constants, beacon parameters, zone definitions, and
system settings are defined here. Edit this file to match your
physical deployment before running the system.

Project: Indoor BLE Tracking for Poultry Farm
Paper:   IRJASM Vol 01, Issue 01, November 2023
"""

# ─────────────────────────────────────────────
# BLE BEACON CONFIGURATION
# Each beacon has:
#   position   : (x, y) in metres from origin
#   rssi_at_1m : calibrated RSSI at 1 metre distance (dBm)
#   n          : path loss exponent (env-dependent, 2.0–4.0)
#   label      : human-readable name for logging
# ─────────────────────────────────────────────
BEACONS = {
    "de662a08-6b61-4bc7-b54e-d3920384c8f1": {
        "position":   (0.0, 0.0),
        "rssi_at_1m": -58,
        "n":          2.0,
        "label":      "Beacon-1 (Origin)"
    },
    "e1c27af2-b59e-4863-9471-4718b1295922": {
        "position":   (5.0, 0.0),
        "rssi_at_1m": -62,
        "n":          2.2,
        "label":      "Beacon-2 (Right)"
    },
    "7721401b-f541-4a02-a016-de0a5cc18c4e": {
        "position":   (2.5, 4.3),
        "rssi_at_1m": -60,
        "n":          1.9,
        "label":      "Beacon-3 (Top)"
    },
}

# ─────────────────────────────────────────────
# RFID ZONE MAPPING
# Maps RFID tag UID (as string) → zone label
# Add your actual tag UIDs after deployment
# ─────────────────────────────────────────────
RFID_ZONES = {
    "TAG_UID_ZONE_A": "Zone-A (Entry)",
    "TAG_UID_ZONE_B": "Zone-B (Feed Area)",
    "TAG_UID_ZONE_C": "Zone-C (Water Area)",
    "TAG_UID_ZONE_D": "Zone-D (Exit)",
}
RFID_DEFAULT_ZONE = "Unknown Zone"

# ─────────────────────────────────────────────
# BLE SCANNING PARAMETERS
# ─────────────────────────────────────────────
BLE_SCAN_TIMEOUT    = 3.0   # seconds — BleakScanner.discover() timeout
BLE_SCAN_INTERVAL   = 2.0   # seconds — how often to re-scan
RSSI_HISTORY_SIZE   = 10    # rolling average window (samples per beacon)
MIN_BEACONS_NEEDED  = 3     # minimum beacons required for trilateration

# ─────────────────────────────────────────────
# SERIAL / ARDUINO PARAMETERS
# ─────────────────────────────────────────────
SERIAL_PORT         = "/dev/ttyUSB0"   # change to /dev/ttyACM0 if needed
SERIAL_BAUD         = 9600
SERIAL_TIMEOUT      = 2.0              # seconds

# ─────────────────────────────────────────────
# OLED DISPLAY PARAMETERS
# ─────────────────────────────────────────────
OLED_WIDTH          = 128
OLED_HEIGHT         = 64
OLED_I2C_ADDRESS    = 0x3C

# ─────────────────────────────────────────────
# ENVIRONMENTAL SENSOR THRESHOLDS
# ─────────────────────────────────────────────
AQI_THRESHOLDS = {
    "Good":     (0,   100),
    "Moderate": (101, 200),
    "Poor":     (201, 999),
}
TEMP_ALERT_HIGH     = 35.0   # °C — alert threshold for temperature
HUMIDITY_ALERT_HIGH = 80.0   # %  — alert threshold for humidity

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
LOG_FILE            = "tracking_log.csv"
LOG_HEADERS         = ["timestamp", "x", "y", "zone", "temp_c",
                        "humidity_pct", "aqi_raw", "aqi_status"]

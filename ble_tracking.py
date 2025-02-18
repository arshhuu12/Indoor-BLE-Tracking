import asyncio
from bleak import BleakScanner
import numpy as np
import matplotlib.pyplot as plt

#  List of fixed beacon UUIDs (or MAC addresses)
FIXED_BEACONS = {
    "12345678-1234-5678-1234-567812345678": {"position": (0, 0), "tx_power": -59},
    "87654321-4321-8765-4321-876543218765": {"position": (5, 0), "tx_power": -59},
    "11223344-5566-7788-99AA-BBCCDDEEFF00": {"position": (2.5, 5), "tx_power": -59}
}

#  Convert RSSI to Distance
def rssi_to_distance(rssi, tx_power):
    return 10 ** ((tx_power - rssi) / (10 * 2))  # Path loss exponent = 2

#  Trilateration Algorithm
def trilateration(beacon_data):
    if len(beacon_data) < 3:
        print("⚠️ Need at least 3 beacons for trilateration!")
        return None
    
    A = []
    B = []
    beacons = list(beacon_data.items())

    for i in range(len(beacons) - 1):
        x1, y1 = beacons[i][1]['position']
        x2, y2 = beacons[i + 1][1]['position']
        d1 = beacons[i][1]['distance']
        d2 = beacons[i + 1][1]['distance']

        A.append([2 * (x2 - x1), 2 * (y2 - y1)])
        B.append(d1 ** 2 - d2 ** 2 - x1 ** 2 + x2 ** 2 - y1 ** 2 + y2 ** 2)

    A = np.array(A)
    B = np.array(B)

    try:
        position = np.linalg.lstsq(A, B, rcond=None)[0]
        return position
    except:
        return None

#  Scan for BLE Beacons
async def scan():
    print(" Scanning for BLE beacons...")

    devices = await BleakScanner.discover()
    beacon_data = {}

    for device in devices:
        if device.metadata and "uuids" in device.metadata:
            for uuid in device.metadata["uuids"]:
                if uuid in FIXED_BEACONS:
                    rssi = device.rssi
                    tx_power = FIXED_BEACONS[uuid]["tx_power"]
                    distance = rssi_to_distance(rssi, tx_power)

                    beacon_data[uuid] = {
                        "position": FIXED_BEACONS[uuid]["position"],
                        "distance": distance
                    }

                    print(f"📡 Detected {uuid}: RSSI={rssi}, Distance={distance:.2f}m")

    estimated_position = trilateration(beacon_data)
    
    if estimated_position is not None:
        print(f"📍 Estimated Position: X={estimated_position[0]:.2f}, Y={estimated_position[1]:.2f}")

#  Run the scan function in a loop
async def main():
    while True:
        await scan()
        await asyncio.sleep(2)  # Update every 2 seconds

#  Run the script
asyncio.run(main())

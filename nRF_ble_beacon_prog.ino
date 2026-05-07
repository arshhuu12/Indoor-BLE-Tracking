#include <BLEPeripheral.h>

/*
 * Final Year Project - BLE Beacon Sketch (nRF51822)
 * Author: [Your Name]
 * Date: [Today's Date]
 * 
 * Instructions:
 * - Use this code on all 3 beacons.
 * - Only change the UUID and beacon name.
 * - TX power and Advertising interval are shared across all.
 */

// ========== CUSTOMIZATION SECTION ==========
const char* beaconName = "BLE-Beacon-3";
const char* beaconUUID = "B5839C6E-5B64-44E6-9817-F0173DA5C542";

// Advanced Configuration
const uint16_t advInterval = 160;  // 160 = 100ms (Range: 20ms–10.24s; 1 unit = 0.625ms)
const int txPower = 0;             // Options: 4, 0, -4, -8, -12, -16, -20, -30 (dBm)

// ========== END CUSTOMIZATION ==========

// BLE Peripheral Object
BLEPeripheral blePeripheral = BLEPeripheral();

void setup() {
  // Set advertised service UUID and local name
  blePeripheral.setLocalName(beaconName);
  blePeripheral.setAdvertisedServiceUuid(beaconUUID);

  // Advanced BLE settings
  blePeripheral.setAdvertisingInterval(advInterval);
  blePeripheral.setTxPower(txPower);

  // Start Advertising
  blePeripheral.begin();
}

void loop() {
  blePeripheral.poll();
}

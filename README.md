#  Indoor BLE Tracking System

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)
![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi-red?logo=raspberry-pi)
![Protocol](https://img.shields.io/badge/Protocol-BLE%20%7C%20RFID-green)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

> Real-time indoor positioning and environmental monitoring for poultry farms using BLE trilateration, RFID zone detection, and IoT sensors — all fused on a Raspberry Pi.

---

##  Hardware Setup

<!-- ADD YOUR HARDWARE PHOTO HERE -->
<!-- Drag and drop your photo of the RPi + OLED + breadboard setup -->
<!-- Recommended: Use Figure 3 from the published paper -->

![Hardware Setup](results/hardware_setup.jpg)
*Raspberry Pi 3B+ with MFRC522 RFID reader, SSD1306 OLED, DHT11, MQ-135, and Arduino Uno on a breadboard in the 2×2m testbed*

---

##  System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     POULTRY FARM ENVIRONMENT                │
│                                                             │
│  [nRF51822 Beacon 1]  [nRF51822 Beacon 2]  [nRF51822 Beacon 3]
│       (0, 0)               (5, 0)             (2.5, 4.3)   │
│          │                    │                    │        │
│          └──────── BLE RSSI ──┴──────── BLE RSSI ─┘        │
│                               │                            │
│  [RFID Tags @ Zone A/B/C/D]   │                            │
│          │                    ▼                            │
│          │         ┌─────────────────┐                     │
│          └─RC522──►│  Raspberry Pi   │◄── UART ──[Arduino] │
│                    │     3B+         │         │           │
│                    │  ┌───────────┐  │    [DHT11][MQ-135]  │
│                    │  │Trilaterate│  │                     │
│                    │  │RFID Fuse  │  │                     │
│                    │  │Env. Parse │  │                     │
│                    │  └───────────┘  │                     │
│                    └────────┬────────┘                     │
│                             │                              │
│                   ┌─────────┴──────────┐                   │
│                   ▼                    ▼                   │
│            [OLED Display]         [CSV Logger]             │
│         Live position + env     Timestamped data           │
└─────────────────────────────────────────────────────────────┘
```

---

##  Key Results

| Method | Avg Localization Error |
|--------|----------------------|
| Single BLE Beacon | 0.81 m |
| **Zone-based Trilateration (ours)** | **0.55 m** |

**Zone-wise Accuracy (12 test points across 4 zones):**

| Zone | Mean Error | Notes |
|------|-----------|-------|
| Z1 | ~16% | Moderate interference |
| Z2 | ~30% | Near edge, signal variance |
| Z3 | ~53% | Edge case — poor beacon geometry (GDOP effect) |
| Z4 | ~25% | Best line-of-sight |

> Zone-based calibration reduced average error by **32%** compared to single-beacon estimation.

---

##  Hardware Requirements

| Component | Model | Quantity |
|-----------|-------|----------|
| Single Board Computer | Raspberry Pi 3B+ | 1 |
| BLE Beacon | nRF51822 | 3 |
| RFID Reader | MFRC522 (13.56 MHz) | 1 |
| RFID Tags | Passive ISO 14443A | 4+ |
| Microcontroller | Arduino Uno (ATmega328P) | 1 |
| Temp/Humidity Sensor | DHT11 | 1 |
| Gas Sensor | MQ-135 | 1 |
| OLED Display | SSD1306 128×64 I2C | 1 |
| Power Supply | 5V regulated | 1 |

---

##  Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/arshhuu12/Indoor-BLE-Tracking.git
cd Indoor-BLE-Tracking
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Beacon Parameters

Edit `config/config.py` to match your physical beacon placement:

```python
BEACONS = {
    "your-beacon-uuid-1": {
        "position": (0, 0),
        "rssi_at_1m": -58,
        "n": 2.0,
        "label": "Beacon 1"
    },
    # ... add your beacon UUIDs
}
```

### 4. Flash Arduino Firmware

Open `hardware/environ_monitor.ino` in Arduino IDE and upload to your Arduino Uno. Ensure baud rate matches `config.py` (`SERIAL_BAUD = 9600`).

### 5. Flash BLE Beacon Firmware

Open `hardware/nRF_ble_beacon_prog.ino` in Arduino IDE with nRF51822 board support installed. Flash to each beacon and update their UUIDs in `config.py`.

### 6. Run the Full System

```bash
python software/final_ble_rfid_sensors.py
```

---

##  Project Structure

```
Indoor-BLE-Tracking/
├── README.md                          # You are here
├── requirements.txt                   # Python dependencies
├── .gitignore                         # Ignore build artifacts
│
├── config/
│   └── config.py                      # All constants: UUIDs, positions, thresholds
│
├── software/
│   ├── base_ble.py                    # Prototype v1 — basic BLE scan
│   ├── ble_tracking.py                # Prototype v2 — trilateration added
│   └── final_ble_rfid_sensors.py      # Production system — full integration
│
├── hardware/
│   ├── nRF_ble_beacon_prog.ino        # nRF51822 beacon firmware (Arduino IDE)
│   └── environ_monitor.ino            # Arduino sensor reader + UART transmitter
│
├── results/
│   ├── results_project_ble.pdf        # Experimental results report
│   └── hardware_setup.jpg             # Hardware photo (add yours here)
│
└── docs/
    └── paper.pdf                      # Published conference paper
```

---

##  Tech Stack

**Embedded / Hardware**
- nRF51822 BLE SoC — beacon advertisement broadcasting
- Arduino Uno (ATmega328P) — sensor ADC + UART bridge
- Raspberry Pi 3B+ (Raspbian OS) — central processing unit

**Python Libraries**
- `bleak` — async BLE scanning
- `numpy` — trilateration least-squares solver
- `mfrc522` — RFID reader interface
- `RPi.GPIO` — GPIO control
- `pyserial` — Arduino UART communication
- `adafruit-circuitpython-ssd1306` — OLED display driver
- `Pillow` — OLED image rendering

**Algorithms**
- Log-distance path loss model (RSSI → distance)
- 2D closed-form trilateration
- Zone-based calibration for interference mitigation
- Rolling RSSI average (noise reduction)

---

##  Future Work

- **ML Integration** — k-NN or neural network for RSSI fingerprinting to replace trilateration
- **Kalman Filter** — smooth noisy RSSI readings for better real-time tracking
- **Scalability** — extend to larger sheds with dynamic beacon mesh
- **Battery Optimization** — duty-cycle BLE scanning for low-power deployment
- **Dashboard** — web UI (Flask/Grafana) for remote farm monitoring

---

##  Authors

- **Arsath Maideen F** — UG, Dept. of ECE

##  License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

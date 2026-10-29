# ANIMA-S3 User Guide

Welcome to the **ANIMA-S3 Voice Assistant System**. ANIMA-S3 is a low-latency, half-duplex voice assistant architecture combining an ESP32-S3 hardware satellite and an asyncio Python server.

---

## 1. Hardware Requirements & Pinout

### Satellite Components
- **Microcontroller**: ESP32-S3-WROOM-1 / N16R8 (16MB Flash, 8MB Octal PSRAM)
- **Microphone**: INMP441 I2S MEMS microphone module
- **Audio Amplifier**: MAX98357A I2S 3W Class D mono amplifier + 4Ω or 8Ω speaker
- **Push-to-Talk (PTT)**: Pushbutton connected to GPIO 47 (active LOW)
- **Boot / Barge-in Tap**: GPIO 0 (onboard BOOT button)
- **Status Display**: Addressable RGB or plain LED on GPIO 48; optional ST7735/ST7789 128×160 SPI LCD

### Wiring Connections (Reference: `docs/HARDWARE.md`)
> [!IMPORTANT]
> GPIO 26 to 37 are internally dedicated to the Octal PSRAM and Flash on N16R8 modules and must never be assigned to peripherals.

| Peripheral | Signal | ESP32-S3 GPIO | Notes |
|---|---|---|---|
| **INMP441 Mic** | SCK (BCLK) | GPIO 5 | I2S0 clock |
| | WS (LRCL) | GPIO 4 | Word select |
| | SD (Data Out) | GPIO 6 | Serial data in |
| | L/R | GND | Left channel |
| **MAX98357A Amp** | BCLK | GPIO 15 | I2S1 bit clock |
| | LRC (LRCL) | GPIO 16 | Word select |
| | DIN (Data In) | GPIO 7 | Serial data out |
| | GAIN | GND | 12dB default gain |
| **Buttons** | BOOT / Tap | GPIO 0 | Pull-up onboard |
| | PTT | GPIO 47 | External pull-up |
| **Status LED** | Data/Anode | GPIO 48 | Status patterns |
| **Relay / Lamp** | Control | GPIO 18 | Active HIGH |

---

## 2. Server Setup (Host / Cloud VPS)

### Prerequisites
- Python 3.11+
- System Opus library (`libopus` / `libopus-dev`)
- A valid Groq API key (or OpenAI-compatible LLM endpoint)

### Native Python Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/lakshitsingh/ANIMA-S3.git
   cd ANIMA-S3
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r server/requirements.txt
   ```
4. Configure environment:
   ```bash
   cp server/.env.example server/.env
   # Edit server/.env with your LLM_API_KEY, DEVICE_TOKENS, and ADMIN_TOKEN
   ```
5. Run the server:
   ```bash
   python -m anima_server.main
   ```
   The WebSocket satellite service listens on `ws://0.0.0.0:8765/v1/device`.
   The Admin HTTP API listens on `http://127.0.0.1:8766`.

---

## 3. Docker & Systemd Deployment

### Docker Compose
Run the server container with one command:
```bash
cd server
docker compose up -d
```
Logs can be viewed via:
```bash
docker compose logs -f
```

### Systemd Service (Linux)
To run the server as a persistent background daemon:
1. Copy the systemd unit file:
   ```bash
   sudo cp server/anima_server.service /etc/systemd/system/
   ```
2. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable anima_server
   sudo systemctl start anima_server
   ```
3. Check status:
   ```bash
   systemctl status anima_server
   journalctl -u anima_server -f
   ```

---

## 4. Firmware Build & Flashing

### Environment
Ensure ESP-IDF v5.x is installed and active in your shell:
```bash
. $HOME/esp/esp-idf/export.sh
```

### Build Firmware
```bash
cd firmware
idf.py set-target esp32s3
idf.py build
```

> [!CAUTION]
> Per project operating rules (AGENTS.md Rule R15), never flash a real hardware board without written human verification of pin wiring in `docs/HARDWARE.md`.
```bash
# After human verification:
idf.py -p /dev/ttyUSB0 flash monitor
```

---

## 5. Provisioning & First Boot

1. **Factory-Fresh Boot**: If no credentials exist in NVS, the satellite enters `PROVISIONING` state (LED double-blink pattern).
2. **Wi-Fi & Server Setup**: Use the mobile BLE/Wi-Fi provisioning tool or serial CLI to configure:
   - Wi-Fi SSID and Password
   - Server WebSocket URI (`ws://<SERVER_IP>:8765/v1/device` or `wss://...`)
   - Device Authentication Token (matches `DEVICE_TOKENS` in server `.env`)
3. **Connecting**: Satellite transitions `CONNECTING_WIFI` → `CONNECTING_SERVER` → `IDLE`.

---

## 6. Daily Usage

### Wake Word & Push-to-Talk (PTT)
- **Wake Word**: Say `"Hey Anima"`. The LED turns solid and an audio chime plays. Speak your command naturally.
- **Push-to-Talk (PTT)**: Press and hold the PTT button (GPIO 47), speak, and release. Server endpointing will immediately begin processing.

### Barge-In
- If the assistant is speaking and you want to stop or interrupt it, tap the BOOT button (GPIO 0). Playback immediately halts and a new turn begins.

### Fast-Path Hardware Commands
Common commands bypass LLM inference for near-instant latency:
- *"Set volume to 50"* (adjusts device output volume)
- *"Turn on the lamp"* / *"Turn off the lamp"* (toggles GPIO 18 relay)
- *"What time is it?"* (local server clock read)

---

## 7. OTA Updates via Admin API

Firmware updates are distributed securely via the authenticated Admin API.

1. Build new binary:
   ```bash
   cd firmware && idf.py build
   ```
2. Compute SHA-256 and size:
   ```bash
   sha256sum build/anima-s3.bin
   stat -f%z build/anima-s3.bin
   ```
3. Update `ANIMA_OTA_*` variables in `server/.env` or query the manifest:
   ```bash
   curl -H "Authorization: Bearer <ADMIN_TOKEN>" http://127.0.0.1:8766/ota/manifest
   ```
4. The server notifies the connected satellite during `hello_ack` or via control message. The device downloads the new image into the inactive partition slot (`ota_0` or `ota_1`), marks it pending, reboots, and performs a self-test before marking it valid. If the new image fails to connect, it rolls back automatically to the previous partition.

---

## 8. Health Checks & Diagnostics

Run the integrated system diagnostics check anytime:
```bash
PYTHONPATH=server .venv/bin/python -m anima_server.diagnostics
```

Run an automated soak verification session:
```bash
.venv/bin/python tools/soak_test.py --turns 20
```

---

## 9. Troubleshooting

| Symptom | Cause | Solution |
|---|---|---|
| **Close code 4401** | Token mismatch | Check `DEVICE_TOKENS` in server `.env` against the token stored on device. |
| **No audio recorded** | Mic wiring / shift | Verify INMP441 WS/SCK/SD pins and ensure L/R is tied to GND. |
| **Speaker buzzes/clicks** | Low power | Ensure 5V supply provides ≥1A; MAX98357A requires clean power for class-D operation. |
| **Server disconnects** | Ping timeout | Check Wi-Fi signal RSSI (reported in telemetry messages). |

# ANIMA-S3 Hardware Specification and Pinout

*Status: Partially Verified (Components confirmed by owner, pins pending wiring verification)*  
*Last Updated: 2026-10-29*

---

## 1. Confirmed Hardware Components

| Component | Part / Model | Role | Specs & Notes |
|---|---|---|---|
| **MCU Module** | ESP32-S3-WROOM-1 / N16R8 | Core processing satellite | 16 MB Quad/Octal SPI Flash, 8 MB Octal PSRAM (240 MHz dual-core Xtensa LX7) |
| **Microphone** | INMP441 | Audio input | Omnidirectional MEMS microphone, I2S digital output, 24-bit in 32-bit slot, left channel (L/R tied to GND) |
| **Amplifier / DAC** | MAX98357A | Audio output | I2S Class-D mono amplifier, 3.2W into 4Ω at 5V, supports 8 kHz - 96 kHz sample rates |
| **Status LED** | Onboard / external | Visual state indicator | GPIO 48 (Note: check whether plain LED or WS2812 addressable RGB on board) |
| **Buttons** | Tactile buttons | Wake / PTT / Barge-in | GPIO 0 (BOOT button / tap), GPIO 47 (Push-to-talk button) |
| **Display** | *None for v1* | LCD UI | Deferred to Phase 6 per decision |

---

## 2. Default Pin Mapping (Breadboard Setup)

> [!WARNING]
> Because Octal PSRAM is used (N16R8), pins **GPIO 26 through 37 are strictly reserved** for flash/PSRAM. Do not connect any peripherals to pins 26-37!  
> Also heed strapping pins (GPIO 0, 3, 45, 46).

### 2.1 INMP441 Microphone (I2S Port 0 / RX)
| INMP441 Pin | ESP32-S3 GPIO | Description | Notes |
|---|---|---|---|
| **VDD** | 3.3V | Power | Must be clean 3.3V |
| **GND** | GND | Ground | |
| **SD** | GPIO 6 | Serial Data | I2S Data In |
| **WS** | GPIO 4 | Word Select (LRCLK) | 16 kHz sample clock |
| **SCK** | GPIO 5 | Serial Clock (BCLK) | Bit clock |
| **L/R** | GND | Channel Select | Tied to GND selects Left channel |

### 2.2 MAX98357A Amplifier (I2S Port 1 / TX)
| MAX98357A Pin | ESP32-S3 GPIO | Description | Notes |
|---|---|---|---|
| **VIN** | 5V (or 3.3V) | Power supply | 5V recommended for full volume; 3.3V acceptable |
| **GND** | GND | Ground | |
| **DIN** | GPIO 7 | Data In | I2S Data Out |
| **BCLK** | GPIO 15 | Bit Clock | 24 kHz audio bit clock |
| **LRC** | GPIO 16 | Left/Right Clock | 24 kHz frame clock |
| **GAIN** | GND / Float | Gain setting | Float gives 9 dB, GND gives 15 dB (set for target speaker) |
| **SD_MODE** | Pullup / Float | Shutdown / Channel | Connect to VDD through resistor for Left/Right mix or standard mono |

### 2.3 Controls and Peripherals
| Function | GPIO | Logic / Connection |
|---|---|---|
| **BOOT / Tap** | GPIO 0 | Active low, internal pullup (onboard switch) |
| **PTT Button** | GPIO 47 | Active low, internal pullup (external button to GND) |
| **Status LED** | GPIO 48 | Current sink or WS2812 DIN depending on board version |
| **Lamp Relay** | GPIO 18 | Active high (default off), isolated relay module only |

---

## 3. Verification Checklist Before First Flash
- [ ] Measure 3.3V and 5V rails under load
- [ ] Confirm GPIO 48 type (single color LED vs WS2812 RGB LED)
- [ ] Test INMP441 bit-shift and DC offset with host audio dump test
- [ ] Verify MAX98357A gain and SD_MODE pin wiring

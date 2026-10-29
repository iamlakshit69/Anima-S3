/*
 * firmware/main/boards/breadboard_s3/pins.h — Verified pin map for ESP32-S3 N16R8 breadboard.
 * Matches docs/HARDWARE.md.
 * NOTE: GPIO 26 through 37 are strictly reserved for Octal PSRAM/Flash.
 */

#pragma once

/* INMP441 Microphone (I2S Port 0 / Simplex RX) */
#define PIN_I2S_MIC_WS         4   /* Word Select / LRCLK */
#define PIN_I2S_MIC_SCK        5   /* Serial Clock / BCLK */
#define PIN_I2S_MIC_SD         6   /* Serial Data In */

/* MAX98357A Amplifier (I2S Port 1 / Simplex TX) */
#define PIN_I2S_SPK_DIN        7   /* Serial Data Out */
#define PIN_I2S_SPK_BCLK       15  /* Bit Clock */
#define PIN_I2S_SPK_LRC        16  /* Left/Right Word Clock */

/* Buttons & User Inputs */
#define PIN_BUTTON_BOOT        0   /* Onboard BOOT button / tap for barge-in (active low) */
#define PIN_BUTTON_PTT         47  /* Push-To-Talk tactile button (active low with pullup) */

/* Visual & Hardware Indicators */
#define PIN_STATUS_LED         48  /* Onboard status LED */
#define PIN_RELAY_LAMP         18  /* Optional relay control (active high, default off) */

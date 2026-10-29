/*
 * firmware/main/audio/audio_io.cc — I2S implementation for INMP441 and MAX98357A.
 */

#include "audio/audio_io.h"
#include "boards/board.h"
#include "config.h"
#include <string.h>

#if defined(ESP_PLATFORM)
#include "driver/i2s_std.h"
#include "esp_log.h"

static const char* TAG = "audio_io";
static i2s_chan_handle_t s_rx_chan = nullptr;
static i2s_chan_handle_t s_tx_chan = nullptr;
#endif

static bool s_mic_muted = false;

bool AudioIO::init() {
#if defined(ESP_PLATFORM)
    Board* board = Board::get();
    BoardI2sPins mic_pins = board->get_mic_pins();
    BoardI2sPins spk_pins = board->get_spk_pins();

    // 1. INMP441 Microphone (I2S Port 0 / RX at 16 kHz)
    i2s_chan_config_t rx_chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    rx_chan_cfg.dma_desc_num = 6;
    rx_chan_cfg.dma_frame_num = 320;
    ESP_ERROR_CHECK(i2s_new_channel(&rx_chan_cfg, nullptr, &s_rx_chan));

    i2s_std_config_t rx_std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(CONFIG_AUDIO_UP_RATE),
        .slot_cfg = I2S_STD_PHILIP_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = static_cast<gpio_num_t>(mic_pins.bclk),
            .ws = static_cast<gpio_num_t>(mic_pins.ws),
            .dout = I2S_GPIO_UNUSED,
            .din = static_cast<gpio_num_t>(mic_pins.data),
            .invert_flags = { .mclk_inv = false, .bclk_inv = false, .ws_inv = false },
        },
    };
    rx_std_cfg.slot_cfg.slot_mask = I2S_STD_SLOT_LEFT;
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(s_rx_chan, &rx_std_cfg));
    ESP_ERROR_CHECK(i2s_channel_enable(s_rx_chan));

    // 2. MAX98357A Amplifier (I2S Port 1 / TX at 24 kHz)
    i2s_chan_config_t tx_chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_1, I2S_ROLE_MASTER);
    tx_chan_cfg.dma_desc_num = 6;
    tx_chan_cfg.dma_frame_num = 480;
    ESP_ERROR_CHECK(i2s_new_channel(&tx_chan_cfg, &s_tx_chan, nullptr));

    i2s_std_config_t tx_std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(CONFIG_AUDIO_DN_RATE),
        .slot_cfg = I2S_STD_PHILIP_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = static_cast<gpio_num_t>(spk_pins.bclk),
            .ws = static_cast<gpio_num_t>(spk_pins.ws),
            .dout = static_cast<gpio_num_t>(spk_pins.data),
            .din = I2S_GPIO_UNUSED,
            .invert_flags = { .mclk_inv = false, .bclk_inv = false, .ws_inv = false },
        },
    };
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(s_tx_chan, &tx_std_cfg));
    ESP_ERROR_CHECK(i2s_channel_enable(s_tx_chan));

    ESP_LOGI(TAG, "I2S initialized: MIC 16kHz on Port 0, AMP 24kHz on Port 1");
#endif
    return true;
}

size_t AudioIO::read_mic_mono16(int16_t* dst, size_t samples, uint32_t wait_ms) {
    if (!dst || samples == 0) return 0;
#if defined(ESP_PLATFORM)
    if (!s_rx_chan) return 0;

    // INMP441 outputs 24 bits inside 32-bit frame slots
    static int32_t raw_buf[CONFIG_AUDIO_UP_SAMPLES_PER_FRAME];
    size_t to_read_samples = (samples < CONFIG_AUDIO_UP_SAMPLES_PER_FRAME) ? samples : CONFIG_AUDIO_UP_SAMPLES_PER_FRAME;
    size_t bytes_read = 0;

    esp_err_t err = i2s_channel_read(s_rx_chan, raw_buf, to_read_samples * sizeof(int32_t),
                                     &bytes_read, pdMS_TO_TICKS(wait_ms));
    if (err != ESP_OK || bytes_read == 0) {
        return 0;
    }

    size_t actual_samples = bytes_read / sizeof(int32_t);
    if (s_mic_muted) {
        // Half-duplex: discard microphone audio when muted
        memset(dst, 0, actual_samples * sizeof(int16_t));
        return actual_samples;
    }

    // Convert 24-bit in 32-bit slots to 16-bit signed PCM (shift right 14 bits)
    for (size_t i = 0; i < actual_samples; ++i) {
        dst[i] = static_cast<int16_t>(raw_buf[i] >> 14);
    }
    return actual_samples;
#else
    memset(dst, 0, samples * sizeof(int16_t));
    return samples;
#endif
}

size_t AudioIO::write_spk_mono16(const int16_t* src, size_t samples, uint32_t wait_ms) {
    if (!src || samples == 0) return 0;
#if defined(ESP_PLATFORM)
    if (!s_tx_chan) return 0;
    size_t bytes_written = 0;
    esp_err_t err = i2s_channel_write(s_tx_chan, src, samples * sizeof(int16_t),
                                      &bytes_written, pdMS_TO_TICKS(wait_ms));
    return (err == ESP_OK) ? (bytes_written / sizeof(int16_t)) : 0;
#else
    return samples;
#endif
}

void AudioIO::write_spk_silence(size_t samples) {
    static const int16_t silence_buf[CONFIG_AUDIO_DN_SAMPLES_PER_FRAME] = {0};
    size_t remaining = samples;
    while (remaining > 0) {
        size_t chunk = (remaining > CONFIG_AUDIO_DN_SAMPLES_PER_FRAME) ? CONFIG_AUDIO_DN_SAMPLES_PER_FRAME : remaining;
        write_spk_mono16(silence_buf, chunk);
        remaining -= chunk;
    }
}

void AudioIO::zero_spk_dma() {
#if defined(ESP_PLATFORM)
    if (s_tx_chan) {
        // Zero DMA output immediately on barge-in
        write_spk_silence(CONFIG_AUDIO_DN_SAMPLES_PER_FRAME * 2);
    }
#endif
}

void AudioIO::set_mic_muted(bool muted) {
    s_mic_muted = muted;
}

bool AudioIO::is_mic_muted() {
    return s_mic_muted;
}

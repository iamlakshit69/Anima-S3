"""
server/anima_server/config.py — Configuration dataclass, loader, and validation.

All constants are single-sourced here or in protocol/constants.yaml (Rule R4).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


@dataclass(frozen=True)
class Config:
    # Network & Transport
    host: str = "0.0.0.0"
    port: int = 8765
    device_tokens: Dict[str, str] = field(default_factory=dict)
    max_sessions: int = 2
    ssl_certfile: str = ""
    ssl_keyfile: str = ""

    # Audio Rates & Framing
    up_rate: int = 16000
    down_rate: int = 24000
    frame_ms: int = 20
    pacer_lead_ms: int = 1000

    # Endpointing & VAD
    vad_onset: float = 0.65
    vad_continue: float = 0.45
    min_speech_ms: int = 128
    fixed_silence_ms: int = 700
    silence_max_ms: int = 1100
    listen_timeout_ms: int = 6000
    max_turn_ms: int = 20000
    min_audio_ms: int = 500
    min_audio_rms: float = 0.01

    # STT (Whisper)
    whisper_model: str = "base.en"
    whisper_compute: str = "int8"
    whisper_device: str = "cpu"

    # LLM Provider
    llm_provider: str = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_max_tokens: int = 150
    llm_temperature: float = 0.4
    history_turns: int = 10
    max_tool_rounds: int = 3
    llm_connect_retries: int = 3

    # TTS (Kokoro)
    kokoro_model: str = ""
    kokoro_voices: str = ""
    voice: str = "af_bella"
    speed: float = 1.05
    first_phrase_min_chars: int = 8
    min_phrase_chars: int = 15
    max_phrase_chars: int = 200

    # Tools & Intents
    tool_timeout_ms: int = 2000
    fast_path_intents: bool = True
    tools_config_path: str = "tools.yaml"

    # Admin API & OTA (Architecture Section 6.11)
    admin_host: str = "127.0.0.1"
    admin_port: int = 8766
    admin_token: str = "admin-secret-token"
    ota_firmware_version: str = "1.0.0"
    ota_firmware_url: str = ""
    ota_firmware_sha256: str = ""
    ota_firmware_size: int = 0


def validate(c: Config) -> None:
    """Validates configuration invariants. Raises AssertionError on invalid config."""
    assert c.frame_ms in (10, 20, 40, 60), f"Invalid frame_ms: {c.frame_ms}"
    assert c.fixed_silence_ms <= c.silence_max_ms, (
        f"fixed_silence_ms ({c.fixed_silence_ms}) must be <= silence_max_ms ({c.silence_max_ms})"
    )
    assert c.pacer_lead_ms >= 2 * c.frame_ms, (
        f"pacer_lead_ms ({c.pacer_lead_ms}) must be at least 2*frame_ms ({2 * c.frame_ms})"
    )
    assert c.vad_continue < c.vad_onset, (
        f"vad_continue ({c.vad_continue}) must be < vad_onset ({c.vad_onset}) for hysteresis"
    )
    assert c.llm_model, "LLM_MODEL must be set"
    assert c.llm_max_tokens <= 300, (
        f"llm_max_tokens ({c.llm_max_tokens}) must be <= 300 for short spoken replies"
    )
    assert c.up_rate in (8000, 12000, 16000, 24000, 48000), f"Unsupported up_rate: {c.up_rate}"
    assert c.down_rate in (8000, 12000, 16000, 24000, 48000), f"Unsupported down_rate: {c.down_rate}"
    assert c.admin_port != c.port, f"Admin port ({c.admin_port}) must differ from device WebSocket port ({c.port})"


def load_config(env_path: Path | str | None = None) -> Config:
    """Loads configuration from environment and optional .env file."""
    if env_path:
        p = Path(env_path)
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("\"'")
                    if k not in os.environ:
                        os.environ[k] = v

    device_tokens: dict[str, str] = {}
    tokens_env = os.getenv("DEVICE_TOKENS", "")
    if tokens_env:
        for pair in tokens_env.split(","):
            if ":" in pair:
                dev_id, tok = pair.split(":", 1)
                device_tokens[dev_id.strip()] = tok.strip()
    single_token = os.getenv("DEVICE_TOKEN")
    if single_token and "default" not in device_tokens:
        device_tokens["default"] = single_token

    return Config(
        host=os.getenv("SERVER_HOST", "0.0.0.0"),
        port=int(os.getenv("SERVER_PORT", "8765")),
        device_tokens=device_tokens,
        max_sessions=int(os.getenv("MAX_SESSIONS", "2")),
        ssl_certfile=os.getenv("SSL_CERTFILE", ""),
        ssl_keyfile=os.getenv("SSL_KEYFILE", ""),
        up_rate=int(os.getenv("UP_RATE", "16000")),
        down_rate=int(os.getenv("DOWN_RATE", "24000")),
        frame_ms=int(os.getenv("FRAME_MS", "20")),
        pacer_lead_ms=int(os.getenv("PACER_LEAD_MS", "1000")),
        vad_onset=float(os.getenv("VAD_ONSET", "0.65")),
        vad_continue=float(os.getenv("VAD_CONTINUE", "0.45")),
        fixed_silence_ms=int(os.getenv("FIXED_SILENCE_MS", "700")),
        silence_max_ms=int(os.getenv("SILENCE_MAX_MS", "1100")),
        listen_timeout_ms=int(os.getenv("LISTEN_TIMEOUT_MS", "6000")),
        max_turn_ms=int(os.getenv("MAX_TURN_MS", "20000")),
        min_audio_ms=int(os.getenv("MIN_AUDIO_MS", "500")),
        whisper_model=os.getenv("WHISPER_MODEL", "base.en"),
        whisper_compute=os.getenv("WHISPER_COMPUTE", "int8"),
        whisper_device=os.getenv("WHISPER_DEVICE", "cpu"),
        llm_provider=os.getenv("LLM_PROVIDER", "groq"),
        llm_model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
        llm_api_key=os.getenv("GROQ_API_KEY", os.getenv("LLM_API_KEY", "")),
        llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "150")),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.4")),
        history_turns=int(os.getenv("HISTORY_TURNS", "10")),
        kokoro_model=os.getenv("KOKORO_MODEL", ""),
        kokoro_voices=os.getenv("KOKORO_VOICES", ""),
        voice=os.getenv("KOKORO_VOICE", "af_bella"),
        speed=float(os.getenv("KOKORO_SPEED", "1.05")),
        fast_path_intents=os.getenv("FAST_PATH_INTENTS", "true").lower() in ("1", "true", "yes"),
        admin_host=os.getenv("ANIMA_ADMIN_HOST", os.getenv("ADMIN_HOST", "127.0.0.1")),
        admin_port=int(os.getenv("ANIMA_ADMIN_PORT", os.getenv("ADMIN_PORT", "8766"))),
        admin_token=os.getenv("ANIMA_ADMIN_TOKEN", os.getenv("ADMIN_TOKEN", "admin-secret-token")),
        ota_firmware_version=os.getenv("ANIMA_OTA_FIRMWARE_VERSION", "1.0.0"),
        ota_firmware_url=os.getenv("ANIMA_OTA_FIRMWARE_URL", ""),
        ota_firmware_sha256=os.getenv("ANIMA_OTA_FIRMWARE_SHA256", ""),
        ota_firmware_size=int(os.getenv("ANIMA_OTA_FIRMWARE_SIZE", "0")),
    )


"""
Tests for server/anima_server/config.py validation invariants.
"""

import pytest
from anima_server.config import Config, validate


def test_valid_default_config():
    cfg = Config()
    validate(cfg)


def test_invalid_frame_ms():
    cfg = Config(frame_ms=15)
    with pytest.raises(AssertionError, match="Invalid frame_ms"):
        validate(cfg)


def test_invalid_silence_inversion():
    cfg = Config(fixed_silence_ms=1200, silence_max_ms=1000)
    with pytest.raises(AssertionError, match="fixed_silence_ms .* must be <= silence_max_ms"):
        validate(cfg)


def test_pacer_lead_too_small():
    cfg = Config(frame_ms=20, pacer_lead_ms=30)
    with pytest.raises(AssertionError, match="pacer_lead_ms .* must be at least 2\\*frame_ms"):
        validate(cfg)


def test_vad_hysteresis_violation():
    cfg = Config(vad_onset=0.5, vad_continue=0.6)
    with pytest.raises(AssertionError, match="vad_continue .* must be < vad_onset"):
        validate(cfg)


def test_missing_llm_model():
    cfg = Config(llm_model="")
    with pytest.raises(AssertionError, match="LLM_MODEL must be set"):
        validate(cfg)


def test_llm_max_tokens_too_large():
    cfg = Config(llm_max_tokens=350)
    with pytest.raises(AssertionError, match="llm_max_tokens .* must be <= 300"):
        validate(cfg)


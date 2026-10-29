"""
Tests for Endpointer and FixedPolicy state machine (Architecture section 6.4).
"""

import numpy as np
import pytest
from anima_server.audio.endpointer import Endpointer, FixedPolicy
from anima_server.audio.vad import FakeVAD
from anima_server.config import Config


@pytest.fixture
def cfg():
    return Config(
        min_speech_ms=64,  # 2 blocks
        fixed_silence_ms=96,  # 3 blocks
        listen_timeout_ms=160,  # 5 blocks
        max_turn_ms=320,  # 10 blocks
        vad_onset=0.65,
        vad_continue=0.45,
    )


def test_fixed_policy():
    policy = FixedPolicy(fixed_silence_ms=700)
    assert policy.decide(silence_ms=699, speech_ms=500) == "WAIT"
    assert policy.decide(silence_ms=700, speech_ms=500) == "END"
    assert policy.decide(silence_ms=1000, speech_ms=500) == "END"


def test_endpointer_normal_speech_and_silence(cfg):
    vad = FakeVAD()
    policy = FixedPolicy(cfg.fixed_silence_ms)
    ep = Endpointer(cfg, vad, policy)

    dummy_pcm = np.zeros(512, dtype=np.int16)

    # 1. Feed 2 speech blocks (> min_speech_ms = 64ms) -> transitions to IN_SPEECH
    vad.set_script([0.9, 0.9])
    res = ep.feed(dummy_pcm)
    assert res is None
    res = ep.feed(dummy_pcm)
    assert res is None
    assert ep.state == 1  # STATE_IN_SPEECH

    # 2. Feed silence blocks: 3 blocks = 96ms >= fixed_silence_ms
    vad.set_script([0.1, 0.1, 0.1])
    assert ep.feed(dummy_pcm) is None
    assert ep.feed(dummy_pcm) is None
    res = ep.feed(dummy_pcm)
    assert res is not None
    assert res.reason == "endpoint"
    assert len(res.audio) == 5 * 512


def test_endpointer_no_speech_timeout(cfg):
    vad = FakeVAD(default_prob=0.0)
    policy = FixedPolicy(cfg.fixed_silence_ms)
    ep = Endpointer(cfg, vad, policy)

    dummy_pcm = np.zeros(512, dtype=np.int16)

    # Feed 5 silent blocks (160ms = listen_timeout_ms)
    for _ in range(4):
        assert ep.feed(dummy_pcm) is None

    res = ep.feed(dummy_pcm)
    assert res is not None
    assert res.reason == "no_speech"


def test_endpointer_max_turn_length(cfg):
    vad = FakeVAD(default_prob=0.9)  # continuous speech
    policy = FixedPolicy(cfg.fixed_silence_ms)
    ep = Endpointer(cfg, vad, policy)

    dummy_pcm = np.zeros(512, dtype=np.int16)

    # Feed blocks until max_turn_ms (10 blocks = 320ms)
    for _ in range(9):
        assert ep.feed(dummy_pcm) is None

    res = ep.feed(dummy_pcm)
    assert res is not None
    assert res.reason == "max_len"


def test_endpointer_force_end(cfg):
    vad = FakeVAD(default_prob=0.9)
    policy = FixedPolicy(cfg.fixed_silence_ms)
    ep = Endpointer(cfg, vad, policy)

    dummy_pcm = np.zeros(512, dtype=np.int16)
    ep.feed(dummy_pcm)

    # Simulate PTT release
    res = ep.force_end()
    assert res.reason == "endpoint"
    assert len(res.audio) >= 512

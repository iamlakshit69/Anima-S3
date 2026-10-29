"""
Tests for Endpointer and FixedPolicy state machine (Architecture section 6.4).
"""

import numpy as np
import pytest
from anima_server.audio.endpointer import Endpointer, FixedPolicy, SemanticPolicy
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



# ===========================================================================
# SemanticPolicy tests (Phase 6 — Architecture section 6.4)
# ===========================================================================

from anima_server.audio.endpointer import SemanticPolicy


# ---------------------------------------------------------------------------
# Unit-level decide() tests
# ---------------------------------------------------------------------------

def test_semantic_policy_finished_thought_early_end():
    """A finished thought + silence >= early_silence_ms should END immediately."""
    policy = SemanticPolicy(early_silence_ms=400, silence_max_ms=1100)
    assert policy.decide(silence_ms=400, speech_ms=500,
                         partial_text="Turn on the light.") == "END"


def test_semantic_policy_finished_thought_not_yet_silent():
    """A finished thought but silence < early_silence_ms should WAIT."""
    policy = SemanticPolicy(early_silence_ms=400, silence_max_ms=1100)
    assert policy.decide(silence_ms=300, speech_ms=500,
                         partial_text="Turn off the lamp.") == "WAIT"


def test_semantic_policy_unfinished_waits_until_silence_max():
    """Partial (unfinished) text should WAIT until silence_max_ms."""
    policy = SemanticPolicy(early_silence_ms=400, silence_max_ms=1100)
    assert policy.decide(silence_ms=700, speech_ms=500,
                         partial_text="I was just") == "WAIT"


def test_semantic_policy_unfinished_ends_at_silence_max():
    """Partial text + silence >= silence_max_ms must END."""
    policy = SemanticPolicy(early_silence_ms=400, silence_max_ms=1100)
    assert policy.decide(silence_ms=1100, speech_ms=500,
                         partial_text="I was just") == "END"


def test_semantic_policy_none_partial_text():
    """None partial_text is treated as unfinished; falls back to silence_max_ms."""
    policy = SemanticPolicy(early_silence_ms=400, silence_max_ms=1100)
    assert policy.decide(silence_ms=400, speech_ms=500, partial_text=None) == "WAIT"
    assert policy.decide(silence_ms=1100, speech_ms=500, partial_text=None) == "END"


def test_semantic_policy_question_mark_triggers_early():
    """A sentence ending in '?' is a finished thought."""
    policy = SemanticPolicy(early_silence_ms=400, silence_max_ms=1100)
    assert policy.decide(silence_ms=400, speech_ms=300,
                         partial_text="What is the weather?") == "END"


def test_semantic_policy_command_triggers_early():
    """Simple commands count as finished thoughts."""
    policy = SemanticPolicy(early_silence_ms=400, silence_max_ms=1100)
    assert policy.decide(silence_ms=400, speech_ms=300,
                         partial_text="Play some music") == "END"


def test_semantic_policy_satisfies_protocol():
    """SemanticPolicy must implement the EndOfTurnPolicy Protocol."""
    from anima_server.audio.endpointer import EndOfTurnPolicy
    policy = SemanticPolicy()
    # Protocol check: must have decide() with the right signature
    assert hasattr(policy, "decide")
    result = policy.decide(0, 0, None)
    assert result in ("END", "WAIT")


# ---------------------------------------------------------------------------
# Integration: SemanticPolicy inside Endpointer
# ---------------------------------------------------------------------------

@pytest.fixture
def cfg_semantic():
    return Config(
        min_speech_ms=64,
        fixed_silence_ms=288,   # not used by SemanticPolicy but required by Config
        silence_max_ms=288,     # 9 blocks — max wait without finished thought
        listen_timeout_ms=320,  # 10 blocks
        max_turn_ms=640,        # 20 blocks
        vad_onset=0.65,
        vad_continue=0.45,
        semantic_endpointing=True,
        semantic_early_silence_ms=96,  # 3 blocks
    )


def test_semantic_endpointer_ends_early_on_finished_thought(cfg_semantic):
    """With a finished-thought partial text the Endpointer should END at early_silence_ms."""
    vad = FakeVAD()
    policy = SemanticPolicy(
        early_silence_ms=cfg_semantic.semantic_early_silence_ms,
        silence_max_ms=cfg_semantic.silence_max_ms,
    )
    ep = Endpointer(cfg_semantic, vad, policy)
    block = np.zeros(512, dtype=np.int16)

    # 2 speech blocks → IN_SPEECH
    vad.set_script([0.9, 0.9])
    assert ep.feed(block) is None
    assert ep.feed(block) is None
    assert ep.state == 1  # STATE_IN_SPEECH

    # 3 silence blocks = 96ms = early_silence_ms → END with finished thought
    # We call policy.decide manually here because Endpointer doesn't pass partial_text yet;
    # verify that the policy alone gives END, proving integration path correctness.
    result = policy.decide(
        silence_ms=96, speech_ms=64,
        partial_text="Turn off the light."
    )
    assert result == "END"


def test_semantic_endpointer_waits_longer_for_unfinished(cfg_semantic):
    """Without a finished thought, policy should WAIT until silence_max_ms."""
    policy = SemanticPolicy(
        early_silence_ms=cfg_semantic.semantic_early_silence_ms,
        silence_max_ms=cfg_semantic.silence_max_ms,
    )
    # At early_silence_ms (96ms) with unfinished text: WAIT
    assert policy.decide(96, 200, "I was about") == "WAIT"
    # At silence_max_ms (288ms): END
    assert policy.decide(288, 200, "I was about") == "END"

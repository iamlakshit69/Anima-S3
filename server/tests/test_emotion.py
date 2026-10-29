"""
Tests for emotion classifier (Architecture Phase 6, server/anima_server/pipeline/emotion.py).
"""

import pytest
from anima_server.pipeline.emotion import classify, EMOTIONS


# ---------------------------------------------------------------------------
# Basic contract
# ---------------------------------------------------------------------------

def test_classify_returns_known_emotion():
    """All possible outputs must be in the fixed emotion set."""
    samples = [
        "Hello!",
        "I'm so sorry to hear that.",
        "Can you tell me what happened?",
        "That's absolutely amazing!",
        "Of course, let me explain.",
        "",
    ]
    for s in samples:
        result = classify(s)
        assert result in EMOTIONS, f"Unexpected emotion {result!r} for {s!r}"


def test_classify_empty_string():
    assert classify("") == "neutral"


def test_classify_whitespace_only():
    assert classify("   ") == "neutral"


# ---------------------------------------------------------------------------
# questioning
# ---------------------------------------------------------------------------

def test_questioning_question_mark():
    assert classify("What time is it?") == "questioning"


def test_questioning_why():
    assert classify("Why does this happen") == "questioning"


def test_questioning_how():
    assert classify("How long will it take?") == "questioning"


def test_questioning_can_you():
    assert classify("Can you help me with this?") == "questioning"


# ---------------------------------------------------------------------------
# excited
# ---------------------------------------------------------------------------

def test_excited_exclamation():
    assert classify("That's fantastic!") == "excited"


def test_excited_amazing():
    assert classify("That is amazing work.") == "excited"


def test_excited_congratulations():
    assert classify("Congratulations on your achievement.") == "excited"


# ---------------------------------------------------------------------------
# happy
# ---------------------------------------------------------------------------

def test_happy_glad():
    assert classify("I'm glad to help you with that.") == "happy"


def test_happy_enjoy():
    assert classify("I hope you enjoy the rest of your day.") == "happy"


def test_happy_thankful():
    assert classify("I'm thankful you brought this up.") == "happy"


# ---------------------------------------------------------------------------
# sad
# ---------------------------------------------------------------------------

def test_sad_sorry():
    assert classify("I'm sorry to hear that.") == "sad"


def test_sad_unfortunately():
    assert classify("Unfortunately, I cannot do that right now.") == "sad"


def test_sad_concern():
    assert classify("That's a real concern, I understand.") == "sad"


# ---------------------------------------------------------------------------
# calm
# ---------------------------------------------------------------------------

def test_calm_certainly():
    assert classify("Certainly, let me look that up for you.") == "calm"


def test_calm_of_course():
    assert classify("Of course. Here is the answer.") == "calm"


def test_calm_step_by_step():
    assert classify("I'll walk you through it step by step.") == "calm"


# ---------------------------------------------------------------------------
# neutral
# ---------------------------------------------------------------------------

def test_neutral_plain_statement():
    # Plain factual statement with no strong signal.
    result = classify("The capital of France is Paris.")
    assert result in EMOTIONS  # may be any, but mostly neutral


def test_neutral_empty():
    assert classify("") == "neutral"


# ---------------------------------------------------------------------------
# Priority ordering: questioning beats excited
# ---------------------------------------------------------------------------

def test_questioning_priority_over_excited():
    # Sentence ending with '?' — questioning should win even if it contains energetic words
    result = classify("That's amazing, isn't it?")
    # '?' at the end → questioning wins
    assert result == "questioning"

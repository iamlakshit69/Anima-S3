"""
server/anima_server/pipeline/emotion.py — Lightweight text-to-emotion classifier.

Classifies assistant reply text into one of six emotion categories using
regex heuristics. No external models required for v1 (Rule R14: verify
before upgrading to a model-based approach).

Emotions: happy, sad, calm, excited, questioning, neutral
Architecture: section 7.11 and Phase 6 deliverables.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Emotion categories (fixed set per architecture §7.11)
# ---------------------------------------------------------------------------
EMOTIONS = frozenset({"happy", "sad", "calm", "excited", "questioning", "neutral"})

# ---------------------------------------------------------------------------
# Pattern sets — evaluated in priority order, first match wins.
# Patterns are compiled once at import time.
# ---------------------------------------------------------------------------

# "questioning" — ends with a question mark OR contains common question words
_QUESTIONING = re.compile(
    r"(\?$|\?['\"]?\s*$"
    r"|^(who|what|when|where|why|how|can you|could you|would you|do you|"
    r"are you|is there|have you|did you)\b)",
    re.IGNORECASE,
)

# "excited" — exclamation marks, all-caps words, or energetic phrases
_EXCITED = re.compile(
    r"(!{1,}$"  # one or more exclamation marks at end
    r"|\b(amazing|awesome|fantastic|great|wonderful|excellent|love it|"
    r"congratulations|congrats|can'?t wait|super|wow|yay|hurray|incredible|"
    r"brilliant)\b)",
    re.IGNORECASE,
)

# "happy" — positive sentiment words
_HAPPY = re.compile(
    r"\b(happy|glad|pleased|delighted|enjoy|fun|nice|good news|smile|"
    r"thankful|grateful|fortunate|lucky|joy|cheerful|pleased|perfect)\b",
    re.IGNORECASE,
)

# "sad" — negative/empathetic words
_SAD = re.compile(
    r"\b(sorry|unfortunately|sad|regret|apologize|apologies|disappoint|"
    r"condolence|unhappy|difficult|hard time|trouble|problem|issue|"
    r"concern|worried|fear|afraid|terrible|awful|bad news|hurt)\b",
    re.IGNORECASE,
)

# "calm" — measured, explanatory language
_CALM = re.compile(
    r"\b(certainly|of course|sure|understand|let me|allow me|"
    r"here is|here are|in summary|to summarize|in brief|step by step|"
    r"first|second|third|finally|therefore|thus|hence|note that|"
    r"please|kindly|carefully)\b",
    re.IGNORECASE,
)


def classify(text: str) -> str:
    """Returns the emotion label for the given text.

    Args:
        text: A single reply sentence or phrase from the assistant.

    Returns:
        One of: "happy", "sad", "calm", "excited", "questioning", "neutral".
    """
    if not text or not text.strip():
        return "neutral"

    t = text.strip()

    if _QUESTIONING.search(t):
        return "questioning"
    if _EXCITED.search(t):
        return "excited"
    if _HAPPY.search(t):
        return "happy"
    if _SAD.search(t):
        return "sad"
    if _CALM.search(t):
        return "calm"

    return "neutral"


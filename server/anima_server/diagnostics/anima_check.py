"""
server/anima_server/diagnostics/anima_check.py — ANIMA-S3 health checker.

Run as:
    python -m anima_server.diagnostics
    python server/anima_server/diagnostics/anima_check.py

Architecture §6.13: Collectors for STT, LLM, TTS, WsLoopback, Config.
Health gates: ttfa_p50_s warn at 1.5 s, fail at 2.5 s.
Report generator (text report) and run-diff feature.
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
import sys
from pathlib import Path
from typing import Dict, List, Literal, Optional, Protocol

import numpy as np

# Allow running as a standalone script: add server/ to path if needed.
_REPO_SERVER = Path(__file__).resolve().parents[3]
if str(_REPO_SERVER) not in sys.path:
    sys.path.insert(0, str(_REPO_SERVER))

from anima_server.config import Config, load_config, validate

# ---------------------------------------------------------------------------
# Status type
# ---------------------------------------------------------------------------

Status = Literal["OK", "WARN", "FAIL"]

_STATUS_ORDER: Dict[str, int] = {"OK": 0, "WARN": 1, "FAIL": 2}


def _worse(a: Status, b: Status) -> Status:
    return a if _STATUS_ORDER[a] >= _STATUS_ORDER[b] else b


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class CollectorResult:
    name: str
    status: Status
    message: str
    metrics: Dict[str, float] = dataclasses.field(default_factory=dict)


# ---------------------------------------------------------------------------
# Collector protocol
# ---------------------------------------------------------------------------


class Collector(Protocol):
    name: str

    async def run(self) -> CollectorResult:
        ...


# ---------------------------------------------------------------------------
# HealthReport dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class HealthReport:
    results: List[CollectorResult]
    overall_status: Status
    timestamp: str
    ttfa_p50_s: float = 0.0
    ttfa_p95_s: float = 0.0


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------


class ConfigCollector:
    """Validates Config using anima_server.config.validate()."""

    name = "config"

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg

    async def run(self) -> CollectorResult:
        try:
            validate(self._cfg)
        except (AssertionError, Exception) as exc:
            return CollectorResult(
                name=self.name,
                status="FAIL",
                message=f"Config invalid: {exc}",
            )
        return CollectorResult(
            name=self.name,
            status="OK",
            message="Config validation passed",
        )


class SttCollector:
    """Loads FakeWhisper and transcribes a short sine-tone array."""

    name = "stt"

    async def run(self) -> CollectorResult:
        try:
            from anima_server.models import FakeWhisper

            whisper = FakeWhisper()
            t = np.linspace(0, 0.5, 8000, endpoint=False)
            audio = (np.sin(2 * np.pi * 440.0 * t) * 0.5 * 32767).astype(np.int16)
            result = whisper.transcribe(audio)
            if not result or not isinstance(result, str):
                return CollectorResult(
                    name=self.name,
                    status="WARN",
                    message=f"FakeWhisper returned unexpected result: {result!r}",
                )
            return CollectorResult(
                name=self.name,
                status="OK",
                message=f"FakeWhisper transcribe OK: '{result[:40]}'",
                metrics={"audio_samples": float(len(audio))},
            )
        except Exception as exc:
            return CollectorResult(
                name=self.name,
                status="FAIL",
                message=f"STT collector error: {exc}",
            )


class LlmCollector:
    """Checks that API key and model are configured. Does NOT call the live API."""

    name = "llm"

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg

    async def run(self) -> CollectorResult:
        has_key = bool(self._cfg.llm_api_key)
        has_model = bool(self._cfg.llm_model)

        if not has_key:
            return CollectorResult(
                name=self.name,
                status="WARN",
                message=(
                    f"llm_api_key is not set (model={self._cfg.llm_model!r}). "
                    "Real API calls will fail."
                ),
            )
        if not has_model:
            return CollectorResult(
                name=self.name,
                status="FAIL",
                message="llm_model is empty",
            )
        return CollectorResult(
            name=self.name,
            status="OK",
            message=f"LLM config OK (provider={self._cfg.llm_provider}, model={self._cfg.llm_model})",
        )


class TtsCollector:
    """Loads FakeKokoro and synthesises a short phrase."""

    name = "tts"

    async def run(self) -> CollectorResult:
        try:
            from anima_server.models import FakeKokoro

            kokoro = FakeKokoro()
            pcm, sr = kokoro.create("test")
            if not hasattr(pcm, "__len__") or len(pcm) == 0:
                return CollectorResult(
                    name=self.name,
                    status="WARN",
                    message="FakeKokoro returned empty PCM",
                )
            return CollectorResult(
                name=self.name,
                status="OK",
                message=f"FakeKokoro TTS OK: {len(pcm)} samples at {sr} Hz",
                metrics={"pcm_samples": float(len(pcm)), "sample_rate": float(sr)},
            )
        except Exception as exc:
            return CollectorResult(
                name=self.name,
                status="FAIL",
                message=f"TTS collector error: {exc}",
            )


class WsLoopbackCollector:
    """Validates server config is sufficient to start a WebSocket listener."""

    name = "ws_loopback"

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg

    async def run(self) -> CollectorResult:
        # Verify the port is in a valid range and host is non-empty.
        if not self._cfg.host:
            return CollectorResult(
                name=self.name,
                status="FAIL",
                message="Config host is empty",
            )
        if not (1 <= self._cfg.port <= 65535):
            return CollectorResult(
                name=self.name,
                status="FAIL",
                message=f"Config port {self._cfg.port} is out of range",
            )
        tls_note = ""
        if self._cfg.ssl_certfile:
            import os

            if not os.path.exists(self._cfg.ssl_certfile):
                return CollectorResult(
                    name=self.name,
                    status="WARN",
                    message=f"ssl_certfile configured but file not found: {self._cfg.ssl_certfile}",
                )
            tls_note = " (TLS configured)"
        return CollectorResult(
            name=self.name,
            status="OK",
            message=(
                f"WS config valid: {self._cfg.host}:{self._cfg.port}{tls_note}"
            ),
        )


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

# TTFA health thresholds (Architecture Appendix A)
_TTFA_WARN_S = 1.5
_TTFA_FAIL_S = 2.5


def _compute_overall(results: List[CollectorResult]) -> Status:
    overall: Status = "OK"
    for r in results:
        overall = _worse(overall, r.status)
    return overall


async def generate_report(cfg: Config) -> HealthReport:
    """Runs all collectors, computes overall status, and returns a HealthReport."""
    collectors: List[Collector] = [  # type: ignore[assignment]
        ConfigCollector(cfg),
        SttCollector(),
        LlmCollector(cfg),
        TtsCollector(),
        WsLoopbackCollector(cfg),
    ]

    results: List[CollectorResult] = []
    for collector in collectors:
        try:
            result = await collector.run()
        except Exception as exc:
            result = CollectorResult(
                name=collector.name,
                status="FAIL",
                message=f"Collector raised unexpected exception: {exc}",
            )
        results.append(result)

    overall = _compute_overall(results)
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"

    # TTFA values are placeholders; real values come from a ws_loopback soak run.
    # For config-only mode (no live server), we report 0.0.
    ttfa_p50_s = 0.0
    ttfa_p95_s = 0.0

    return HealthReport(
        results=results,
        overall_status=overall,
        timestamp=timestamp,
        ttfa_p50_s=ttfa_p50_s,
        ttfa_p95_s=ttfa_p95_s,
    )


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------

_STATUS_SYMBOL = {"OK": "✓", "WARN": "⚠", "FAIL": "✗"}


def print_report(report: HealthReport) -> None:
    """Prints a clean text table of the health report."""
    line = "─" * 60
    print(f"\n{'ANIMA-S3 Health Report':^60}")
    print(f"{'Timestamp: ' + report.timestamp:^60}")
    print(line)
    print(f"  {'Collector':<20} {'Status':<8} Message")
    print(line)
    for r in report.results:
        sym = _STATUS_SYMBOL.get(r.status, "?")
        print(f"  {r.name:<20} {r.status:<8} {r.message}")
        for k, v in r.metrics.items():
            print(f"    {'':20}   {k}={v:.1f}")
    print(line)

    # TTFA summary
    if report.ttfa_p50_s > 0:
        ttfa_warn = " ⚠ WARN" if report.ttfa_p50_s >= _TTFA_WARN_S else ""
        ttfa_fail = " ✗ FAIL" if report.ttfa_p50_s >= _TTFA_FAIL_S else ""
        print(
            f"  TTFA p50={report.ttfa_p50_s:.3f}s  p95={report.ttfa_p95_s:.3f}s"
            f"{ttfa_warn}{ttfa_fail}"
        )
        print(line)

    sym = _STATUS_SYMBOL.get(report.overall_status, "?")
    print(f"\n  Overall: {sym} {report.overall_status}\n")


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def diff_reports(r1: HealthReport, r2: HealthReport) -> None:
    """Prints collectors whose status or message changed between two reports."""
    r1_map = {r.name: r for r in r1.results}
    r2_map = {r.name: r for r in r2.results}

    all_names = sorted(set(r1_map) | set(r2_map))
    changed = False
    print("\nDiff: report1 vs report2")
    print("─" * 60)
    for name in all_names:
        a = r1_map.get(name)
        b = r2_map.get(name)
        if a is None:
            print(f"  + {name}: NEW → {b.status}: {b.message}")  # type: ignore[union-attr]
            changed = True
        elif b is None:
            print(f"  - {name}: REMOVED (was {a.status})")
            changed = True
        elif a.status != b.status or a.message != b.message:
            print(f"  ~ {name}: {a.status}→{b.status}  '{a.message}' → '{b.message}'")
            changed = True

    if not changed:
        print("  (no changes)")
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


async def main() -> int:
    cfg = load_config(".env")
    report = await generate_report(cfg)
    print_report(report)
    return 0 if report.overall_status in ("OK", "WARN") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))


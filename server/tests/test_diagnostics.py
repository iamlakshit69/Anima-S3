"""
server/tests/test_diagnostics.py — Unit tests for anima_check diagnostics suite.
"""

from __future__ import annotations

import pytest

from anima_server.config import Config
from anima_server.diagnostics.anima_check import (
    CollectorResult,
    ConfigCollector,
    HealthReport,
    LlmCollector,
    SttCollector,
    TtsCollector,
    WsLoopbackCollector,
    diff_reports,
    generate_report,
    print_report,
)


@pytest.mark.asyncio
async def test_config_collector_valid():
    collector = ConfigCollector(Config())
    res = await collector.run()
    assert res.status == "OK"
    assert "passed" in res.message


@pytest.mark.asyncio
async def test_config_collector_invalid():
    # frame_ms=99 is invalid per validate(cfg)
    bad_cfg = Config(frame_ms=99)
    collector = ConfigCollector(bad_cfg)
    res = await collector.run()
    assert res.status == "FAIL"
    assert "Invalid frame_ms" in res.message


@pytest.mark.asyncio
async def test_stt_collector():
    collector = SttCollector()
    res = await collector.run()
    assert res.status == "OK"
    assert "FakeWhisper" in res.message
    assert res.metrics.get("audio_samples") == 8000


@pytest.mark.asyncio
async def test_tts_collector():
    collector = TtsCollector()
    res = await collector.run()
    assert res.status == "OK"
    assert "FakeKokoro" in res.message
    assert res.metrics.get("sample_rate") == 24000


@pytest.mark.asyncio
async def test_llm_collector_no_key():
    cfg = Config(llm_api_key="")
    collector = LlmCollector(cfg)
    res = await collector.run()
    assert res.status == "WARN"
    assert "not set" in res.message


@pytest.mark.asyncio
async def test_llm_collector_with_key():
    cfg = Config(llm_api_key="gsk-dummy-key")
    collector = LlmCollector(cfg)
    res = await collector.run()
    assert res.status == "OK"


@pytest.mark.asyncio
async def test_ws_loopback_collector():
    collector = WsLoopbackCollector(Config())
    res = await collector.run()
    assert res.status == "OK"


@pytest.mark.asyncio
async def test_generate_report_overall_status():
    report = await generate_report(Config(llm_api_key="key"))
    assert report.overall_status == "OK"

    report_warn = await generate_report(Config(llm_api_key=""))
    assert report_warn.overall_status == "WARN"

    report_fail = await generate_report(Config(frame_ms=99))
    assert report_fail.overall_status == "FAIL"


def test_print_report_no_crash(capsys):
    report = HealthReport(
        results=[
            CollectorResult(name="test_col", status="OK", message="Everything fine", metrics={"val": 1.0}),
            CollectorResult(name="test_warn", status="WARN", message="Caution"),
        ],
        overall_status="WARN",
        timestamp="2026-10-29T12:00:00Z",
    )
    print_report(report)
    out = capsys.readouterr().out
    assert "ANIMA-S3 Health Report" in out
    assert "test_col" in out
    assert "Everything fine" in out
    assert "WARN" in out


def test_diff_reports(capsys):
    r1 = HealthReport(
        results=[
            CollectorResult(name="stt", status="OK", message="Good"),
            CollectorResult(name="llm", status="WARN", message="No key"),
        ],
        overall_status="WARN",
        timestamp="t1",
    )
    r2 = HealthReport(
        results=[
            CollectorResult(name="stt", status="OK", message="Good"),
            CollectorResult(name="llm", status="OK", message="Key set"),
        ],
        overall_status="OK",
        timestamp="t2",
    )
    diff_reports(r1, r2)
    out = capsys.readouterr().out
    assert "Diff: report1 vs report2" in out
    assert "llm" in out
    assert "WARN→OK" in out

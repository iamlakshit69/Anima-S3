"""
Integration tests: In-process server driven by FakeDevice across all scenarios.
"""

import asyncio
import pytest
import websockets
from anima_server.config import Config
from anima_server.models import ModelHub
from anima_server.providers.base import Done, TextDelta, ToolCall
from anima_server.transport.ws_server import WsServer
from tools.fake_device import FakeDevice, generate_synthetic_speech


class FakeLLM:
    def __init__(self, reply_text="I am doing well, thank you for asking."):
        self.reply_text = reply_text

    async def validate(self):
        pass

    async def stream(self, messages, tools, scope):
        # Yield words as tokens
        for word in self.reply_text.split():
            if scope.is_cancelled():
                break
            yield TextDelta(word + " ")
            await asyncio.sleep(0.01)
        yield Done(reason="stop")


@pytest.fixture
async def server_port():
    cfg = Config(
        host="127.0.0.1",
        port=0,  # dynamic free port
        device_tokens={"esp32s3-fake-01": "secret-test-token"},
        min_audio_ms=100,
        fixed_silence_ms=100,
        listen_timeout_ms=500,
    )
    models = await ModelHub.load(cfg, use_fakes=True)
    provider = FakeLLM()
    ws_server = WsServer(cfg, models, provider)

    server = await websockets.serve(
        ws_server.handle_connection,
        cfg.host,
        0,
        ping_interval=10,
        ping_timeout=30,
    )
    port = server.sockets[0].getsockname()[1]
    yield port
    server.close()
    await server.wait_closed()


@pytest.mark.asyncio
async def test_scenario_normal(server_port):
    url = f"ws://127.0.0.1:{server_port}/v1/device"
    dev = FakeDevice(url=url, token="secret-test-token", device_id="esp32s3-fake-01")
    await dev.connect()
    ack = await dev.handshake()
    assert ack.proto == 1

    reader = asyncio.create_task(dev.reader_loop())
    try:
        dev.turn = 1
        await dev.send_json({"type": "listen.start", "turn": 1, "reason": "wake_word"})
        pcm = generate_synthetic_speech(duration_s=0.5)
        await dev.stream_pcm_uplink(pcm, turn=1)

        # Await reply and listen_stop
        await asyncio.wait_for(dev._listen_stop_event.wait(), timeout=3.0)
        await asyncio.sleep(0.8)

        # Verify messages received
        types = [getattr(m, "type", m.get("type") if isinstance(m, dict) else None) for m in dev.received_messages]
        assert "listen.stop" in types
        assert "stt" in types
        assert "reply" in types
        assert "tts.start" in types
        assert len(dev.received_audio_frames) > 0
    finally:
        reader.cancel()
        await dev.close()


@pytest.mark.asyncio
async def test_scenario_bad_token(server_port):
    url = f"ws://127.0.0.1:{server_port}/v1/device"
    dev = FakeDevice(url=url, token="wrong-invalid-token", device_id="esp32s3-fake-01")
    await dev.connect()
    # Server closes with 4401 on unauthorized token
    with pytest.raises(websockets.exceptions.ConnectionClosed):
        await dev.handshake()


@pytest.mark.asyncio
async def test_scenario_no_speech(server_port):
    url = f"ws://127.0.0.1:{server_port}/v1/device"
    dev = FakeDevice(url=url, token="secret-test-token", device_id="esp32s3-fake-01")
    await dev.connect()
    await dev.handshake()

    reader = asyncio.create_task(dev.reader_loop())
    try:
        dev.turn = 1
        await dev.send_json({"type": "listen.start", "turn": 1, "reason": "wake_word"})
        # Send no speech; wait for server timeout (500ms)
        await asyncio.sleep(0.9)

        stop_msgs = [m for m in dev.received_messages if getattr(m, "type", None) == "listen.stop"]
        assert len(stop_msgs) >= 1
        assert getattr(stop_msgs[0], "reason", "") == "no_speech"
    finally:
        reader.cancel()
        await dev.close()


@pytest.mark.asyncio
async def test_scenario_barge_in(server_port):
    url = f"ws://127.0.0.1:{server_port}/v1/device"
    dev = FakeDevice(url=url, token="secret-test-token", device_id="esp32s3-fake-01")
    await dev.connect()
    await dev.handshake()

    reader = asyncio.create_task(dev.reader_loop())
    try:
        # Start Turn 1
        dev.turn = 1
        await dev.send_json({"type": "listen.start", "turn": 1, "reason": "wake_word"})
        pcm = generate_synthetic_speech(duration_s=0.3)
        await dev.stream_pcm_uplink(pcm, turn=1)
        await asyncio.sleep(0.3)

        # Barge-in: flush playback and start Turn 2
        await dev.send_json({"type": "playback", "turn": 1, "event": "flushed"})
        dev.turn = 2
        dev.received_audio_frames.clear()
        await dev.send_json({"type": "listen.start", "turn": 2, "reason": "barge_in"})
        pcm2 = generate_synthetic_speech(duration_s=0.4)
        await dev.stream_pcm_uplink(pcm2, turn=2)
        await asyncio.sleep(1.0)

        # All new audio frames must belong to turn 2
        for fr in dev.received_audio_frames:
            assert fr.turn == 2
    finally:
        reader.cancel()
        await dev.close()


@pytest.mark.asyncio
async def test_scenario_reconnect(server_port):
    url = f"ws://127.0.0.1:{server_port}/v1/device"
    dev = FakeDevice(url=url, token="secret-test-token", device_id="esp32s3-fake-01")
    await dev.connect()
    ack = await dev.handshake()
    assert ack.proto == 1

    reader = asyncio.create_task(dev.reader_loop())
    try:
        # Turn 1
        dev.turn = 1
        await dev.send_json({"type": "listen.start", "turn": 1, "reason": "wake_word"})
        pcm = generate_synthetic_speech(duration_s=0.4)
        await dev.stream_pcm_uplink(pcm, turn=1)
        await asyncio.sleep(0.5)

        # Simulate network failure / disconnect
        reader.cancel()
        await dev.close()
        await asyncio.sleep(0.2)

        # Reconnect with fresh handshake carrying last_turn=1
        dev2 = FakeDevice(url=url, token="secret-test-token", device_id="esp32s3-fake-01")
        dev2.last_turn = 1
        await dev2.connect()
        ack2 = await dev2.handshake()
        assert ack2.proto == 1

        reader2 = asyncio.create_task(dev2.reader_loop())
        try:
            # Turn 2
            dev2.turn = 2
            await dev2.send_json({"type": "listen.start", "turn": 2, "reason": "wake_word"})
            pcm2 = generate_synthetic_speech(duration_s=0.4)
            await dev2.stream_pcm_uplink(pcm2, turn=2)
            await asyncio.sleep(0.8)

            types = [getattr(m, "type", m.get("type") if isinstance(m, dict) else None) for m in dev2.received_messages]
            assert "listen.stop" in types
            assert "reply" in types
            assert len(dev2.received_audio_frames) > 0
            for fr in dev2.received_audio_frames:
                assert fr.turn == 2
        finally:
            reader2.cancel()
            await dev2.close()
    finally:
        pass


@pytest.mark.asyncio
async def test_scenario_disconnect_mid_stream(server_port):
    url = f"ws://127.0.0.1:{server_port}/v1/device"
    dev = FakeDevice(url=url, token="secret-test-token", device_id="esp32s3-fake-01")
    await dev.connect()
    await dev.handshake()

    reader = asyncio.create_task(dev.reader_loop())
    try:
        dev.turn = 1
        await dev.send_json({"type": "listen.start", "turn": 1, "reason": "wake_word"})
        # Send one audio packet then abruptly close
        pcm = generate_synthetic_speech(duration_s=0.1)
        # Just stream partial audio
        await dev.stream_pcm_uplink(pcm, turn=1)
    finally:
        reader.cancel()
        await dev.close()

    # Allow server to process disconnect cleanly
    await asyncio.sleep(0.3)

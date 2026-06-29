"""
网页版后端（FastAPI + WebSocket）。

职责：
- 提供前端页面（``GET /``）。
- 通过 WebSocket（``/ws``）接收浏览器麦克风采集的 16kHz/16bit PCM 音频，
  转交给转录引擎（复用 ``src.transcriber``），再把临时/最终结果回传浏览器。

这样 API Key 只保存在服务端，不会暴露到浏览器。
"""

from __future__ import annotations

import asyncio
import functools
import json
from pathlib import Path

# 即时刷新, 确保诊断日志在后台运行时也能立刻写出
print = functools.partial(print, flush=True)  # noqa: A001

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

import config
from src.notes import NoteWriter
from src.transcriber import create_transcriber

app = FastAPI(title=config.APP_TITLE)

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_notes = NoteWriter()


@app.get("/")
async def index() -> FileResponse:
    """返回前端页面。"""
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/api/config")
async def api_config() -> dict:
    """前端启动时获取当前配置（采样率、默认引擎、Key 是否就绪）。"""
    return {
        "sample_rate": config.SAMPLE_RATE,
        "engine": config.ENGINE,
        "deepgram_ready": bool(config.DEEPGRAM_API_KEY),
    }


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    """音频上行 / 转录结果下行的双向通道。"""
    await ws.accept()
    loop = asyncio.get_running_loop()
    out_queue: "asyncio.Queue[dict | None]" = asyncio.Queue()

    def push(message: dict) -> None:
        """线程安全地把消息排队发往浏览器（转录回调在后台线程）。"""
        try:
            loop.call_soon_threadsafe(out_queue.put_nowait, message)
        except RuntimeError:
            pass

    def on_final(text: str) -> None:
        print(f"[final] {text}")
        push({"type": "final", "text": text})
        _notes.append(text)

    def on_interim(text: str) -> None:
        print(f"[interim] {text}")
        push({"type": "interim", "text": text})

    def build_transcriber(sample_rate: int):
        return create_transcriber(
            on_interim=on_interim,
            on_final=on_final,
            on_error=lambda e: (print(f"[error] {e}"), push({"type": "error", "text": e})),
            on_status=lambda s: push({"type": "status", "text": s}),
            sample_rate=sample_rate,
        )

    transcriber = None  # 延迟到收到 init/engine 消息（含真实采样率）后再创建
    audio_bytes = 0

    async def sender() -> None:
        """把队列中的消息持续发给浏览器。"""
        while True:
            message = await out_queue.get()
            if message is None:
                return
            try:
                await ws.send_text(json.dumps(message, ensure_ascii=False))
            except Exception:
                return

    sender_task = asyncio.create_task(sender())

    try:
        while True:
            packet = await ws.receive()
            if packet.get("type") == "websocket.disconnect":
                break
            data = packet.get("bytes")
            if data:
                if transcriber is not None:
                    transcriber.feed(data)
                    audio_bytes += len(data)
                continue
            text = packet.get("text")
            if text:
                # 控制消息: {"action":"engine","engine":"deepgram","sample_rate":48000}
                try:
                    msg = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if msg.get("action") == "engine":
                    engine = msg.get("engine", config.ENGINE)
                    rate = int(msg.get("sample_rate") or config.SAMPLE_RATE)
                    if transcriber is not None:
                        transcriber.stop()
                    config.ENGINE = engine
                    print(f"[ws] start engine={engine} sample_rate={rate}")
                    transcriber = build_transcriber(rate)
                    transcriber.start()
    except WebSocketDisconnect:
        pass
    finally:
        print(f"[ws] closed, received {audio_bytes} audio bytes")
        if transcriber is not None:
            transcriber.stop()
        out_queue.put_nowait(None)
        await sender_task


def main() -> None:
    """以 uvicorn 启动服务。"""
    import uvicorn

    print(f"网页版已启动: http://{config.WEB_HOST}:{config.WEB_PORT}")
    uvicorn.run(app, host=config.WEB_HOST, port=config.WEB_PORT, log_level="info")


if __name__ == "__main__":
    main()

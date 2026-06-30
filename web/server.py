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
import urllib.error
import urllib.request
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
    """前端启动时获取当前配置（采样率、默认引擎、各 AI 服务商就绪状态）。"""
    providers = [
        {"id": name, "label": c["label"], "ready": bool(c["key"])}
        for name, c in config.LLM_CONFIG.items()
    ]
    return {
        "sample_rate": config.SAMPLE_RATE,
        "engine": config.ENGINE,
        "deepgram_ready": bool(config.DEEPGRAM_API_KEY),
        "llm_default": config.LLM_DEFAULT_PROVIDER,
        "llm_providers": providers,
    }


# 网页"设置"面板的字段名 -> .env 中的环境变量名(随 LLM 服务商自动派生)
_SETTINGS_FIELD_TO_ENV = {"deepgram": "DEEPGRAM_API_KEY"}
_SETTINGS_FIELD_TO_ENV.update(
    {name: f"{name.upper()}_API_KEY" for name in config.LLM_CONFIG}
)


@app.get("/api/settings")
async def api_get_settings() -> dict:
    """返回各密钥的就绪状态与掩码(不含明文), 供设置面板展示。"""
    return config.secret_status()


@app.post("/api/settings")
def api_save_settings(payload: dict) -> dict:
    """保存网页端填写的密钥到本地 .env, 并热更新(免重启)。

    安全约定:
    - 含 '•' 的值视为掩码占位符, 表示"未修改", 直接跳过, 不会覆盖原值。
    - 空字符串表示"清除该项"。
    - 仅 MANAGED_SECRETS 中的字段会被写入。
    """
    updates: dict[str, str] = {}
    for field, env_name in _SETTINGS_FIELD_TO_ENV.items():
        if field not in payload:
            continue
        value = payload.get(field)
        if value is None:
            continue
        value = str(value).strip()
        if "•" in value:  # 掩码占位符, 表示未改动
            continue
        updates[env_name] = value

    default_provider = payload.get("llm_default")
    if default_provider:
        dp = str(default_provider).strip().lower()
        if dp in config.LLM_CONFIG:
            updates["LLM_PROVIDER"] = dp

    if updates:
        config.apply_secrets(updates)
    return {"ok": True, "status": config.secret_status()}


# 单次请求携带的历史轮数上限(一问一答算 2 条), 防止上下文过长
_MAX_HISTORY_MESSAGES = 20


def _sanitize_history(history: object) -> list[dict]:
    """校验并裁剪前端传来的对话历史, 只保留合法的 user/assistant 文本消息。"""
    if not isinstance(history, list):
        return []
    cleaned: list[dict] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            cleaned.append({"role": role, "content": content})
    return cleaned[-_MAX_HISTORY_MESSAGES:]


def _call_llm(
    provider: str, question: str, mode: str, history: list[dict] | None = None
) -> tuple[str | None, str | None]:
    """
    调用指定服务商的 OpenAI 兼容 Chat Completions 接口回答问题(支持多轮上下文)。

    @param provider "openai" / "deepseek" / "gemini" / "groq"。
    @param question 用户(转录得到)的问题。
    @param mode "detailed"=详细 / "concise"=简略。
    @param history 之前的对话历史(user/assistant 交替), 用于连续追问。
    @return (answer, error)。成功时 error 为 None。
    """
    conf = config.LLM_CONFIG.get(provider)
    if conf is None:
        return None, f"未知的 AI 服务商: {provider}"
    if not conf["key"]:
        env_name = provider.upper() + "_API_KEY"
        return None, f"未配置 {env_name}，请在 .env 填入后重启服务。"

    style = (
        "请给出详细、有条理的解释，分点说明，必要时举例。"
        if mode == "detailed"
        else "请用简洁的方式回答，直接给出要点，不要冗长。"
    )
    system_prompt = (
        "你是一个乐于助人的助手。用与问题相同的语言回答。"
        "这是一段连续对话，请结合上文理解用户的追问。" + style
    )
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": question})
    body = json.dumps(
        {
            "model": conf["model"],
            "messages": messages,
            "temperature": 0.5,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        conf["base_url"].rstrip("/") + "/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {conf['key']}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip(), None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:200] if exc.fp else ""
        return None, f"{conf['label']} 请求失败 ({exc.code})。{detail}"
    except Exception as exc:  # 网络/解析等
        return None, f"{conf['label']} 请求出错: {exc}"


@app.post("/api/ask")
def api_ask(payload: dict) -> dict:
    """把问题发给所选 AI 服务商并返回回答(支持多轮上下文)。"""
    question = (payload.get("question") or "").strip()
    mode = payload.get("mode", "concise")
    provider = (payload.get("provider") or config.LLM_DEFAULT_PROVIDER).strip().lower()
    history = _sanitize_history(payload.get("history"))
    if not question:
        return {"error": "问题为空，请先录入内容。"}
    answer, error = _call_llm(provider, question, mode, history)
    if error:
        return {"error": error}
    return {"answer": answer, "provider": provider}


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


def _maybe_open_browser(url: str) -> None:
    """由 start.bat 设置 VTT_OPEN_BROWSER=1 时, 稍候自动打开浏览器。

    延迟一点点等服务端口就绪, 避免浏览器先打开导致首次加载失败。
    """
    import os
    import threading
    import webbrowser

    if os.environ.get("VTT_OPEN_BROWSER") != "1":
        return
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()


def main() -> None:
    """以 uvicorn 启动服务。"""
    import uvicorn

    # 浏览器里用 localhost 访问; 监听地址若是 0.0.0.0 也回退到 localhost
    host = "127.0.0.1" if config.WEB_HOST in ("0.0.0.0", "") else config.WEB_HOST
    url = f"http://{host}:{config.WEB_PORT}"
    print(f"网页版已启动: {url}")
    _maybe_open_browser(url)
    uvicorn.run(app, host=config.WEB_HOST, port=config.WEB_PORT, log_level="info")


if __name__ == "__main__":
    main()

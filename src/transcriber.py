"""
流式转录模块。

定义统一的 ``Transcriber`` 抽象接口，并提供基于 Deepgram 流式 WebSocket 的实现
``DeepgramTranscriber``。直接使用 ``websockets`` 连接，避免对易变的官方 SDK 版本产生依赖。

线程模型：转录在后台线程里跑一个独立的 asyncio 事件循环。
- 发送：``feed()`` 把 PCM 字节投递进 asyncio 队列，发送协程取出后通过 WebSocket 上送。
- 接收：接收协程解析 JSON 转录结果，按"临时/最终"分别回调。
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional
from urllib.parse import urlencode

import websockets

import config

# 回调类型别名
TextCallback = Callable[[str], None]
ErrorCallback = Callable[[str], None]


class Transcriber(ABC):
    """转录引擎抽象接口。便于未来替换为本地引擎（如 faster-whisper）。"""

    @abstractmethod
    def start(self) -> None:
        """启动引擎，建立连接并准备接收音频。"""

    @abstractmethod
    def stop(self) -> None:
        """停止引擎并释放资源。"""

    @abstractmethod
    def feed(self, pcm: bytes) -> None:
        """喂入一块 16bit PCM 音频字节。"""


class DeepgramTranscriber(Transcriber):
    """基于 Deepgram 流式 WebSocket 的转录实现。"""

    _DG_URL = "wss://api.deepgram.com/v1/listen"

    def __init__(
        self,
        api_key: str,
        on_interim: TextCallback,
        on_final: TextCallback,
        on_error: Optional[ErrorCallback] = None,
        on_status: Optional[TextCallback] = None,
        sample_rate: Optional[int] = None,
    ) -> None:
        """
        @param api_key Deepgram API Key。
        @param on_interim 收到临时（未定稿）转录文本时回调。
        @param on_final 收到最终（定稿）转录文本时回调。
        @param on_error 发生错误时回调（可选）。
        @param on_status 连接状态变化时回调，如 "connected"/"closed"（可选）。
        @param sample_rate 输入音频采样率；留空用 config.SAMPLE_RATE。
               让 Deepgram 服务端做高质量重采样，避免前端粗降采样损伤(尤其中文)。
        """
        self._api_key = api_key
        self._on_interim = on_interim
        self._on_final = on_final
        self._on_error = on_error or (lambda msg: None)
        self._on_status = on_status or (lambda msg: None)
        self._sample_rate = sample_rate or config.SAMPLE_RATE

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._queue: Optional[asyncio.Queue] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._running = False
        # 当前这句话已确认(is_final)的片段累积，等 speech_final 才整句定稿
        self._utterance = ""
        # 当前累积片段所属说话人(diarize 开启时)
        self._cur_speaker: Optional[int] = None

    # ---- 公共接口 ----

    def start(self) -> None:
        """在后台线程启动 asyncio 事件循环并连接 Deepgram。"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止转录：通知发送协程结束并等待后台线程退出。"""
        if not self._running:
            return
        self._running = False
        loop = self._loop
        if loop is not None and self._queue is not None:
            # 投递哨兵 None，触发发送协程优雅关闭
            loop.call_soon_threadsafe(self._queue.put_nowait, None)
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        self._thread = None
        self._loop = None

    def feed(self, pcm: bytes) -> None:
        """把一块 PCM 字节投递到发送队列（线程安全）。"""
        loop = self._loop
        queue = self._queue
        if not self._running or loop is None or queue is None:
            return
        loop.call_soon_threadsafe(queue.put_nowait, pcm)

    # ---- 内部实现 ----

    def _build_url(self) -> str:
        """组装带查询参数的 Deepgram 流式 URL。"""
        params = {
            "model": config.DG_MODEL,
            "language": config.DG_LANGUAGE,
            "encoding": "linear16",
            "sample_rate": self._sample_rate,
            "channels": config.CHANNELS,
            "endpointing": config.DG_ENDPOINTING,
            "interim_results": str(config.DG_INTERIM_RESULTS).lower(),
            "smart_format": str(config.DG_SMART_FORMAT).lower(),
            "diarize": str(config.DG_DIARIZE).lower(),
            # 间隙断句: Deepgram 会在静默超过该时长时发 UtteranceEnd 事件
            "utterance_end_ms": config.DG_UTTERANCE_END_MS,
        }
        # keyterm 仅在非空时附加(Nova-3 传空会导致 400)。doseq 让列表展开为多个同名参数。
        if config.DG_KEYTERMS:
            params["keyterm"] = config.DG_KEYTERMS
        return f"{self._DG_URL}?{urlencode(params, doseq=True)}"

    def _thread_main(self) -> None:
        """后台线程入口：创建并运行事件循环。"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._queue = asyncio.Queue()
        self._stop_event = asyncio.Event()
        try:
            self._loop.run_until_complete(self._run())
        except Exception as exc:  # 兜底，避免线程静默崩溃
            self._on_error(f"转录线程异常: {exc}")
        finally:
            self._loop.close()

    async def _run(self) -> None:
        """建立 WebSocket 连接并并发跑收发协程。"""
        url = self._build_url()
        try:
            # Deepgram 支持通过子协议传递鉴权：["token", <API_KEY>]，避免不同
            # websockets 版本中 header 参数命名差异带来的兼容问题。
            async with websockets.connect(
                url,
                subprotocols=["token", self._api_key],
                max_size=None,
            ) as ws:
                self._on_status("connected")
                sender = asyncio.create_task(self._send_loop(ws))
                receiver = asyncio.create_task(self._recv_loop(ws))
                await asyncio.wait(
                    {sender, receiver}, return_when=asyncio.FIRST_COMPLETED
                )
                for task in (sender, receiver):
                    if not task.done():
                        task.cancel()
        except Exception as exc:
            self._on_error(f"连接失败: {exc}")
        finally:
            self._on_status("closed")

    async def _send_loop(self, ws) -> None:
        """从队列取 PCM 并发送；取到 None 时关闭流。"""
        assert self._queue is not None
        while True:
            chunk = await self._queue.get()
            if chunk is None:
                # 通知 Deepgram 关闭音频流以拿到最后的最终结果
                try:
                    await ws.send(json.dumps({"type": "CloseStream"}))
                except Exception:
                    pass
                return
            try:
                await ws.send(chunk)
            except Exception as exc:
                self._on_error(f"发送音频失败: {exc}")
                return

    async def _recv_loop(self, ws) -> None:
        """接收并解析转录结果，按临时/最终分发。"""
        try:
            async for message in ws:
                self._handle_message(message)
        except websockets.ConnectionClosed:
            pass
        except Exception as exc:
            self._on_error(f"接收结果失败: {exc}")
        finally:
            self._flush()

    # 句末标点：长语音中即使没有停顿，也按句子分行
    _SENTENCE_END = ".?!。？！…"

    @staticmethod
    def _speaker_of(alt: dict) -> Optional[int]:
        """从词级结果中取该片段的主要说话人编号(diarize 开启时)。"""
        words = alt.get("words") or []
        speakers = [w["speaker"] for w in words if w.get("speaker") is not None]
        if not speakers:
            return None
        return max(set(speakers), key=speakers.count)

    def _prefix(self, text: str, speaker: Optional[int]) -> str:
        """给文本加说话人前缀(仅在 diarize 且有说话人时)。"""
        if config.DG_DIARIZE and speaker is not None:
            return f"说话人{speaker + 1}：{text}"
        return text

    def _handle_message(self, message: str) -> None:
        """
        解析单条 Deepgram JSON 消息。

        分行规则(满足任一即把当前累积内容定稿成一行)：
        - ``speech_final``：检测到停顿/端点；
        - 句末标点结尾：长语音无停顿时按句子切分；
        - ``UtteranceEnd`` 事件：静默间隙超过 utterance_end_ms；
        - 说话人切换：不同人说话时分行(diarize 开启)。
        """
        try:
            data = json.loads(message)
        except (json.JSONDecodeError, TypeError):
            return

        mtype = data.get("type")
        if mtype == "UtteranceEnd":
            # 间隙断句：把当前累积内容定稿
            self._flush()
            return
        if mtype != "Results":
            return
        try:
            alt = data["channel"]["alternatives"][0]
            transcript = alt.get("transcript", "")
        except (KeyError, IndexError):
            return

        is_final = bool(data.get("is_final"))
        speech_final = bool(data.get("speech_final"))
        speaker = self._speaker_of(alt)

        if not is_final:
            if transcript:
                # 临时预览不加说话人前缀: diarize 在流式下编号会反复变动,
                # 加前缀会造成 说话人1<->说话人2 视觉闪烁。前缀只在整句定稿时确定。
                preview = (self._utterance + " " + transcript).strip()
                self._on_interim(preview)
            return

        if not transcript:
            # 空的 is_final：可能只是确认端点
            if speech_final:
                self._flush()
            return

        # 说话人切换：先把上一个人的内容定稿，再开新的一行
        if (
            config.DG_DIARIZE
            and speaker is not None
            and self._cur_speaker is not None
            and speaker != self._cur_speaker
            and self._utterance
        ):
            self._flush()
        if speaker is not None:
            self._cur_speaker = speaker

        self._utterance = (self._utterance + " " + transcript).strip()

        ends_sentence = self._utterance[-1] in self._SENTENCE_END
        if speech_final or ends_sentence:
            self._flush()
        else:
            # 已确认片段也以无前缀的预览形式展示, 定稿时再补说话人
            self._on_interim(self._utterance)

    def _flush(self) -> None:
        """把当前累积的整句作为一行输出，并重置状态。"""
        if self._utterance:
            self._on_final(self._prefix(self._utterance, self._cur_speaker))
        self._utterance = ""
        self._cur_speaker = None


class LocalWhisperTranscriber(Transcriber):
    """
    本地离线转录实现（faster-whisper），无需任何 API Key / 联网。

    由于 Whisper 本身不是天然流式，这里用"能量 VAD 分句 + 滚动缓冲"模拟实时：
    - 持续累积当前句子的音频；检测到说话则刷新"最后有声时间"。
    - 后台 worker 定期对当前缓冲做一次快速转写，发出临时(灰色)结果。
    - 当静音超过阈值时，对整句做一次较准的转写，发出最终结果并清空缓冲。

    说明：要达到接近 1 秒的延迟且准确，建议使用 NVIDIA 显卡；纯 CPU 会偏慢。
    """

    def __init__(
        self,
        on_interim: TextCallback,
        on_final: TextCallback,
        on_error: Optional[ErrorCallback] = None,
        on_status: Optional[TextCallback] = None,
        sample_rate: Optional[int] = None,
    ) -> None:
        self._on_interim = on_interim
        self._on_final = on_final
        self._on_error = on_error or (lambda msg: None)
        self._on_status = on_status or (lambda msg: None)
        # Whisper 固定按 16kHz 处理；输入若非 16k 在转写前重采样。
        self._input_rate = sample_rate or config.SAMPLE_RATE

        self._model = None
        self._queue: "queue.Queue[Optional[bytes]]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = False

    # ---- 公共接口 ----

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._queue.put(None)  # 唤醒并触发收尾
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._thread = None

    def feed(self, pcm: bytes) -> None:
        if self._running:
            self._queue.put(pcm)

    # ---- 内部实现 ----

    def _ensure_model(self) -> bool:
        """懒加载 faster-whisper 模型；失败时回调错误并返回 False。"""
        if self._model is not None:
            return True
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            self._on_error(
                "未安装 faster-whisper，请运行: pip install faster-whisper"
            )
            return False
        try:
            self._on_status("loading")
            self._model = WhisperModel(
                config.WHISPER_MODEL,
                device=config.WHISPER_DEVICE,
                compute_type=config.WHISPER_COMPUTE_TYPE,
            )
            return True
        except Exception as exc:
            self._on_error(f"加载本地模型失败: {exc}")
            return False

    @staticmethod
    def _rms(pcm: bytes) -> float:
        """计算一块 int16 PCM 的均方根能量，用于简单 VAD。"""
        import numpy as np

        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        if samples.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples * samples)))

    def _transcribe(self, pcm: bytes, accurate: bool) -> str:
        """对一段 PCM 做转写，返回拼接文本。"""
        import numpy as np

        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        if self._input_rate != 16000 and audio.size > 0:
            n = int(round(audio.size * 16000 / self._input_rate))
            if n > 0:
                x_old = np.linspace(0.0, 1.0, audio.size, endpoint=False)
                x_new = np.linspace(0.0, 1.0, n, endpoint=False)
                audio = np.interp(x_new, x_old, audio).astype(np.float32)
        segments, _ = self._model.transcribe(
            audio,
            language=config.WHISPER_LANGUAGE,
            beam_size=5 if accurate else 1,
            vad_filter=False,
        )
        return "".join(seg.text for seg in segments).strip()

    def _worker(self) -> None:
        """后台线程：消费音频、做 VAD 分句、产出临时/最终结果。"""
        if not self._ensure_model():
            self._running = False
            return
        self._on_status("connected")

        bytes_per_sec = self._input_rate * 2  # int16 单声道
        buffer = bytearray()
        last_voice = time.monotonic()
        last_interim = 0.0
        has_speech = False

        def flush_final() -> None:
            nonlocal buffer, has_speech
            if buffer and has_speech:
                try:
                    text = self._transcribe(bytes(buffer), accurate=True)
                    if text:
                        self._on_final(text)
                except Exception as exc:
                    self._on_error(f"本地转写失败: {exc}")
            buffer = bytearray()
            has_speech = False

        while self._running:
            try:
                chunk = self._queue.get(timeout=0.1)
            except queue.Empty:
                chunk = b""

            if chunk is None:  # 停止信号：收尾最后一句
                flush_final()
                break

            now = time.monotonic()
            if chunk:
                if self._rms(chunk) >= config.VAD_SILENCE_RMS:
                    has_speech = True
                    last_voice = now
                buffer.extend(chunk)
                # 防止缓冲无限增长（最长约 30 秒）
                if len(buffer) > bytes_per_sec * 30:
                    flush_final()
                    last_voice = now

            # 静音超过阈值 -> 定稿
            if has_speech and (now - last_voice) >= config.VAD_SILENCE_SECONDS:
                flush_final()
                continue

            # 定期产出临时结果
            if (
                has_speech
                and buffer
                and (now - last_interim) >= config.LOCAL_INTERIM_INTERVAL
            ):
                last_interim = now
                try:
                    text = self._transcribe(bytes(buffer), accurate=False)
                    if text:
                        self._on_interim(text)
                except Exception as exc:
                    self._on_error(f"本地转写失败: {exc}")

        self._on_status("closed")


def create_transcriber(
    on_interim: TextCallback,
    on_final: TextCallback,
    on_error: Optional[ErrorCallback] = None,
    on_status: Optional[TextCallback] = None,
    sample_rate: Optional[int] = None,
) -> Transcriber:
    """
    根据 ``config.ENGINE`` 创建对应的转录引擎。

    @param sample_rate 输入音频采样率（如浏览器原生 48000）；留空用默认值。
    @return ENGINE=="local" 时返回本地 faster-whisper 引擎，否则返回 Deepgram 引擎。
    """
    if config.ENGINE == "local":
        return LocalWhisperTranscriber(
            on_interim, on_final, on_error, on_status, sample_rate=sample_rate
        )
    return DeepgramTranscriber(
        api_key=config.DEEPGRAM_API_KEY,
        on_interim=on_interim,
        on_final=on_final,
        on_error=on_error,
        on_status=on_status,
        sample_rate=sample_rate,
    )

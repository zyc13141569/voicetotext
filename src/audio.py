"""
麦克风采集模块。

使用 sounddevice 以 16kHz / 单声道 / 16bit PCM 持续采集音频，
并通过回调把原始 PCM 字节推送出去（交给转录引擎）。
"""

from __future__ import annotations

from typing import Callable, Optional

import sounddevice as sd

import config


class AudioCapture:
    """
    封装麦克风采集。

    采集到的每个音频块会以 bytes 形式回调给 ``on_chunk``，
    字节格式为 16bit 小端 PCM（linear16），与 Deepgram 流式要求一致。
    """

    def __init__(self, on_chunk: Callable[[bytes], None]) -> None:
        """
        @param on_chunk 接收 PCM 字节块的回调；在 sounddevice 的音频线程中被调用。
        """
        self._on_chunk = on_chunk
        self._stream: Optional[sd.RawInputStream] = None

    def _callback(self, indata, frames, time_info, status) -> None:
        """sounddevice 音频线程回调，将原始字节转发出去。"""
        if status:
            # 仅打印警告（如缓冲区溢出），不中断采集
            print(f"[audio] 状态警告: {status}")
        self._on_chunk(bytes(indata))

    def start(self) -> None:
        """开始采集。重复调用安全（已在运行则忽略）。"""
        if self._stream is not None:
            return
        self._stream = sd.RawInputStream(
            samplerate=config.SAMPLE_RATE,
            blocksize=config.BLOCKSIZE,
            channels=config.CHANNELS,
            dtype="int16",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        """停止采集并释放设备。重复调用安全。"""
        if self._stream is None:
            return
        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None

    @property
    def is_running(self) -> bool:
        """是否正在采集。"""
        return self._stream is not None

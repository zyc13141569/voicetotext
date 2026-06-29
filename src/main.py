"""
程序入口与总装配。

把各模块串起来：
    麦克风(audio) -> 转录(transcriber) -> 悬浮窗(overlay) / 笔记(notes)
并通过全局热键(hotkey)与按钮切换"监听 / 待机"。

线程边界：
- 音频采集回调在 sounddevice 线程；
- 转录结果回调在 transcriber 的 asyncio 线程；
- 热键回调在 pynput 线程；
- 所有触达 UI 的操作都经由 Qt 信号转发到主线程执行。
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

import config
from src.audio import AudioCapture
from src.hotkey import GlobalHotkey
from src.notes import NoteWriter
from src.overlay import OverlayWindow
from src.transcriber import create_transcriber


class AppController(QObject):
    """协调音频、转录、UI 与笔记的控制器。"""

    # 用于把"切换监听"请求从任意线程安全地转回主线程
    _sig_toggle = Signal()
    # 切换转录引擎请求（参数为引擎标识）
    _sig_engine = Signal(str)

    def __init__(self, overlay: OverlayWindow, notes: NoteWriter) -> None:
        super().__init__()
        self._overlay = overlay
        self._notes = notes
        self._listening = False

        self._audio = AudioCapture(self._on_chunk)
        self._transcriber = create_transcriber(
            on_interim=self._on_interim,
            on_final=self._on_final,
            on_error=self._on_error,
            on_status=self._on_status,
        )

        self._sig_toggle.connect(self._do_toggle)
        self._sig_engine.connect(self._do_set_engine)

    # ---- 切换监听（线程安全入口） ----

    def request_toggle(self) -> None:
        """从任意线程请求切换监听状态。"""
        self._sig_toggle.emit()

    def _do_toggle(self) -> None:
        if self._listening:
            self._stop_listening()
        else:
            self._start_listening()

    def _start_listening(self) -> None:
        self._listening = True
        self._overlay.sig_status.emit("listening")
        self._transcriber.start()
        self._audio.start()

    def _stop_listening(self) -> None:
        self._listening = False
        self._audio.stop()
        self._transcriber.stop()
        self._overlay.sig_status.emit("idle")

    # ---- 切换引擎（线程安全入口） ----

    def request_set_engine(self, engine: str) -> None:
        """从任意线程请求切换转录引擎。"""
        self._sig_engine.emit(engine)

    def _do_set_engine(self, engine: str) -> None:
        if engine == config.ENGINE and self._transcriber is not None:
            return
        was_listening = self._listening
        if was_listening:
            self._stop_listening()
        config.ENGINE = engine
        self._transcriber = create_transcriber(
            on_interim=self._on_interim,
            on_final=self._on_final,
            on_error=self._on_error,
            on_status=self._on_status,
        )
        if was_listening:
            self._start_listening()

    def shutdown(self) -> None:
        """退出前清理资源。"""
        if self._listening:
            self._stop_listening()

    # ---- 回调（来自后台线程，均通过信号回到主线程） ----

    def _on_chunk(self, pcm: bytes) -> None:
        self._transcriber.feed(pcm)

    def _on_interim(self, text: str) -> None:
        self._overlay.sig_interim.emit(text)

    def _on_final(self, text: str) -> None:
        self._overlay.sig_final.emit(text)
        self._notes.append(text)

    def _on_error(self, message: str) -> None:
        print(f"[error] {message}")
        self._overlay.sig_status.emit(f"error:{message}")

    def _on_status(self, status: str) -> None:
        # 仅在监听中转发状态，避免覆盖待机提示
        if not self._listening:
            return
        if status == "connected":
            self._overlay.sig_status.emit("connected")
        elif status == "loading":
            self._overlay.sig_status.emit("error:正在加载本地模型...")


def main() -> int:
    app = QApplication(sys.argv)

    overlay = OverlayWindow()
    notes = NoteWriter()
    controller = AppController(overlay, notes)

    overlay.set_toggle_callback(controller.request_toggle)
    overlay.set_engine_callback(controller.request_set_engine)

    hotkey = GlobalHotkey(controller.request_toggle)
    hotkey.start()

    app.aboutToQuit.connect(controller.shutdown)
    app.aboutToQuit.connect(hotkey.stop)

    overlay.bring_to_front()

    if config.ENGINE != "local" and not config.DEEPGRAM_API_KEY:
        QMessageBox.warning(
            overlay,
            config.APP_TITLE,
            "未检测到 DEEPGRAM_API_KEY。\n\n"
            "方案一: 把 .env.example 复制为 .env 并填入 Deepgram API Key。\n"
            "方案二: 改用本地离线引擎, 在 .env 中设置 TRANSCRIBER_ENGINE=local "
            "(需先 pip install faster-whisper)。",
        )

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

"""
全局热键模块（pynput）。

在后台监听系统级热键（默认 Ctrl+Alt+Space），任意窗口下都能触发，
用于切换"监听 / 待机"。回调可能在 pynput 的监听线程中被调用，
上层需注意线程安全（本项目通过 Qt 信号转发到主线程）。
"""

from __future__ import annotations

from typing import Callable, Optional

from pynput import keyboard

import config


class GlobalHotkey:
    """封装一个全局热键到回调的绑定。"""

    def __init__(self, on_toggle: Callable[[], None]) -> None:
        """
        @param on_toggle 热键触发时调用的回调（无参）。
        """
        self._on_toggle = on_toggle
        self._listener: Optional[keyboard.GlobalHotKeys] = None

    def start(self) -> None:
        """开始监听全局热键。"""
        if self._listener is not None:
            return
        self._listener = keyboard.GlobalHotKeys(
            {config.HOTKEY_TOGGLE: self._safe_toggle}
        )
        self._listener.start()

    def stop(self) -> None:
        """停止监听。"""
        if self._listener is None:
            return
        self._listener.stop()
        self._listener = None

    def _safe_toggle(self) -> None:
        """包一层异常处理，避免回调异常导致监听线程崩溃。"""
        try:
            self._on_toggle()
        except Exception as exc:
            print(f"[hotkey] 回调异常: {exc}")

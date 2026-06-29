"""
桌面悬浮窗 UI（PySide6）。

无边框、置顶、半透明、可鼠标拖动。实时显示转录文本：
- 最终（定稿）文本：正常颜色，逐句累积。
- 临时（未定稿）文本：灰色，跟在最终文本后面，随时被刷新。

跨线程更新：对外暴露 Qt 信号（``sig_interim`` / ``sig_final`` / ``sig_status``），
后台线程可直接 ``emit``，Qt 会自动把更新排队到 UI 主线程执行，保证线程安全。
"""

from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import config


class OverlayWindow(QWidget):
    """悬浮主窗口。"""

    # 跨线程安全的更新信号
    sig_interim = Signal(str)
    sig_final = Signal(str)
    sig_status = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._finals: List[str] = []
        self._interim: str = ""
        self._drag_pos = None
        self._toggle_callback: Optional[Callable[[], None]] = None
        self._engine_callback: Optional[Callable[[str], None]] = None

        self._build_ui()
        self._connect_signals()
        self._set_listening(False)

    # ---- 对外接口 ----

    def set_toggle_callback(self, callback: Callable[[], None]) -> None:
        """设置"开始/停止"按钮被点击时的回调。"""
        self._toggle_callback = callback

    def set_engine_callback(self, callback: Callable[[str], None]) -> None:
        """设置引擎下拉切换时的回调，参数为引擎标识('deepgram'/'local')。"""
        self._engine_callback = callback

    def session_text(self) -> str:
        """返回当前会话已定稿的全部文本。"""
        return " ".join(self._finals).strip()

    def _move_to_visible_spot(self) -> None:
        """把窗口放到主屏幕中上方，避免出现在看不到的角落。"""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + max(40, geo.height() // 6)
        self.move(x, y)

    def bring_to_front(self) -> None:
        """显示并把窗口提到最前、获取焦点。"""
        self.show()
        self.raise_()
        self.activateWindow()

    # ---- UI 构建 ----

    def _build_ui(self) -> None:
        self.setWindowTitle(config.APP_TITLE)
        # 不使用 Qt.Tool, 以便在任务栏出现, 方便找到/切换窗口
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(420, 240)
        self._move_to_visible_spot()

        root = QWidget(self)
        root.setObjectName("root")
        root.setStyleSheet(
            """
            #root {
                background-color: rgba(28, 28, 32, 235);
                border-radius: 14px;
            }
            QLabel#title { color: #e8e8ea; font-size: 13px; font-weight: 600; }
            QLabel#status { color: #b0b0b6; font-size: 12px; }
            QTextEdit {
                background-color: rgba(255, 255, 255, 16);
                border: none; border-radius: 8px;
                color: #f2f2f4; font-size: 15px; padding: 8px;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 26);
                color: #e8e8ea; border: none; border-radius: 8px;
                padding: 6px 12px; font-size: 12px;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 46); }
            QComboBox {
                background-color: rgba(255, 255, 255, 26);
                color: #e8e8ea; border: none; border-radius: 8px;
                padding: 6px 10px; font-size: 12px;
            }
            QComboBox:hover { background-color: rgba(255, 255, 255, 46); }
            QComboBox QAbstractItemView {
                background-color: #2a2a30; color: #e8e8ea;
                selection-background-color: #2f6fed; outline: none;
            }
            QPushButton#toggle {
                background-color: #2f6fed; color: white;
                font-size: 15px; font-weight: 600;
            }
            QPushButton#toggle:hover { background-color: #3f7ff5; }
            QPushButton#toggle[listening="true"] { background-color: #e0483d; }
            QPushButton#toggle[listening="true"]:hover { background-color: #f0584d; }
            """
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # 顶部：标题 + 状态
        top = QHBoxLayout()
        title = QLabel(config.APP_TITLE, objectName="title")
        self._status_label = QLabel("", objectName="status")
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self._status_label)
        layout.addLayout(top)

        # 中部：文本显示
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        layout.addWidget(self._text, 1)

        # 主控制：独占一行的大按钮，点击开始 / 结束
        self._toggle_btn = QPushButton("\u25b6 \u5f00\u59cb", objectName="toggle")  # ▶ 开始
        self._toggle_btn.setMinimumHeight(44)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._on_toggle_clicked)
        layout.addWidget(self._toggle_btn)

        # 次级操作：引擎切换 + 复制 / 清空 / 关闭
        bottom = QHBoxLayout()
        self._engine_combo = QComboBox()
        self._engine_combo.setCursor(Qt.PointingHandCursor)
        # (显示文本, 引擎标识)
        self._engine_combo.addItem("\u2601 \u4e91\u7aef Deepgram", "deepgram")  # ☁ 云端
        self._engine_combo.addItem("\U0001f4bb \u672c\u5730\u79bb\u7ebf", "local")  # 💻 本地
        idx = self._engine_combo.findData(config.ENGINE)
        if idx >= 0:
            self._engine_combo.setCurrentIndex(idx)
        self._engine_combo.currentIndexChanged.connect(self._on_engine_changed)

        copy_btn = QPushButton("复制")
        copy_btn.clicked.connect(self._on_copy)
        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._on_clear)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(QApplication.quit)
        for btn in (copy_btn, clear_btn, close_btn):
            btn.setCursor(Qt.PointingHandCursor)
        bottom.addWidget(self._engine_combo)
        bottom.addStretch(1)
        bottom.addWidget(copy_btn)
        bottom.addWidget(clear_btn)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def _connect_signals(self) -> None:
        self.sig_interim.connect(self._update_interim)
        self.sig_final.connect(self._append_final)
        self.sig_status.connect(self._update_status)

    # ---- 槽函数（均在 UI 主线程执行） ----

    def _append_final(self, text: str) -> None:
        text = text.strip()
        if text:
            self._finals.append(text)
        self._interim = ""
        self._render()

    def _update_interim(self, text: str) -> None:
        self._interim = text
        self._render()

    def _update_status(self, status: str) -> None:
        if status == "listening":
            self._set_listening(True)
        elif status in ("idle", "closed"):
            self._set_listening(False)
        elif status == "connected":
            self._status_label.setText("\u25cf \u8fde\u63a5\u6210\u529f")  # ● 连接成功
        elif status.startswith("error:"):
            self._status_label.setText("\u26a0 " + status[6:])

    def _set_listening(self, listening: bool) -> None:
        if listening:
            self._status_label.setText("\u25cf \u76d1\u542c\u4e2d")  # ● 监听中
            self._toggle_btn.setText("\u25a0 \u7ed3\u675f")  # ■ 结束
            self._toggle_btn.setProperty("listening", True)
        else:
            hint = config.HOTKEY_TOGGLE.replace("<", "").replace(">", "")
            self._status_label.setText(f"\u25cb \u5f85\u673a  ({hint})")  # ○ 待机
            self._toggle_btn.setText("\u25b6 \u5f00\u59cb")  # ▶ 开始
            self._toggle_btn.setProperty("listening", False)
        # 切换属性后需重新应用样式表
        self._toggle_btn.style().unpolish(self._toggle_btn)
        self._toggle_btn.style().polish(self._toggle_btn)

    # ---- 渲染 ----

    def _render(self) -> None:
        """把最终文本（正常色）与临时文本（灰色）拼成 HTML 显示。"""
        final_html = " ".join(self._finals)
        if self._interim:
            interim_html = f'<span style="color:#9a9aa0;">{self._interim}</span>'
            body = (final_html + " " + interim_html).strip()
        else:
            body = final_html
        self._text.setHtml(
            f'<div style="line-height:1.5;">{body}</div>'
        )
        # 滚动到底部
        sb = self._text.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ---- 按钮 ----

    def _on_toggle_clicked(self) -> None:
        if self._toggle_callback is not None:
            self._toggle_callback()

    def _on_engine_changed(self, _index: int) -> None:
        if self._engine_callback is not None:
            engine = self._engine_combo.currentData()
            self._engine_callback(engine)

    def _on_copy(self) -> None:
        QGuiApplication.clipboard().setText(self.session_text())

    def _on_clear(self) -> None:
        self._finals.clear()
        self._interim = ""
        self._render()

    # ---- 鼠标拖动 ----

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None

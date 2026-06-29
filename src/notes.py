"""
笔记保存模块。

把最终（定稿）的转录句子按天追加到 ``notes/YYYY-MM-DD.md``。
每条记录带时间戳，方便回溯。
"""

from __future__ import annotations

from datetime import datetime

import config


class NoteWriter:
    """按天归档的 Markdown 笔记写入器。"""

    def __init__(self) -> None:
        config.NOTES_DIR.mkdir(parents=True, exist_ok=True)
        self._current_date: str = ""

    def _file_path(self, now: datetime):
        """返回当天笔记文件路径，并在新的一天写入标题。"""
        date_str = now.strftime("%Y-%m-%d")
        path = config.NOTES_DIR / f"{date_str}.md"
        if not path.exists():
            path.write_text(f"# {date_str} 语音笔记\n\n", encoding="utf-8")
        return path

    def append(self, text: str) -> None:
        """
        追加一条定稿文本到当天笔记。

        @param text 要保存的文本（空白文本将被忽略）。
        """
        text = text.strip()
        if not text:
            return
        now = datetime.now()
        path = self._file_path(now)
        line = f"- {now.strftime('%H:%M:%S')}  {text}\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(line)

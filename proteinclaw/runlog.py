from __future__ import annotations

from pathlib import Path

from proteinclaw.utils import utc_now


class MarkdownRunLogger:
    def __init__(self, path: Path, title: str) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(f"# {title}\n\n", encoding="utf-8")

    def section(self, title: str) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"## {title}\n\n")

    def text(self, text: str) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"{text}\n\n")

    def event(self, text: str) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"- `{utc_now()}` {text}\n")


from __future__ import annotations

from dataclasses import dataclass

from ui.notify import NotifyMessage, parse_notify
from ui.windows import WinInfo, fill_input, find_notify, restore_if_needed, screenshot_region


@dataclass(frozen=True)
class PlatformSpec:
    key: str
    process: str
    window_title_contains: str
    notify_title: str
    input_rel_x: float
    input_rel_y: float


class PlatformAdapter:
    def __init__(self, spec: PlatformSpec) -> None:
        self.spec = spec

    def chat_window(self) -> WinInfo:
        win = restore_if_needed(self.spec.process, self.spec.window_title_contains)
        if win is None:
            raise RuntimeError(f"window not found: {self.spec.process} / {self.spec.window_title_contains}")
        return win

    def notify_window(self) -> WinInfo | None:
        if self.spec.key == "qianniu":
            return find_notify(title_equals=self.spec.notify_title)
        return find_notify(title_startswith=self.spec.notify_title)

    def read_notify(self) -> NotifyMessage | None:
        return parse_notify(self.spec.key, self.spec.notify_title, self.notify_window())

    def fill_draft(self, text: str, screenshot_path=None) -> WinInfo:
        win = self.chat_window()
        from pathlib import Path

        import yaml

        root = Path(__file__).resolve().parent.parent
        cfg = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8")) or {}
        fill_input(
            win,
            self.spec.input_rel_x,
            self.spec.input_rel_y,
            text,
            auto_send=bool(cfg.get("auto_send")),
        )
        if screenshot_path is not None:
            screenshot_region(win, self.spec.input_rel_x, self.spec.input_rel_y, screenshot_path)
        return win

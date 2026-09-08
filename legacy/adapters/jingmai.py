from __future__ import annotations

from pathlib import Path

from legacy.adapters.base import PlatformAdapter, PlatformSpec
from legacy.ui.windows import WinInfo


class JingmaiWebAdapter(PlatformAdapter):
    """Dongdong web workbench. Native Win32 fill is skipped on purpose."""

    def __init__(self, spec: PlatformSpec, web_cfg: dict) -> None:
        super().__init__(spec)
        self.web_cfg = web_cfg

    def chat_window(self) -> WinInfo:
        raise RuntimeError("jingmai web mode does not use the desktop client window")

    def fill_draft(self, text: str, screenshot_path=None) -> WinInfo:
        from legacy.ui.web_jingmai import fill_web_draft

        target = fill_web_draft(self.web_cfg, text, Path(screenshot_path) if screenshot_path else None)
        return WinInfo(
            hwnd=target.hwnd,
            title=target.title,
            class_name="playwright",
            process="msedge" if "咚咚工作站" in (target.title or "") else "chrome",
            visible=True,
            left=0,
            top=0,
            right=0,
            bottom=0,
        )


def make_adapter(cfg: dict) -> PlatformAdapter:
    jm = cfg["jingmai"]
    rel = jm.get("input_rel") or {"x": 0.219, "y": 0.640}
    spec = PlatformSpec(
        key="jingmai",
        process=jm.get("process") or "jdm_dd_workbench",
        window_title_contains=jm.get("window_title_contains") or "咚咚融合工作台",
        notify_title=jm.get("notify_title") or "新消息提醒",
        input_rel_x=float(rel["x"]),
        input_rel_y=float(rel["y"]),
    )
    mode = str(jm.get("mode") or "web").lower()
    if mode == "web":
        return JingmaiWebAdapter(spec, jm.get("web") or {})
    return PlatformAdapter(spec)

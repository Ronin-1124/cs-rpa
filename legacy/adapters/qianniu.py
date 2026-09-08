from __future__ import annotations

from legacy.adapters.base import PlatformAdapter, PlatformSpec


def make_adapter(cfg: dict) -> PlatformAdapter:
    qn = cfg["qianniu"]
    rel = qn["input_rel"]
    return PlatformAdapter(
        PlatformSpec(
            key="qianniu",
            process=qn["process"],
            window_title_contains=qn["window_title_contains"],
            notify_title=qn["notify_title"],
            input_rel_x=float(rel["x"]),
            input_rel_y=float(rel["y"]),
        )
    )

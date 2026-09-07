"""Record the mouse position relative to a chat window.

Usage:
  python calibrate.py jingmai
  python calibrate.py qianniu

Put the cursor in the message input box, then wait for the countdown.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import yaml

from ui.windows import find_window, list_windows


def load_config() -> dict:
    path = Path(__file__).with_name("config.yaml")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("platform", choices=["qianniu", "jingmai"])
    parser.add_argument("--seconds", type=int, default=5)
    args = parser.parse_args()
    cfg = load_config()[args.platform]
    win = find_window(cfg["process"], cfg["window_title_contains"], visible_only=True)
    if win is None:
        print("window not found. current titled windows:", file=sys.stderr)
        for w in list_windows():
            if w.visible and w.title:
                print(f"  {w.process}: {w.title}", file=sys.stderr)
        return 1
    print(f"window: {win.title} {win.left},{win.top} {win.width}x{win.height}")
    print(f"move the cursor into the INPUT BOX of {args.platform} ...")
    for i in range(args.seconds, 0, -1):
        print(f"  {i}")
        time.sleep(1)
    import ctypes
    from ctypes import wintypes

    pt = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    if win.width <= 0 or win.height <= 0:
        print("invalid window size", file=sys.stderr)
        return 1
    x_rel = (pt.x - win.left) / win.width
    y_rel = (pt.y - win.top) / win.height
    print(f"cursor=({pt.x},{pt.y})")
    print(f"input_rel: {{x: {x_rel:.3f}, y: {y_rel:.3f}}}")
    print("paste those numbers into config.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

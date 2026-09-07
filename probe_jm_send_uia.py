"""Find Jingmai 发送 via UIA and inspect siblings. Never send."""
from __future__ import annotations

import time
from pathlib import Path

from PIL import ImageGrab

from ui.windows import (
    SW_RESTORE,
    _minimize_siblings,
    restore_if_needed,
    set_clipboard_text,
    user32,
)


def dump_ctrl(c, prefix: str) -> None:
    try:
        r = c.BoundingRectangle
        rect = f"({r.left},{r.top})-({r.right},{r.bottom})"
    except Exception:
        rect = "?"
    try:
        print(
            f"{prefix} type={c.ControlTypeName} name={c.Name!r:.80} "
            f"cls={c.ClassName!r} auto={c.AutomationId!r} rect={rect} "
            f"focusable={c.IsKeyboardFocusable} hwnd={c.NativeWindowHandle} "
            f"value={getattr(c, 'GetValuePattern', lambda: None)()}"
        )
    except Exception as e:
        print(f"{prefix} err {e}")


def try_value(c, text: str) -> bool:
    try:
        vp = c.GetValuePattern()
        if vp:
            vp.SetValue(text)
            print(f"  SetValue on {c.ControlTypeName} {c.Name!r}")
            return True
    except Exception as e:
        print(f"  SetValue failed: {e}")
    try:
        tp = c.GetLegacyIAccessiblePattern()
        if tp:
            tp.SetValue(text)
            print(f"  Legacy SetValue on {c.ControlTypeName} {c.Name!r}")
            return True
    except Exception as e:
        print(f"  Legacy SetValue failed: {e}")
    return False


def main() -> int:
    artifacts = Path(__file__).resolve().parent / "artifacts"
    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    _minimize_siblings(win)
    user32.ShowWindow(win.hwnd, SW_RESTORE)
    user32.SetForegroundWindow(win.hwnd)
    time.sleep(0.4)

    import uiautomation as auto

    draft = "[草稿未发送] 咚咚填充1243"
    set_clipboard_text(draft)

    print("=== search 发送 ===")
    btn = auto.ButtonControl(searchDepth=30, Name="发送")
    if btn.Exists(1.0, 0.1):
        dump_ctrl(btn, "SEND")
        p = btn.GetParentControl()
        dump_ctrl(p, "PARENT")
        if p:
            kids = p.GetChildren()
            print(f"siblings/children of parent: {len(kids)}")
            for i, k in enumerate(kids):
                dump_ctrl(k, f"  [{i}]")
                if k.IsKeyboardFocusable or k.ControlTypeName in (
                    "EditControl",
                    "DocumentControl",
                    "CustomControl",
                    "TextControl",
                ):
                    if try_value(k, draft):
                        time.sleep(0.3)
                        ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-setvalue.png")
                        print("tried SetValue")
    else:
        print("no Button 发送")

    print("=== search by name contains ===")
    root = auto.ControlFromHandle(win.hwnd)
    found = 0

    def walk(c, depth: int = 0) -> None:
        nonlocal found
        if depth > 15 or found > 60:
            return
        try:
            name = c.Name or ""
            t = c.ControlTypeName
            if (
                "发送" in name
                or "输入" in name
                or "粘贴" in name
                or t in ("EditControl", "DocumentControl", "ComboBoxControl")
                or c.IsKeyboardFocusable
            ):
                dump_ctrl(c, f"d{depth}")
                found += 1
                if t in ("EditControl", "DocumentControl") or ("输入" in name):
                    try_value(c, draft)
        except Exception:
            return
        try:
            for ch in c.GetChildren():
                walk(ch, depth + 1)
        except Exception:
            return

    walk(root)
    print(f"walk matched {found}")

    print("=== ControlFromPoint around compose/send ===")
    for x, y in ((420, 720), (700, 800), (980, 1045), (500, 1040), (396, 649)):
        try:
            c = auto.ControlFromPoint(x, y)
            dump_ctrl(c, f"pt({x},{y})")
        except Exception as e:
            print(f"pt({x},{y}) err {e}")

    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-uia-send.png")
    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

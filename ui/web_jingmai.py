"""Jingmai Dongdong web workbench fill. Fills replies and clicks 发送 when auto_send.

Prefers the already-logged-in Edge window titled 咚咚工作站 (user login
state). Falls back to Playwright CDP on a dedicated profile.
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Frame, Locator, Page, sync_playwright

SEND_LABELS = ("发送", "發送", "Send")
COMPOSER_SELECTORS = (
    "textarea",
    "[contenteditable='true']",
    "[contenteditable='']",
    "[role='textbox']",
    "div.ql-editor",
    ".ProseMirror",
    "[placeholder*='输入']",
    "[placeholder*='請輸入']",
    "[placeholder*='请输入']",
)
CHROME_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)
EDITOR_CLASS_HINTS = ("EditorContent", "ql-editor", "ProseMirror", "public-DraftEditor")
STREAM_CLASS_NEEDLES = ("c_stream-content", "stream-content")
STREAM_ITEM_NEEDLES = ("c_stream-item", "stream-item")
MESSAGE_WRAP_NEEDLES = ("chat-scroll-wrap", "c-wrap")
TAB_NAMES = ("留言", "正在咨询", "今日咨询", "待付款", "已付款", "未下单")
_SKIP_SESSION_NAMES = set(TAB_NAMES) | {"搜索联系人", "搜索", "搜索关键词/快捷短语"}
_GROUP_HEADER_RE = re.compile(
    r"^(正在咨询|留言|内部会话|最近联系人|今日咨询|待付款|已付款|未下单)"
)
_GROUP_COUNT_RE = re.compile(
    r"^(正在咨询|留言|内部会话(?:&群聊)?)\((\d+)\)"
)
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
GA_ROOT = 2


@dataclass(frozen=True)
class FillTarget:
    hwnd: int
    title: str


@dataclass(frozen=True)
class SessionRow:
    buyer_id: str
    preview: str
    time: str
    unread: int
    click_x: int
    click_y: int


@dataclass(frozen=True)
class ChatMessage:
    role: str
    text: str
    y: int


def _is_login(url: str) -> bool:
    u = (url or "").lower()
    if "dongdong.jd.com" in u and "passport" not in u:
        return False
    return "passport." in u or "/uc/login" in u


def _looks_like_send(loc: Locator) -> bool:
    try:
        name = (loc.get_attribute("aria-label") or "") + (loc.inner_text(timeout=400) or "")
    except Exception:
        name = loc.get_attribute("aria-label") or ""
    return any(s in (name or "") for s in SEND_LABELS)


def _pick_composer(root: Page | Frame) -> Locator | None:
    for sel in COMPOSER_SELECTORS:
        loc = root.locator(sel)
        n = loc.count()
        for i in range(n - 1, -1, -1):
            item = loc.nth(i)
            try:
                if not item.is_visible(timeout=400):
                    continue
            except Exception:
                continue
            if _looks_like_send(item):
                continue
            box = item.bounding_box()
            if box is None or box["width"] < 80 or box["height"] < 16:
                continue
            return item
    return None


def find_composer(page: Page) -> Locator:
    found = _pick_composer(page)
    if found is not None:
        return found
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        found = _pick_composer(frame)
        if found is not None:
            return found
    raise RuntimeError("dongdong web composer not found (log in and open a chat first)")


def _fill_locator(page: Page, loc: Locator, text: str) -> None:
    loc.scroll_into_view_if_needed(timeout=5000)
    loc.click(timeout=5000)
    # Never press Enter: fill/insert_text must not submit the chat.
    try:
        loc.fill(text, timeout=4000)
    except Exception:
        loc.click()
        loc.evaluate(
            """(el) => {
                el.focus();
                if ('value' in el) el.value = '';
                else el.innerText = '';
            }"""
        )
        page.keyboard.insert_text(text)


def _port_open(host: str, port: int) -> bool:
    sock = socket.socket()
    sock.settimeout(0.35)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _chrome_exe() -> str:
    for path in CHROME_CANDIDATES:
        if Path(path).is_file():
            return path
    raise RuntimeError("Chrome/Edge not found; install Chrome or set jingmai.web.chrome_path")


def _parse_cdp(cdp_url: str) -> tuple[str, int]:
    raw = cdp_url.replace("http://", "").replace("https://", "")
    host, _, port_s = raw.partition(":")
    host = host or "127.0.0.1"
    port = int(port_s.split("/")[0] or "9222")
    return host, port


def _ensure_debug_chrome(web: dict, url: str) -> str:
    cdp = (web.get("cdp_url") or "http://127.0.0.1:9222").strip()
    host, port = _parse_cdp(cdp)
    if _port_open(host, port):
        return f"http://{host}:{port}"

    user_data = Path(web.get("user_data_dir") or "artifacts/chrome-jingmai")
    if not user_data.is_absolute():
        user_data = Path(__file__).resolve().parent.parent / user_data
    user_data.mkdir(parents=True, exist_ok=True)
    exe = web.get("chrome_path") or _chrome_exe()
    flags = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data}",
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
        url,
    ]
    subprocess.Popen(
        flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
    )
    for _ in range(50):
        if _port_open(host, port):
            time.sleep(0.4)
            return f"http://{host}:{port}"
        time.sleep(0.2)
    raise RuntimeError(f"Chrome debug port {port} did not open")


def _existing_page(context, url_hint: str) -> Page | None:
    for page in context.pages:
        if "dongdong.jd.com" in (page.url or ""):
            return page
    hint_host = ""
    if "://" in url_hint:
        hint_host = url_hint.split("/")[2]
    if hint_host:
        for page in context.pages:
            if hint_host in (page.url or "") and "passport" not in page.url:
                return page
    return None


_cfg_cache: dict | None = None
_logged_mock_fallback = False
MOCK_TITLE_MARK = "本地测试"


def _load_root_cfg() -> dict:
    global _cfg_cache
    if _cfg_cache is not None:
        return _cfg_cache
    import yaml

    root = Path(__file__).resolve().parent.parent
    cfg = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8")) or {}
    local = root / "config.local.yaml"
    if local.exists():
        cfg.update(yaml.safe_load(local.read_text(encoding="utf-8")) or {})
    _cfg_cache = cfg
    return cfg


def _web_cfg() -> dict:
    return (_load_root_cfg().get("jingmai") or {}).get("web") or {}


def mock_mode() -> bool:
    env = os.environ.get("CS_RPA_MOCK")
    if env is not None and str(env).strip() != "":
        return str(env).strip().lower() in ("1", "true", "yes", "on")
    return bool(_web_cfg().get("mock"))


def mock_workbench_url() -> str:
    return str(_web_cfg().get("mock_url") or "http://127.0.0.1:18765/workbench")


def _is_mock_dongdong_title(title: str) -> bool:
    t = title or ""
    return "咚咚工作站" in t and MOCK_TITLE_MARK in t


def _is_real_dongdong_title(title: str) -> bool:
    t = title or ""
    return "咚咚工作站" in t and MOCK_TITLE_MARK not in t


def dongdong_missing_hint() -> str:
    if mock_mode():
        return (
            "open 咚咚工作站·本地测试 first "
            "(python -m mock_dongdong serve --open / run-mock.cmd)"
        )
    return "open 咚咚工作站 in Edge"


def _pick_edge_frame(hits):
    vis = [w for w in hits if w.visible]
    pool = vis or list(hits)
    if not pool:
        return None
    pool.sort(
        key=lambda w: (
            0 if w.visible else 1,
            0 if (w.class_name or "").endswith("_1") else 1,
            -(w.width * w.height),
        )
    )
    return pool[0]


def _find_live_dongdong_edge():
    from ui.windows import list_windows

    edges = [
        w
        for w in list_windows()
        if w.process == "msedge"
        and (w.class_name or "").startswith("Chrome_WidgetWin")
        and w.width >= 400
        and w.height >= 300
    ]
    mock_hits = [w for w in edges if _is_mock_dongdong_title(w.title or "")]
    real_hits = [w for w in edges if _is_real_dongdong_title(w.title or "")]
    if mock_mode():
        return _pick_edge_frame(mock_hits)
    found = _pick_edge_frame(real_hits)
    if found is not None:
        return found
    # Usual hang command with only the local test window open.
    fallback = _pick_edge_frame(mock_hits)
    if fallback is not None:
        global _logged_mock_fallback
        if not _logged_mock_fallback:
            print(
                "jingmai web: real 咚咚 not found, using 本地测试 window. "
                "Prefer run-jm-mock.cmd so the real shop is never touched.",
                flush=True,
            )
            _logged_mock_fallback = True
        return fallback
    return None


def _prepare_live_edge(steal_focus: bool = True):
    from ui.windows import SW_SHOW, foreground, maximize, user32, win_from_hwnd

    win = _find_live_dongdong_edge()
    if win is None:
        raise RuntimeError(f"dongdong Edge window not found ({dongdong_missing_hint()})")
    if not steal_focus:
        return win
    user32.ShowWindow(win.hwnd, SW_SHOW)
    maximize(win)
    # Do not keep_topmost: that pins 咚咚 over 千牛 on every poll.
    foreground(win, settle_s=0.35, keep_topmost=False, restore=False)
    live = win_from_hwnd(win.hwnd)
    return live or win


def _climb(ctrl, pred, limit: int = 16):
    cur = ctrl
    for _ in range(limit):
        if cur is None:
            return None
        try:
            if pred(cur):
                return cur
            cur = cur.GetParentControl()
        except Exception:
            return None
    return None


def _named_texts(ctrl, depth: int = 0, acc=None, max_depth: int = 10) -> list[str]:
    if acc is None:
        acc = []
    if depth > max_depth:
        return acc
    try:
        name = (ctrl.Name or "").strip()
        if name:
            acc.append(name)
        for child in ctrl.GetChildren():
            _named_texts(child, depth + 1, acc, max_depth)
    except Exception:
        pass
    return acc


def _point(win, x_rel: float, y_rel: float) -> tuple[int, int]:
    return win.left + int(win.width * x_rel), win.top + int(win.height * y_rel)


def _find_class_bfs(root, needle: str, max_nodes: int = 8000, max_depth: int = 24):
    from collections import deque

    q = deque([(root, 0)])
    seen = 0
    deadline = time.time() + 2.5
    while q and seen < max_nodes and time.time() < deadline:
        ctrl, depth = q.popleft()
        seen += 1
        if needle in _ctrl_class(ctrl):
            return ctrl
        if depth >= max_depth:
            continue
        try:
            kids = ctrl.GetChildren()
        except Exception:
            continue
        for ch in kids[:100]:
            q.append((ch, depth + 1))
    return None


def _find_class_any(root, needle: str, max_depth: int = 22):
    """Find a descendant whose ClassName contains needle. No focus change."""
    if root is None:
        return None
    try:
        item = root.Control(ClassName=needle, searchDepth=max_depth)
        if item is not None and item.Exists(0, 0) and needle in _ctrl_class(item):
            return item
    except Exception:
        pass

    def pred(ctrl, _depth: int) -> bool:
        return needle in _ctrl_class(ctrl)

    try:
        found = root.FindControl(pred, maxDepth=max_depth)
        if found is not None:
            return found
    except Exception:
        pass
    return _find_class_bfs(root, needle, max_nodes=8000, max_depth=max_depth)


def _enum_child_hwnds(hwnd: int) -> list[tuple[int, str]]:
    from ui.windows import EnumWindowsProc, _text, user32

    found: list[int] = []

    def cb(child, _lp) -> bool:
        found.append(int(child))
        return True

    proc = EnumWindowsProc(cb)
    try:
        user32.EnumChildWindows(int(hwnd), proc, 0)
    except Exception:
        return []
    out: list[tuple[int, str]] = []
    for h in found:
        cls = _text(user32.GetClassNameW, h, 256)
        out.append((h, cls or ""))
    return out


def _uia_roots(win):
    """Top-level Edge hwnd plus Chrome render widgets. Page UIA lives on the child."""
    import uiautomation as auto

    roots = []
    seen: set[int] = set()

    def add(hwnd: int) -> None:
        hwnd = int(hwnd)
        if hwnd in seen:
            return
        seen.add(hwnd)
        try:
            ctrl = auto.ControlFromHandle(hwnd)
        except Exception:
            return
        if ctrl is not None:
            roots.append(ctrl)

    add(win.hwnd)
    children = _enum_child_hwnds(win.hwnd)
    render = [h for h, cls in children if "RenderWidget" in cls]
    widgets = [
        h
        for h, cls in children
        if cls.startswith("Chrome_WidgetWin") and h not in render
    ]
    for h in render + widgets:
        add(h)
        if len(roots) >= 6:
            break
    return roots


def _native_hwnd(ctrl) -> int:
    try:
        h = int(ctrl.NativeWindowHandle or 0)
        if h:
            return h
    except Exception:
        pass
    cur = ctrl
    for _ in range(24):
        try:
            cur = cur.GetParentControl()
        except Exception:
            return 0
        if cur is None:
            return 0
        try:
            h = int(cur.NativeWindowHandle or 0)
        except Exception:
            h = 0
        if h:
            return h
    return 0


def _belongs_to_win(ctrl, win) -> bool:
    if ctrl is None:
        return False
    from ui.windows import user32

    h = _native_hwnd(ctrl)
    if h:
        if h == win.hwnd:
            return True
        try:
            root = int(user32.GetAncestor(h, GA_ROOT) or 0)
            if root == win.hwnd:
                return True
        except Exception:
            pass
        try:
            parent = h
            for _ in range(8):
                parent = int(user32.GetParent(parent) or 0)
                if not parent:
                    break
                if parent == win.hwnd:
                    return True
        except Exception:
            pass
        return False
    try:
        r = ctrl.BoundingRectangle
        cx = (int(r.left) + int(r.right)) // 2
        cy = (int(r.top) + int(r.bottom)) // 2
        return win.left <= cx <= win.right and win.top <= cy <= win.bottom
    except Exception:
        return False


def _search_needles(roots, needles: tuple[str, ...], max_depth: int = 22):
    for root in roots:
        for needle in needles:
            found = _find_class_any(root, needle, max_depth=max_depth)
            if found is not None:
                return found
    return None


_stream_cache: dict = {"hwnd": 0, "ctrl": None, "t": 0.0}


def _session_stream(win, allow_point: bool = True):
    import uiautomation as auto

    now = time.time()
    cached = _stream_cache.get("ctrl")
    if _stream_cache.get("hwnd") == win.hwnd and now - float(_stream_cache.get("t") or 0) < 5:
        try:
            if cached is not None and cached.Exists(0, 0):
                return cached
        except Exception:
            pass

    roots = _uia_roots(win)
    stream = _search_needles(roots, STREAM_CLASS_NEEDLES, max_depth=20)
    if stream is None and allow_point:
        probes = (
            _point(win, 0.12, 0.32),
            _point(win, 0.10, 0.38),
            _point(win, 0.14, 0.28),
            _point(win, 0.11, 0.45),
            (win.left + 160, win.top + 320),
            (win.left + 120, win.top + 280),
        )
        for x, y in probes:
            if x < win.left or x > win.right or y < win.top or y > win.bottom:
                continue
            try:
                hit = auto.ControlFromPoint(int(x), int(y))
            except Exception:
                continue
            if hit is None or not _belongs_to_win(hit, win):
                continue
            stream = _climb(
                hit,
                lambda c: any(n in _ctrl_class(c) for n in STREAM_CLASS_NEEDLES),
            )
            if stream is not None:
                break
    if stream is not None:
        _stream_cache.update(hwnd=win.hwnd, ctrl=stream, t=now)
    return stream


def _is_stream_item(cn: str) -> bool:
    return any(n in cn for n in STREAM_ITEM_NEEDLES)


def _is_skip_session_name(name: str) -> bool:
    if not name:
        return True
    if name in _SKIP_SESSION_NAMES:
        return True
    if _GROUP_HEADER_RE.match(name):
        return True
    if "翻译" in name and ("页面" in name or "英语" in name):
        return True
    return False


def _iter_session_item_ctrls(stream):
    found = []

    def walk(node, depth: int) -> None:
        if depth > 8:
            return
        cn = _ctrl_class(node)
        if _is_stream_item(cn):
            found.append(node)
            return
        try:
            kids = node.GetChildren()
        except Exception:
            return
        for ch in kids:
            walk(ch, depth + 1)

    walk(stream, 0)
    for c in found:
        yield c


def _parse_session_row(child) -> SessionRow | None:
    names = _named_texts(child)
    if not names:
        return None
    # Chrome often puts concatenated innerText on the row; keep leaf names.
    leaves: list[str] = []
    for n in names:
        others = [x for x in names if x != n]
        if len(n) >= 8 and sum(1 for x in others if x and x in n) >= 2:
            continue
        leaves.append(n)
    if leaves:
        names = leaves
    unread = 0
    rest = list(names)
    if rest and rest[0].isdigit() and len(rest[0]) <= 3:
        unread = int(rest.pop(0))
    buyer = rest[0] if rest else ""
    if _is_skip_session_name(buyer):
        return None
    ts = ""
    preview = ""
    for item in rest[1:]:
        if _is_skip_session_name(item):
            continue
        if _TIME_RE.match(item) or ("月" in item and "日" in item):
            ts = item
        elif item != buyer and not preview:
            preview = item
    rect = child.BoundingRectangle
    cx = int(rect.left) + min(90, max(40, (int(rect.right) - int(rect.left)) // 3))
    cy = (int(rect.top) + int(rect.bottom)) // 2
    return SessionRow(buyer, preview, ts, unread, cx, cy)


def list_live_sessions(win=None, steal_focus: bool = True) -> list[SessionRow]:
    """Visible session rows in the left list (留言 / 正在咨询 / 最近联系人)."""
    if win is None:
        win = _prepare_live_edge(steal_focus=steal_focus)
    stream = _session_stream(win, allow_point=True)
    if stream is None:
        raise RuntimeError("dongdong session list not found")
    rows: list[SessionRow] = []
    seen: set[str] = set()
    for child in _iter_session_item_ctrls(stream):
        row = _parse_session_row(child)
        if row is None or row.buyer_id in seen:
            continue
        seen.add(row.buyer_id)
        rows.append(row)
    return rows


def list_inbox_tabs(win) -> list[dict]:
    out: list[dict] = []
    for root in _uia_roots(win):
        nav = _find_class_any(root, "c_tabs-nav", max_depth=18)
        if nav is None:
            continue
        tabs = [c for c in nav.GetChildren() if "c_tabs-tab" in _ctrl_class(c)]
        for i, tab in enumerate(tabs):
            try:
                r = tab.BoundingRectangle
                cx = (int(r.left) + int(r.right)) // 2
                cy = (int(r.top) + int(r.bottom)) // 2
            except Exception:
                continue
            cn = _ctrl_class(tab)
            names = _named_texts(tab, max_depth=3)[:6]
            selected = any(s in cn for s in ("active", "selected", "tabs-tab-active"))
            out.append(
                {
                    "index": i,
                    "class": cn,
                    "names": names,
                    "cx": cx,
                    "cy": cy,
                    "selected": selected,
                }
            )
        if out:
            break
    return out


def click_inbox_tab(win, index: int = 0) -> bool:
    """Click a top icon tab in the session list. 0 = live 正在咨询/留言, 1 = 最近联系人."""
    from ui.windows import click_abs

    tabs = list_inbox_tabs(win)
    if not tabs or index >= len(tabs):
        return False
    tab = tabs[index]
    click_abs(int(tab["cx"]), int(tab["cy"]), settle_s=0.7)
    _stream_cache.update(hwnd=0, ctrl=None, t=0.0)
    time.sleep(0.25)
    return True


def _stream_is_live_inbox(stream) -> bool:
    if stream is None:
        return False
    try:
        kids = list(stream.GetChildren())
    except Exception:
        return False
    for ch in kids[:10]:
        cn = _ctrl_class(ch)
        names = " ".join(_named_texts(ch, max_depth=4)[:8])
        if "c_cas-head" in cn or "正在咨询" in names or "内部会话" in names:
            return True
        if names == "留言" or names.startswith("留言("):
            return True
    return False


def live_group_counts(win) -> dict[str, int]:
    stream = _session_stream(win, allow_point=True)
    if stream is None:
        return {}
    out: dict[str, int] = {}
    try:
        kids = list(stream.GetChildren())
    except Exception:
        return {}
    for ch in kids[:12]:
        for name in _named_texts(ch, max_depth=3)[:8]:
            compact = name.replace(" ", "")
            m = _GROUP_COUNT_RE.match(compact)
            if not m:
                continue
            label = m.group(1)
            if label.startswith("留言"):
                key = "留言"
            elif label.startswith("正在咨询"):
                key = "正在咨询"
            else:
                key = "内部"
            out[key] = int(m.group(2))
    return out


def _click_named_group(win, label: str) -> bool:
    from ui.windows import click_abs

    roots = _uia_roots(win)
    left_cut = win.left + int(win.width * 0.40)
    top_cut = win.top + int(win.height * 0.55)

    def pred(ctrl, _depth: int) -> bool:
        try:
            name = (ctrl.Name or "").strip()
        except Exception:
            return False
        if not (name == label or name.startswith(f"{label}(")):
            return False
        try:
            r = ctrl.BoundingRectangle
            cx = (int(r.left) + int(r.right)) // 2
            cy = (int(r.top) + int(r.bottom)) // 2
        except Exception:
            return False
        return win.left <= cx <= left_cut and win.top <= cy <= top_cut

    for root in roots:
        try:
            found = root.FindControl(pred, maxDepth=18)
        except Exception:
            found = None
        if found is None:
            continue
        try:
            r = found.BoundingRectangle
            cx = (int(r.left) + int(r.right)) // 2
            cy = (int(r.top) + int(r.bottom)) // 2
        except Exception:
            continue
        click_abs(cx, cy, settle_s=0.4)
        _stream_cache.update(hwnd=0, ctrl=None, t=0.0)
        return True
    return False


def ensure_live_inbox(win) -> bool:
    """Stay on tab 0 (正在咨询/留言). Click only if the live list is not showing."""
    stream = _session_stream(win, allow_point=True)
    if stream is None or not _stream_is_live_inbox(stream):
        if not click_inbox_tab(win, 0):
            return False
        stream = _session_stream(win, allow_point=True)
    if stream is None:
        return False
    counts = live_group_counts(win)
    live_n = int(counts.get("正在咨询") or 0) + int(counts.get("留言") or 0)
    rows_n = sum(1 for _ in _iter_session_item_ctrls(stream))
    if live_n > 0 and rows_n == 0:
        if int(counts.get("留言") or 0) > 0:
            _click_named_group(win, "留言")
        if int(counts.get("正在咨询") or 0) > 0:
            _click_named_group(win, "正在咨询")
    return True


def restore_live_inbox() -> int:
    """Bring 咚咚工作站 to front on tab 0 after a person clicked the UI. Never sends."""
    win = _prepare_live_edge(steal_focus=True)
    ok = ensure_live_inbox(win)
    counts = live_group_counts(win)
    try:
        rows = list_live_sessions(win, steal_focus=False)
    except Exception as exc:
        print(
            f"restore failed: hwnd={win.hwnd} tab0={ok} groups={counts} list={exc}",
            flush=True,
        )
        return 1
    print(
        f"restore ok hwnd={win.hwnd} title={win.title} tab0={ok} "
        f"groups={counts} live_sessions={len(rows)}",
        flush=True,
    )
    return 0


def open_recent_contacts(win) -> bool:
    """Tab 1: 最近联系人 (historical buyers)."""
    return click_inbox_tab(win, 1)


def ensure_liuyan_tab(win) -> bool:
    """Open the live inbox (tab 0) and expand the 留言 group. Never sends."""
    clicked = click_inbox_tab(win, 0)
    if _click_named_group(win, "留言"):
        clicked = True
    return clicked


def open_live_session(win, buyer_id: str, row: SessionRow | None = None):
    from ui.windows import click_abs

    match = row
    if match is None or match.buyer_id != buyer_id:
        try:
            rows = list_live_sessions(win)
        except RuntimeError:
            win = _prepare_live_edge()
            rows = list_live_sessions(win)
        match = next((r for r in rows if r.buyer_id == buyer_id), None)
    if match is None:
        raise RuntimeError(f"session not in list: {buyer_id}")
    click_abs(match.click_x, match.click_y, settle_s=0.85)
    header = read_live_header(win)
    if header and buyer_id not in header:
        print(f"jingmai web: opened {buyer_id} header={header!r}", flush=True)
    return match


def read_live_header(win) -> str:
    import uiautomation as auto

    for root in _uia_roots(win):
        head = _find_class_any(root, "chat-head-name", max_depth=20)
        if head is None:
            continue
        names = [n for n in _named_texts(head, max_depth=4) if n]
        if names:
            return names[0]
    for x, y in (
        (win.left + 450, win.top + 108),
        _point(win, 0.28, 0.12),
        _point(win, 0.35, 0.11),
        _point(win, 0.40, 0.16),
    ):
        try:
            hit = auto.ControlFromPoint(int(x), int(y))
        except Exception:
            continue
        head = _climb(hit, lambda c: "chat-head-name" in _ctrl_class(c))
        if head is None:
            continue
        names = [n for n in _named_texts(head, max_depth=4) if n]
        if names:
            return names[0]
    return ""


_TIME_RE = re.compile(r"^(\d{2}:\d{2}(:\d{2})?|\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})$")
_SKIP_BUBBLE = {
    "发送",
    "聊天",
    "返回",
    "转接客户",
    "搜索联系人",
    "搜索关键词/快捷短语",
    "图片-正常",
    "今日咨询",
    "待付款",
    "已付款",
    "未下单",
    "已读",
    "未读",
}


def _message_role_from_class(cn: str) -> str:
    if "message_left" in cn:
        return "customer"
    if "message_right" in cn:
        return "agent"
    if "message_center" in cn:
        return "system"
    return "unknown"


def _unwrap_chat(wrap):
    if wrap is None:
        return None
    wcn = _ctrl_class(wrap)
    if "chat-scroll-wrap" in wcn:
        try:
            kids = wrap.GetChildren()
        except Exception:
            kids = []
        if kids and "c-wrap" in _ctrl_class(kids[0]):
            return kids[0]
        inner = _find_class_any(wrap, "c-wrap", max_depth=6)
        return inner or wrap
    return wrap


def _find_message_wrap(win):
    import uiautomation as auto

    roots = _uia_roots(win)
    wrap = _search_needles(roots, MESSAGE_WRAP_NEEDLES, max_depth=20)
    found = _unwrap_chat(wrap)
    if found is not None:
        return found

    for y in range(win.top + 180, min(win.bottom - 80, win.top + 820), 36):
        for x in (
            win.left + int(win.width * 0.42),
            win.left + int(win.width * 0.48),
            win.left + int(win.width * 0.55),
            win.left + 450,
        ):
            if x < win.left or x > win.right:
                continue
            try:
                hit = auto.ControlFromPoint(int(x), int(y))
            except Exception:
                continue
            if hit is None or not _belongs_to_win(hit, win):
                continue
            cn = _ctrl_class(hit)
            if hit.ControlTypeName == "GroupControl" and cn.strip() in ("root", "") and not (hit.Name or "").strip():
                continue
            wrap = _climb(
                hit,
                lambda c: _ctrl_class(c).strip() == "c-wrap" or "chat-scroll-wrap" in _ctrl_class(c),
            )
            found = _unwrap_chat(wrap)
            if found is not None:
                return found
    return None


def _role_from_bubble_geom(ctrl) -> str:
    try:
        parent = ctrl.GetParentControl()
    except Exception:
        parent = None
    try:
        r = ctrl.BoundingRectangle
        cx = (int(r.left) + int(r.right)) // 2
    except Exception:
        return "customer"
    if parent is not None and "c-wrap" in _ctrl_class(parent):
        try:
            wr = parent.BoundingRectangle
            mid = (int(wr.left) + int(wr.right)) // 2
            return "agent" if cx > mid else "customer"
        except Exception:
            pass
    return "customer"


def _parse_bubble(ctrl) -> ChatMessage | None:
    cn = _ctrl_class(ctrl)
    role = _message_role_from_class(cn)
    if role == "unknown" and "bubble" in cn:
        role = _role_from_bubble_geom(ctrl)
    if role == "unknown" and "message_" not in cn:
        return None
    if role == "unknown":
        role = "system"
    parts: list[str] = []
    has_image = False
    has_emoji = False

    def walk(node, depth: int = 0) -> None:
        nonlocal has_image, has_emoji
        if depth > 8:
            return
        try:
            ncn = _ctrl_class(node)
            name = (node.Name or "").strip()
            if "message__image" in ncn:
                has_image = True
            if "message__emoticon" in ncn or "emoticon" in ncn:
                has_emoji = True
            if "message__nickname" in ncn or "message__avatar" in ncn or "read_status" in ncn:
                return
            if name and name not in _SKIP_BUBBLE and not _TIME_RE.match(name):
                if name not in parts:
                    parts.append(name[:500])
            for child in node.GetChildren():
                walk(child, depth + 1)
        except Exception:
            return

    walk(ctrl, 0)
    # Drop repeated nickname if it leaked
    body = [p for p in parts if p not in _SKIP_BUBBLE]
    if has_image and not body:
        body.append("[图片]")
    if has_emoji and not body:
        body.append("[表情]")
    if not body:
        return None
    text = "\n".join(body)
    y = int(ctrl.BoundingRectangle.top)
    return ChatMessage(role=role, text=text[:800], y=y)


def _collect_message_ctrls(wrap) -> list:
    out = []

    def walk(node, depth: int) -> None:
        if depth > 12:
            return
        cn = _ctrl_class(node)
        if "message_left" in cn or "message_right" in cn or "message_center" in cn:
            out.append(node)
            return
        if "bubble" in cn:
            out.append(node)
            return
        try:
            kids = node.GetChildren()
        except Exception:
            return
        for ch in kids:
            walk(ch, depth + 1)

    walk(wrap, 0)
    return out


def read_live_messages(win) -> list[ChatMessage]:
    """All currently rendered bubbles in the open chat (visible scroll viewport)."""
    wrap = _find_message_wrap(win)
    if wrap is None:
        return []
    rows = _collect_message_ctrls(wrap)
    if not rows:
        try:
            rows = list(wrap.GetChildren())
        except Exception:
            rows = []
        if len(rows) == 1 and "c-c" in _ctrl_class(rows[0]):
            rows = list(rows[0].GetChildren())
    header = read_live_header(win)
    out: list[ChatMessage] = []
    seen: set[tuple[str, str, int]] = set()
    for row in rows:
        msg = _parse_bubble(row)
        if msg is None:
            continue
        text = msg.text
        if header and text.strip() == header:
            continue
        key = (msg.role, text, msg.y)
        if key in seen:
            continue
        seen.add(key)
        out.append(msg)
    out.sort(key=lambda m: m.y)
    return out


def _thread_turns(messages: list[ChatMessage], preview: str = "") -> list[tuple[str, str]]:
    turns = [(m.role, m.text) for m in messages]
    if preview and not any(preview in (m.text or "") for m in messages if m.role == "customer"):
        turns.append(("customer", preview))
    return turns


def fill_openclaw_replies_all_sessions(
    screenshot_dir: Path | None = None,
    bridge_base: str = "http://192.168.2.252:18080",
    bridge_timeout_sec: int = 180,
) -> list[dict]:
    """Switch each visible buyer, send the on-screen thread to OpenClaw, fill draft if needed. Never sends."""
    from openclaw_client import OpenClawClient

    win = _prepare_live_edge()
    # Historical walk uses tab 1 (最近联系人). Tab 0 is live 正在咨询/留言 and is often empty.
    if not open_recent_contacts(win):
        click_inbox_tab(win, 0)
    try:
        rows = list_live_sessions(win)
    except RuntimeError:
        click_inbox_tab(win, 0)
        rows = list_live_sessions(win)
    if not rows:
        click_inbox_tab(win, 0)
        rows = list_live_sessions(win)
    client = OpenClawClient(bridge_base, bridge_timeout_sec)
    results: list[dict] = []
    for i, row in enumerate(rows):
        print(f"jingmai web: session {i + 1}/{len(rows)} {row.buyer_id}", flush=True)
        try:
            open_live_session(win, row.buyer_id, row)
        except RuntimeError as exc:
            print(f"  retry prepare after {exc}", flush=True)
            win = _prepare_live_edge()
            open_live_session(win, row.buyer_id, row)
        time.sleep(0.35)
        msgs = read_live_messages(win)
        if not msgs:
            time.sleep(0.5)
            msgs = read_live_messages(win)
        turns = _thread_turns(msgs, row.preview)
        shot = None
        if screenshot_dir is not None:
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            shot = screenshot_dir / f"oc-reply-{i}-{row.buyer_id[:16]}.png"
        item: dict = {
            "buyer_id": row.buyer_id,
            "preview": row.preview,
            "messages": [{"role": m.role, "text": m.text, "y": m.y} for m in msgs],
            "draft": "",
            "skip": False,
            "reason": "",
            "screenshot": str(shot) if shot else "",
        }
        if not any(t[0] == "customer" for t in turns):
            item["skip"] = True
            item["reason"] = "no customer text"
            print(f"  skip {row.buyer_id}: no customer text", flush=True)
            results.append(item)
            continue
        try:
            result = client.ask_thread("jingmai", row.buyer_id, turns)
        except Exception as exc:
            item["skip"] = True
            item["reason"] = f"openclaw error: {exc}"
            print(f"  skip {row.buyer_id}: {exc}", flush=True)
            results.append(item)
            continue
        if result.skip or not result.reply:
            item["skip"] = True
            item["reason"] = "openclaw NO_REPLY"
            print(f"  skip {row.buyer_id}: NO_REPLY", flush=True)
            results.append(item)
            continue
        text = result.reply.strip()
        _fill_live_edge(win, text, shot, send=auto_send_enabled())
        item["draft"] = text
        item["sent"] = auto_send_enabled()
        print(f"  filled {row.buyer_id}: {text[:80]} sent={item['sent']}", flush=True)
        results.append(item)
    click_inbox_tab(win, 0)
    return results


def fill_mock_replies_all_sessions(screenshot_dir: Path | None = None) -> list[dict]:
    """Back-compat name: OpenClaw drafts from the real on-screen thread. Never sends."""
    from pathlib import Path as _Path
    import yaml

    root = _Path(__file__).resolve().parent.parent
    cfg = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8")) or {}
    local = root / "config.local.yaml"
    if local.exists():
        cfg.update(yaml.safe_load(local.read_text(encoding="utf-8")) or {})
    return fill_openclaw_replies_all_sessions(
        screenshot_dir,
        str(cfg.get("bridge_base") or "http://192.168.2.252:18080"),
        int(cfg.get("bridge_timeout_sec") or 180),
    )


def _ctrl_class(ctrl) -> str:
    try:
        return ctrl.ClassName or ""
    except Exception:
        return ""


def _is_editor_ctrl(ctrl) -> bool:
    cn = _ctrl_class(ctrl)
    return any(h in cn for h in EDITOR_CLASS_HINTS)


def _find_editor_content(win) -> tuple[object, int, int]:
    """Return (control, click_x, click_y) inside EditorContent, away from 发送."""
    import uiautomation as auto

    editor = None
    roots = _uia_roots(win)
    for hint in EDITOR_CLASS_HINTS:
        editor = _search_needles(roots, (hint,), max_depth=20)
        if editor is not None:
            break
    if editor is None:
        probes = (
            (win.left + int(win.width * 0.55), win.top + int(win.height * 0.90)),
            (win.left + int(win.width * 0.48), win.top + int(win.height * 0.88)),
            (win.left + int(win.width * 0.62), win.top + int(win.height * 0.92)),
            (win.left + int(win.width * 0.40), win.top + int(win.height * 0.86)),
        )
        for x, y in probes:
            try:
                cur = auto.ControlFromPoint(int(x), int(y))
            except Exception:
                cur = None
            if cur is None or not _belongs_to_win(cur, win):
                continue
            for _ in range(10):
                if cur is None:
                    break
                if _is_editor_ctrl(cur):
                    editor = cur
                    break
                try:
                    cur = cur.GetParentControl()
                except Exception:
                    break
            if editor is not None:
                break
    if editor is None:
        raise RuntimeError("dongdong Edge composer (EditorContent) not found; open a chat first")
    rect = editor.BoundingRectangle
    left = int(rect.left)
    top = int(rect.top)
    right = min(int(rect.right), win.right - 12)
    bottom = int(rect.bottom)
    if right - left < 80 or bottom - top < 16:
        raise RuntimeError(f"dongdong Edge composer too small: {rect}")
    # Click left-of-center so fill never hits 发送 on the right of the strip.
    cx = left + int((right - left) * 0.35)
    cy = (top + bottom) // 2
    return editor, cx, cy


def auto_send_enabled() -> bool:
    return bool(_load_root_cfg().get("auto_send"))


def _send_btn_point(ctrl, win) -> tuple[int, int] | None:
    try:
        name = (ctrl.Name or "").strip()
        typ = ctrl.ControlTypeName or ""
        cn = _ctrl_class(ctrl)
        r = ctrl.BoundingRectangle
        w = int(r.right) - int(r.left)
        h = int(r.bottom) - int(r.top)
        cx = (int(r.left) + int(r.right)) // 2
        cy = (int(r.top) + int(r.bottom)) // 2
    except Exception:
        return None
    if name not in SEND_LABELS:
        return None
    if typ != "ButtonControl" and "send" not in cn.split():
        return None
    if w < 20 or h < 12 or w > 240 or h > 90:
        return None
    if cy < win.top + int(win.height * 0.55):
        return None
    if not (win.left <= cx <= win.right and win.top <= cy <= win.bottom):
        return None
    return cx, cy


def _click_send_button(win, editor=None) -> bool:
    """Click 发送 next to the composer. Never uses Enter."""
    from collections import deque

    from ui.windows import click_abs

    hits: list[tuple[int, int]] = []
    for root in _uia_roots(win):
        try:
            btn = root.Control(Name="发送", searchDepth=20)
            if btn is not None and btn.Exists(0, 0):
                pt = _send_btn_point(btn, win)
                if pt:
                    hits.append(pt)
        except Exception:
            pass
        q = deque([(root, 0)])
        seen = 0
        while q and seen < 5000:
            node, depth = q.popleft()
            seen += 1
            pt = _send_btn_point(node, win)
            if pt:
                hits.append(pt)
                break
            if depth >= 20:
                continue
            try:
                kids = node.GetChildren()
            except Exception:
                continue
            for ch in kids[:80]:
                q.append((ch, depth + 1))
        if hits:
            break
    if not hits and editor is not None:
        try:
            r = editor.BoundingRectangle
            hits.append((min(win.right - 36, int(r.right) + 36), int(r.bottom) - 18))
        except Exception:
            pass
    if not hits:
        return False
    hits.sort(key=lambda p: (p[1], p[0]))
    cx, cy = hits[-1]
    click_abs(cx, cy, settle_s=0.45)
    print(f"jingmai web: clicked 发送 at ({cx},{cy})", flush=True)
    return True


def _fill_live_edge(
    win, text: str, screenshot_path: Path | None, send: bool | None = None
) -> FillTarget:
    """Fill the logged-in Edge 咚咚工作站 window. Clicks 发送 when auto_send. Never Enter."""
    from ui.windows import click_abs, foreground, maximize, paste_text, user32, win_from_hwnd
    from ui.windows import HWND_NOTOPMOST, SWP_NOMOVE, SWP_NOSIZE, SWP_SHOWWINDOW
    from PIL import ImageGrab

    if send is None:
        send = auto_send_enabled()
    prev = int(user32.GetForegroundWindow() or 0)
    maximize(win)
    foreground(win, settle_s=0.4, keep_topmost=False, restore=False)
    live = win_from_hwnd(win.hwnd)
    if live is not None:
        win = live
    editor, cx, cy = _find_editor_content(win)
    click_abs(cx, cy, settle_s=0.2)
    click_abs(cx, cy, settle_s=0.15)
    # Web editor accepts Ctrl+V; do not Shift+Insert (would duplicate).
    paste_text(text, extra_shift_insert=False)
    time.sleep(0.35)
    if screenshot_path is not None:
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        box = (
            max(0, win.left),
            max(0, win.top + int(win.height * 0.72)),
            min(1920, win.right),
            min(1080, win.bottom),
        )
        ImageGrab.grab(bbox=box).save(screenshot_path)
    if send:
        if not _click_send_button(win, editor):
            raise RuntimeError("dongdong 发送 button not found after fill")
        time.sleep(0.35)
    user32.SetWindowPos(
        win.hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
    )
    if prev and prev != win.hwnd:
        user32.SetForegroundWindow(prev)
    print(
        f"jingmai web: filled live Edge hwnd={win.hwnd} at ({cx},{cy}) send={send}",
        flush=True,
    )
    return FillTarget(hwnd=win.hwnd, title=win.title)


def fill_web_draft(web: dict, text: str, screenshot_path: Path | None = None) -> FillTarget:
    """Fill Dongdong web composer. Clicks 发送 when auto_send is true. Never Enter."""
    if not text:
        raise RuntimeError("empty draft")
    prefer_live = web.get("prefer_live_edge")
    if prefer_live is None or prefer_live:
        live = _find_live_dongdong_edge()
        if live is not None:
            print(f"jingmai web: using logged-in Edge '{live.title}' hwnd={live.hwnd}", flush=True)
            return _fill_live_edge(live, text, screenshot_path)
        if mock_mode():
            raise RuntimeError(f"dongdong Edge window not found ({dongdong_missing_hint()})")

    url = web.get("url") or "https://dongdong.jd.com/"
    timeout_ms = int(web.get("timeout_ms") or 25000)
    cdp = _ensure_debug_chrome(web, url)

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = _existing_page(context, url)
        if page is None:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        else:
            page.bring_to_front()
            if "dongdong.jd.com" not in page.url and "passport" not in page.url:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        page.wait_for_timeout(800)
        login_wait = int(web.get("login_wait_sec") or 0)
        if _is_login(page.url) and login_wait > 0:
            print(f"dongdong login page open; waiting up to {login_wait}s for sign-in...", flush=True)
            deadline = time.time() + login_wait
            while time.time() < deadline and _is_login(page.url):
                page.wait_for_timeout(2000)
            page.wait_for_timeout(800)
        if _is_login(page.url):
            if screenshot_path is not None:
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshot_path), full_page=False)
            raise RuntimeError(
                "dongdong web needs login: complete sign-in in the opened Chrome window, "
                f"then re-run. url={page.url}"
            )

        loc = find_composer(page)
        _fill_locator(page, loc, text)
        page.wait_for_timeout(400)
        if screenshot_path is not None:
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot_path), full_page=False)
        # Do not browser.close(): this is a CDP attach; Chrome must stay open with the draft.
        return FillTarget(hwnd=0, title=page.url)


def _dump_landmarks(win) -> None:
    from ui.windows import _text, user32

    kids = _enum_child_hwnds(win.hwnd)
    print(f"child hwnds {len(kids)}", flush=True)
    for h, cls in kids[:16]:
        title = _text(user32.GetWindowTextW, h, 80)
        print(f"  hwnd={h} cls={cls!r} title={title!r}", flush=True)
    roots = _uia_roots(win)
    print(f"uia roots {len(roots)}", flush=True)
    tabs = list_inbox_tabs(win)
    print(f"inbox tabs {len(tabs)}", flush=True)
    for tab in tabs:
        print(
            f"  tab {tab['index']} selected={tab['selected']} "
            f"cls={tab['class']!r} names={tab['names']} @({tab['cx']},{tab['cy']})",
            flush=True,
        )
    stream = _session_stream(win, allow_point=True)
    if stream is None:
        print("stream: not found", flush=True)
    else:
        try:
            kids_n = len(list(stream.GetChildren()))
        except Exception:
            kids_n = -1
        print(f"stream class={_ctrl_class(stream)!r} kids={kids_n}", flush=True)
        try:
            for i, ch in enumerate(list(stream.GetChildren())[:12]):
                names = _named_texts(ch)[:6]
                print(
                    f"  kid {i:02d} cls={_ctrl_class(ch)!r} names={names}",
                    flush=True,
                )
        except Exception as exc:
            print(f"  stream kids err {exc}", flush=True)
    wrap = _find_message_wrap(win)
    print(f"wrap class={_ctrl_class(wrap)!r}" if wrap is not None else "wrap: not found", flush=True)
    try:
        editor, cx, cy = _find_editor_content(win)
        print(f"editor class={_ctrl_class(editor)!r} click=({cx},{cy})", flush=True)
    except Exception as exc:
        print(f"editor: {exc}", flush=True)


def dump_live() -> int:
    """Print session list + current chat bubbles. Never fills, never sends."""
    from PIL import ImageGrab

    win = _find_live_dongdong_edge()
    if win is None:
        print(f"dongdong Edge window not found ({dongdong_missing_hint()})")
        return 1
    win = _prepare_live_edge(steal_focus=True)
    print(
        f"window hwnd={win.hwnd} vis={win.visible} {win.width}x{win.height} title={win.title}",
        flush=True,
    )
    _dump_landmarks(win)

    def _print_rows(label: str, rows: list[SessionRow]) -> None:
        print(f"{label} {len(rows)}", flush=True)
        for i, row in enumerate(rows[:30]):
            print(
                f"  {i:02d} unread={row.unread} {row.buyer_id!r} preview={row.preview!r} {row.time}",
                flush=True,
            )

    click_inbox_tab(win, 0)
    try:
        live_rows = list_live_sessions(win, steal_focus=False)
    except Exception as exc:
        print(f"tab 0 list failed: {exc}", flush=True)
        live_rows = []
    print(f"tab 0 groups={live_group_counts(win)}", flush=True)
    _print_rows("tab 0 live sessions", live_rows)

    click_inbox_tab(win, 1)
    try:
        hist_rows = list_live_sessions(win, steal_focus=False)
    except Exception as exc:
        print(f"tab 1 list failed: {exc}", flush=True)
        hist_rows = []
    _print_rows("tab 1 recent sessions", hist_rows)

    msgs = read_live_messages(win)
    print(f"messages {len(msgs)} header={read_live_header(win)!r}", flush=True)
    for msg in msgs[-16:]:
        body = (msg.text or "").replace("\n", " ")[:140]
        print(f"  {msg.role:9} {body}", flush=True)
    art = Path(__file__).resolve().parent.parent / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    left = (
        max(0, win.left),
        max(0, win.top + 70),
        min(1920, win.left + min(420, max(280, win.width // 4))),
        min(1080, win.bottom - 20),
    )
    bot = (
        max(0, win.left + int(win.width * 0.22)),
        max(0, win.top + int(win.height * 0.72)),
        min(1920, win.right - 8),
        min(1080, win.bottom - 4),
    )
    try:
        ImageGrab.grab(bbox=left).save(art / "dongdong-dump-recent.png")
    except Exception as exc:
        print(f"screenshot recent failed: {exc}", flush=True)
    click_inbox_tab(win, 0)
    try:
        ImageGrab.grab(bbox=left).save(art / "dongdong-dump-sessions.png")
        ImageGrab.grab(bbox=bot).save(art / "dongdong-dump-composer.png")
        print(
            "screenshots artifacts/dongdong-dump-sessions.png "
            "artifacts/dongdong-dump-recent.png artifacts/dongdong-dump-composer.png",
            flush=True,
        )
    except Exception as exc:
        print(f"screenshot failed: {exc}", flush=True)
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", nargs="?", default="dump", choices=["dump", "fill-all", "restore"])
    args = parser.parse_args()
    if args.cmd == "dump":
        raise SystemExit(dump_live())
    if args.cmd == "restore":
        raise SystemExit(restore_live_inbox())
    from pathlib import Path as _Path

    art = _Path(__file__).resolve().parent.parent / "artifacts"
    fill_openclaw_replies_all_sessions(art)
    raise SystemExit(0)

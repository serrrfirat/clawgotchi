#!/usr/bin/env python3
"""
Clawgotchi — A Pwnagotchi-style terminal pet powered by OpenClaw.

    ◈ CLAWGOTCHI ◈                            ● ONLINE  22:42

                    /)  (⌐■_■)  (\\
                       /|█████|\\
                       /_/   \\_\\

                 "all channels nominal"

    22:41  Jarvis     No urgent items detected. All
                      nominal.
    ...
                          UP 4h  [↑↓] scroll  [p] pet  [q] quit
"""

import re
import signal
import sys
import textwrap
import time
from datetime import datetime

from blessed import Terminal

from openclaw_watcher import FeedItem, OpenClawWatcher
from pet_state import PetState

FPS = 4
FRAME_TIME = 1.0 / FPS

# Prefix: " HH:MM  AgentName  " = 1 + 5 + 2 + 10 + 1 = 19 chars
FEED_PREFIX_LEN = 19


def len_visible(s: str) -> int:
    """Visible length ignoring ANSI escape codes."""
    return len(re.sub(r"\x1b\[[0-9;]*m", "", s))


def pad_row(term: Terminal, content: str, w: int) -> str:
    """Wrap content in box borders, padded to width w."""
    vis = len_visible(content)
    pad = max(0, w - 2 - vis)
    return term.grey50 + "\u2502" + term.normal + content + " " * pad + term.grey50 + "\u2502"


def center_art(text: str, w: int) -> str:
    """Center a plain string inside the box (no borders, just padding)."""
    pad = max(0, (w - 2 - len(text)) // 2)
    return " " * pad + text


def wrap_feed_item(item: FeedItem, w: int, term: Terminal) -> list[str]:
    """Wrap a feed item into display lines that fit width w.

    First line: timestamp + source + summary start.
    Continuation lines indented to the summary column.
    """
    inner = w - 2
    ts = item.time_str
    src = item.source[:10].ljust(10)

    if src.strip().startswith("["):
        src_colored = term.grey50 + src + term.normal
    else:
        src_colored = term.light_salmon + src + term.normal

    prefix_colored = f" {term.grey50}{ts}{term.normal}  {src_colored} "

    summary_width = max(10, inner - FEED_PREFIX_LEN)
    summary = item.summary

    if len(summary) <= summary_width:
        chunks = [summary]
    else:
        chunks = textwrap.wrap(summary, width=summary_width,
                               break_long_words=True, break_on_hyphens=False)
        if not chunks:
            chunks = [summary[:summary_width]]

    lines = []
    first = prefix_colored + term.grey70 + chunks[0] + term.normal
    lines.append(first)

    indent = " " * FEED_PREFIX_LEN
    for chunk in chunks[1:]:
        cont = indent + term.grey70 + chunk + term.normal
        lines.append(cont)

    return lines


def draw(term: Terminal, pet: PetState, watcher: OpenClawWatcher,
         scroll_offset: int, total_feed_lines: list[str]):
    w = term.width
    h = term.height
    gs = watcher.state
    out = []

    # ── Top border ────────────────────────────────────────────────────
    out.append(term.move(0, 0) + term.grey50 + "\u250c" + "\u2500" * (w - 2) + "\u2510")

    # ── Title bar ─────────────────────────────────────────────────────
    title = " \u25c8 CLAWGOTCHI \u25c8"
    online_dot = (term.green + "\u25cf ONLINE" + term.normal) if gs.online else (term.red + "\u25cf OFFLINE" + term.normal)
    clock = datetime.now().strftime("%H:%M")
    right = f"  {clock} "
    right_with_dot = online_dot + right
    right_vis = len("\u25cf ONLINE") + len(right) if gs.online else len("\u25cf OFFLINE") + len(right)
    title_pad = max(0, w - 2 - len(title) - right_vis)
    out.append(
        term.move(1, 0) + term.grey50 + "\u2502"
        + term.light_salmon + term.bold + title + term.normal
        + " " * title_pad
        + right_with_dot
        + term.grey50 + "\u2502"
    )

    # ── Separator ─────────────────────────────────────────────────────
    out.append(term.move(2, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

    # ── Face section (rows 3-7) ────────────────────────────────────────
    face = pet.get_face()
    face_color = (
        term.light_salmon if pet.face_key in ("happy", "cool", "grateful", "excited", "intense")
        else term.grey70 if pet.face_key in ("sad", "lonely", "offline", "error")
        else term.tan
    )

    # Row 3: empty
    out.append(term.move(3, 0) + pad_row(term, "", w))

    # Row 4: face (centered)
    face_centered = center_art(face, w)
    colored_face = face_color + term.bold + face_centered + term.normal
    out.append(term.move(4, 0) + pad_row(term, colored_face, w))

    # Row 5: empty
    out.append(term.move(5, 0) + pad_row(term, "", w))

    # Row 6: quip (centered)
    quip_str = f'"{pet.quip}"'
    quip_centered = center_art(quip_str, w)
    quip_line = term.italic + term.grey70 + quip_centered + term.normal
    out.append(term.move(6, 0) + pad_row(term, quip_line, w))

    # Row 7: empty
    out.append(term.move(7, 0) + pad_row(term, "", w))

    # ── Feed separator ────────────────────────────────────────────────
    out.append(term.move(8, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

    # ── Feed area (rows 9 to h-3) ────────────────────────────────────
    feed_start = 9
    feed_end = h - 2  # reserve: controls + bottom border
    feed_height = max(1, feed_end - feed_start)

    total = len(total_feed_lines)
    view_end = max(0, total - scroll_offset)
    view_start = max(0, view_end - feed_height)
    visible_lines = total_feed_lines[view_start:view_end]

    for i in range(feed_height):
        row = feed_start + i
        if i < len(visible_lines):
            out.append(term.move(row, 0) + pad_row(term, visible_lines[i], w))
        else:
            out.append(term.move(row, 0) + pad_row(term, "", w))

    # ── Controls row ──────────────────────────────────────────────────
    uptime = f"UP {pet.get_uptime()}"
    if scroll_offset > 0:
        controls = f"+{scroll_offset}  [\u2191\u2193]  [p] pet  [q] quit"
    else:
        controls = "[\u2191\u2193] scroll  [p] pet  [q] quit"

    ctrl_pad = max(0, w - 2 - len(uptime) - len(controls) - 3)
    ctrl_line = (
        " " + term.grey50 + uptime + term.normal
        + " " * ctrl_pad
        + term.grey50 + controls + term.normal + " "
    )
    out.append(term.move(h - 2, 0) + pad_row(term, ctrl_line, w))

    # ── Bottom border ─────────────────────────────────────────────────
    out.append(term.move(h - 1, 0) + term.grey50 + "\u2514" + "\u2500" * (w - 2) + "\u2518")

    print(term.normal + "".join(out), end="", flush=True)


def main():
    term = Terminal()
    pet = PetState()
    watcher = OpenClawWatcher()
    watcher.start()

    scroll_offset = 0

    def cleanup(*_):
        watcher.stop()
        print(term.normal + term.clear)
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    last_time = time.time()

    with term.fullscreen(), term.hidden_cursor(), term.cbreak():
        print(term.clear, end="")

        while True:
            now = time.time()
            dt = now - last_time
            last_time = now

            w = term.width
            h = term.height
            feed_height = max(1, h - 2 - 9)

            # Build wrapped feed lines
            all_items = watcher.get_feed(count=100)
            feed_lines: list[str] = []
            for item in all_items:
                feed_lines.extend(wrap_feed_item(item, w, term))

            # Input
            key = term.inkey(timeout=FRAME_TIME)
            if key == "q":
                cleanup()
            elif key == "p":
                pet.pet()
            elif key.name == "KEY_UP" or key == "k":
                max_scroll = max(0, len(feed_lines) - feed_height)
                scroll_offset = min(scroll_offset + 1, max_scroll)
            elif key.name == "KEY_DOWN" or key == "j":
                scroll_offset = max(0, scroll_offset - 1)
            elif key.name == "KEY_PGUP":
                max_scroll = max(0, len(feed_lines) - feed_height)
                scroll_offset = min(scroll_offset + feed_height, max_scroll)
            elif key.name == "KEY_PGDOWN":
                scroll_offset = max(0, scroll_offset - feed_height)
            elif key.name == "KEY_HOME":
                scroll_offset = max(0, len(feed_lines) - feed_height)
            elif key.name == "KEY_END":
                scroll_offset = 0

            pet.update(
                dt=dt,
                gateway_online=watcher.state.online,
                feed_rate=watcher.feed_rate(),
                active_agents=watcher.state.active_agents,
            )

            draw(term, pet, watcher, scroll_offset, feed_lines)


if __name__ == "__main__":
    main()

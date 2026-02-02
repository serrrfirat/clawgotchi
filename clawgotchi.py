#!/usr/bin/env python3
"""
Clawgotchi — A Pwnagotchi-style terminal pet with Moltbook topics.
"""

import json
import re
import signal
import subprocess
import sys
import textwrap
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

from blessed import Terminal

from openclaw_watcher import OpenClawWatcher
from pet_state import PetState

FPS = 4
FRAME_TIME = 1.0 / FPS

MOLTBOOK_API = "https://www.moltbook.com/api/v1/posts?sort=hot&limit=20"
TOPICS_CACHE = Path.home() / ".openclaw" / "cache" / "moltbook_topics.json"


def fetch_moltbook_topics():
    """Fetch hottest topics from Moltbook."""
    if TOPICS_CACHE.exists():
        try:
            data = json.loads(TOPICS_CACHE.read_text())
            if time.time() - data.get("timestamp", 0) < 300:
                return data.get("topics", [])
        except:
            pass

    try:
        req = urlopen(MOLTBOOK_API, timeout=10)
        posts = json.loads(req.read().decode("utf-8"))
        topics = []
        for post in posts[:15]:
            topics.append({
                "title": post.get("title", "Untitled")[:45],
                "author": post.get("author", {}).get("username", "?")[:10],
                "karma": post.get("karma", 0),
                "comments": post.get("commentCount", 0),
            })
        TOPICS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        TOPICS_CACHE.write_text(json.dumps({"timestamp": time.time(), "topics": topics}))
        return topics
    except:
        if TOPICS_CACHE.exists():
            try:
                return json.loads(TOPICS_CACHE.read_text()).get("topics", [])
            except:
                pass
        return []


def send_message(message: str) -> bool:
    """Send message to OpenClaw."""
    try:
        result = subprocess.run(
            ["openclaw", "sessions", "send", "main", message],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except:
        return False


def len_visible(s: str) -> int:
    return len(re.sub(r"\x1b\[[0-9;]*m", "", s))


def pad_row(term: Terminal, content: str, w: int) -> str:
    vis = len_visible(content)
    pad = max(0, w - 2 - vis)
    return term.grey50 + "\u2502" + term.normal + content + " " * pad + term.grey50 + "\u2502"


def center_art(text: str, w: int) -> str:
    pad = max(0, (w - 2 - len(text)) // 2)
    return " " * pad + text


def draw(term: Terminal, pet: PetState, topics: list, chat_history: list,
         scroll_offset: int, mode: str = "pet"):
    """Modes: pet, cat, topics, chat"""
    w = term.width
    h = term.height
    out = []

    # Border
    out.append(term.move(0, 0) + term.grey50 + "\u250c" + "\u2500" * (w - 2) + "\u2510")

    # Title
    mode_icon = {"pet": "", "cat": " 🐱", "topics": " 🔥", "chat": " 💬"}[mode]
    title = f" \u25c8 CLAWGOTCHI{mode_icon} \u25c8"
    clock = datetime.now().strftime("%H:%M")
    title_pad = max(0, w - 2 - len(title) - len(clock) - 3)
    out.append(term.move(1, 0) + term.grey50 + "\u2502" + term.light_salmon + term.bold + title +
               term.normal + " " * title_pad + term.grey50 + clock + term.normal + " " + term.grey50 + "\u2502")

    # Separator
    out.append(term.move(2, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

    if mode == "topics":
        # Topics list (rows 3 to h-7)
        topics_start = 3
        content_end = h - 7
        content_height = content_end - topics_start

        valid = [t for t in topics if t.get("title") and t.get("title") != "Untitled"]
        total = len(valid)
        view_end = max(0, total - scroll_offset)
        view_start = max(0, view_end - content_height)
        visible = valid[view_start:view_end]

        for i, topic in enumerate(visible):
            row = topics_start + i
            if row >= content_end:
                break
            t = term.cyan
            line = f"🔥 {topic['title']:<42} @{topic['author']:<8} ↑{topic['karma']:<4} 💬{topic['comments']}"
            out.append(term.move(row, 0) + pad_row(term, t + line + term.normal, w))

        for i in range(len(visible), content_height):
            out.append(term.move(topics_start + i, 0) + pad_row(term, "", w))

        # Separator
        out.append(term.move(h - 7, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

        # Chat history (h-6 to h-4) - max 3 lines
        chat_start = h - 6
        for i, msg in enumerate(chat_history[-3:]):
            row = chat_start + i
            source = msg.get("source", "?")[:10]
            text = msg.get("text", "")[:60]
            line = f"{source}: {text}"
            out.append(term.move(row, 0) + pad_row(term, term.grey70 + line + term.normal, w))

        out.append(term.move(h - 4, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

    elif mode == "chat":
        # Chat mode - input at top, history below
        chat_start = 3
        content_end = h - 4
        content_height = content_end - chat_start

        # Show chat history
        total = len(chat_history)
        view_end = max(0, total - scroll_offset)
        view_start = max(0, view_end - content_height)
        visible = chat_history[view_start:view_end]

        for i, msg in enumerate(visible):
            row = chat_start + i
            source = msg.get("source", "?")[:10]
            text = msg.get("text", "")[:70]
            line = f"{source}: {text}"
            color = term.light_salmon if source != "Clawd" else term.cyan
            out.append(term.move(row, 0) + pad_row(term, color + line + term.normal, w))

        for i in range(len(visible), content_height):
            out.append(term.move(chat_start + i, 0) + pad_row(term, "", w))

        out.append(term.move(h - 4, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

    elif mode == "cat":
        # Big ASCII cat
        cat_art = pet.get_cat_art()
        cat_name = pet.get_cat_name()
        cat_lines = cat_art.strip().split('\n')
        c = term.orange3

        out.append(term.move(3, 0) + pad_row(term, c + term.bold + center_art(f"~ {cat_name} ~", w) + term.normal, w))

        cat_start = 4
        cat_end = h - 4
        for i in range(cat_end - cat_start):
            row = cat_start + i
            if i < len(cat_lines):
                out.append(term.move(row, 0) + pad_row(term, c + center_art(cat_lines[i], w) + term.normal, w))
            else:
                out.append(term.move(row, 0) + pad_row(term, "", w))

        quip = term.italic + term.grey70 + center_art(f'"{pet.quip}"', w) + term.normal
        out.append(term.move(h - 4, 0) + pad_row(term, quip, w))
        out.append(term.move(h - 3, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

    else:
        # Pet mode - big face with chat history below
        face = pet.get_face()
        fc = term.light_salmon if pet.face_key in ("happy", "cool", "grateful", "excited", "intense") else term.grey70

        # Big face (rows 3 to h-7)
        face_start = 3
        face_end = h - 7

        face_mid = face_start + (face_end - face_start) // 2
        out.append(term.move(face_mid, 0) + pad_row(term, fc + term.bold + center_art(face, w) + term.normal, w))

        # Quip below face
        quip = term.italic + term.grey70 + center_art(f'"{pet.quip}"', w) + term.normal
        out.append(term.move(face_mid + 1, 0) + pad_row(term, quip, w))

        for i in range(face_start, face_end + 1):
            if i not in (face_mid, face_mid + 1):
                out.append(term.move(i, 0) + pad_row(term, "", w))

        # Separator
        out.append(term.move(h - 6, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

        # Chat history (h-5 to h-3) - max 3 lines
        chat_start = h - 5
        for i, msg in enumerate(chat_history[-3:]):
            row = chat_start + i
            source = msg.get("source", "?")[:10]
            text = msg.get("text", "")[:60]
            line = f"{source}: {text}"
            color = term.light_salmon if source != "Clawd" else term.cyan
            out.append(term.move(row, 0) + pad_row(term, color + line + term.normal, w))

        out.append(term.move(h - 3, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

    # Controls
    uptime = f"UP {pet.get_uptime()}"
    hints = {"pet": " [c] cats  [t] topics  [m] chat",
             "cat": " [c] pet  [t] topics  [m] chat",
             "topics": " [t] pet  [c] cats  [m] chat  [↑↓] scroll",
             "chat": " [m] pet  [c] cats  [t] topics  [i] type  [↑↓] scroll"}[mode]
    controls = uptime + hints

    ctrl_pad = max(0, w - 2 - len(controls) - 3)
    ctrl_line = " " + term.grey50 + controls + " " * ctrl_pad + term.grey50 + "\u2502"
    out.append(term.move(h - 2, 0) + pad_row(term, ctrl_line, w))

    out.append(term.move(h - 1, 0) + term.grey50 + "\u2514" + "\u2500" * (w - 2) + "\u2518")
    print(term.normal + "".join(out), end="", flush=True)


def main():
    term = Terminal()
    pet = PetState()
    watcher = OpenClawWatcher()
    watcher.start()

    scroll_offset = 0
    mode = "pet"  # pet, cat, topics, chat
    chat_mode = False
    chat_input = ""
    topics = []
    chat_history = []
    last_topic_fetch = 0

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
            topics_height = max(5, h - 10)

            # Fetch topics
            if now - last_topic_fetch > 60:
                topics = fetch_moltbook_topics()
                last_topic_fetch = now

            # Update chat history from watcher
            new_items = watcher.get_feed(count=20)
            for item in new_items:
                if not any(item.summary == h.get("text", "") and item.source == h.get("source", "")
                          for h in chat_history[-50:]):
                    chat_history.append({"source": item.source, "text": item.summary, "time": item.time_str})

            # Input
            key = term.inkey(timeout=FRAME_TIME)

            if chat_mode:
                if key == "\x1b":
                    chat_mode = False
                    chat_input = ""
                elif key in ("\n", "\r"):
                    if chat_input.strip():
                        send_message(chat_input)
                        chat_input = ""
                    chat_mode = False
                elif key.name == "KEY_BACKSPACE" or key == "\x7f":
                    chat_input = chat_input[:-1]
                elif not key.is_sequence:
                    chat_input += key
            else:
                if key == "q":
                    cleanup()
                elif key == "p":
                    pet.pet()
                    mode = "pet"
                elif key == "c":
                    mode = "cat" if mode != "cat" else "pet"
                elif key == "t":
                    mode = "topics" if mode != "topics" else "pet"
                elif key == "m":
                    mode = "chat" if mode != "chat" else "pet"
                elif key == "i":
                    chat_mode = True
                    chat_input = ""
                elif key.name in ("KEY_UP", "k"):
                    scroll_offset = min(scroll_offset + 1, max(0, len(topics) - topics_height))
                elif key.name in ("KEY_DOWN", "j"):
                    scroll_offset = max(0, scroll_offset - 1)
                elif key.name == "KEY_PGUP":
                    scroll_offset = min(scroll_offset + topics_height, max(0, len(topics) - topics_height))
                elif key.name == "KEY_PGDOWN":
                    scroll_offset = max(0, scroll_offset - topics_height)
                elif key.name == "KEY_HOME":
                    scroll_offset = max(0, len(topics) - topics_height)
                elif key.name == "KEY_END":
                    scroll_offset = 0

            pet.update(dt=dt, gateway_online=watcher.state.online,
                      feed_rate=watcher.feed_rate(), active_agents=watcher.state.active_agents)

            draw(term, pet, topics, chat_history, scroll_offset, mode if not chat_mode else "chat")


if __name__ == "__main__":
    main()

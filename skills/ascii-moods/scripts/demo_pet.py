#!/usr/bin/env python3
"""Render a single pet-mode frame to stdout for screenshots/recordings."""

import json
import re
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from config import DATA_DIR

# ── Load ASCII moods ──────────────────────────────────────────────────

data = json.loads((DATA_DIR / "ascii_moods.json").read_text())
moods = {}
durations = {}
for name, info in data.get("moods", {}).items():
    colored = [f["colored_lines"] for f in info["frames"] if f.get("colored_lines")]
    durs = [f.get("duration_ms", 100) for f in info["frames"]]
    if colored:
        moods[name] = colored
        durations[name] = durs

# ── Terminal helpers ──────────────────────────────────────────────────

RESET = "\033[0m"
GREY50 = "\033[38;5;244m"
GREY70 = "\033[38;5;249m"
SALMON = "\033[38;5;209m"
CYAN = "\033[38;5;80m"
BOLD = "\033[1m"
ITALIC = "\033[3m"


def len_visible(s: str) -> int:
    return len(re.sub(r"\x1b\[[0-9;]*m", "", s))


def center_art(text: str, w: int) -> str:
    vis = len_visible(text) if "\x1b" in text else len(text)
    pad = max(0, (w - 2 - vis) // 2)
    return " " * pad + text


def pad_row(content: str, w: int) -> str:
    vis = len_visible(content)
    pad = max(0, w - 2 - vis)
    return GREY50 + "\u2502" + RESET + content + " " * pad + GREY50 + "\u2502" + RESET


def draw_pet_frame(mood: str, frame_idx: int, w: int = 60, h: int = 30):
    """Draw a single pet-mode frame to stdout."""
    frames = moods.get(mood)
    if not frames:
        return
    frame = frames[frame_idx % len(frames)]
    lines = []

    # Top border
    lines.append(GREY50 + "\u250c" + "\u2500" * (w - 2) + "\u2510" + RESET)

    # Title bar
    title = f" \u25c8 CLAWGOTCHI \u25c8"
    clock = time.strftime("%H:%M")
    mood_label = mood.upper()[:4]
    bar_w = 8
    bar = CYAN + "\u2588" * 5 + GREY50 + "\u2591" * (bar_w - 5) + RESET
    meter = GREY70 + " " + mood_label + " " + bar + RESET
    meter_vis = len(mood_label) + 1 + bar_w + 1
    gap = max(0, w - 2 - len(title) - len(clock) - meter_vis)
    title_line = (GREY50 + "\u2502" + SALMON + BOLD + title + RESET +
                  meter + " " * gap + GREY50 + clock + RESET + GREY50 + "\u2502" + RESET)
    lines.append(title_line)

    # Separator
    lines.append(GREY50 + "\u251c" + "\u2500" * (w - 2) + "\u2524" + RESET)

    # Face area
    face_start = 3
    face_end = h - 11
    if face_end <= face_start:
        face_end = face_start + 1
    area_height = face_end - face_start

    art_height = len(frame)
    art_top = max(0, (area_height - art_height - 1) // 2)

    quips = {
        "happy": "life is good on the wire",
        "grateful": "thanks for chatting with me!",
        "cool": "just another day being awesome",
        "excited": "NEW MESSAGE NEW MESSAGE!!",
        "thinking": "processing...",
        "lonely": "anyone there?",
        "sad": "the silence is deafening",
        "bored": "*yawn*",
        "sleeping": "dreaming of electric shrimp",
        "intense": "MAXIMUM THROUGHPUT",
        "confused": "wait what just happened?",
        "listening": "i'm all ears... er, antennae",
        "speaking": "generating response...",
        "shy": "everyone's looking at me!",
        "curious": "ooh, interesting!",
        "proud": "look what i made!",
        "error": "something went wrong!",
        "offline": "waiting for connection",
    }
    quip = quips.get(mood, "...")

    for i in range(area_height):
        art_i = i - art_top
        if 0 <= art_i < art_height:
            centered = center_art(frame[art_i], w)
            lines.append(pad_row(centered + RESET, w))
        elif art_i == art_height:
            q = ITALIC + GREY70 + center_art(f'"{quip}"', w) + RESET
            lines.append(pad_row(q, w))
        else:
            lines.append(pad_row("", w))

    # Vitals strip
    lines.append(GREY50 + "\u251c " + RESET +
                 "\U0001f49a 92%\u2191 \u2502 \U0001f9e0 3 \u2502 \U0001f445 12 \u2502 \u2705 85%" +
                 GREY50 + " " + "\u2500" * max(0, w - 38) + "\u2524" + RESET)

    # Goal + Thought
    lines.append(pad_row(CYAN + " \U0001f3af explore moltbook curiosity queue" + RESET, w))
    lines.append(pad_row(GREY70 + " \U0001f4ad should i check for new patterns?" + RESET, w))

    # Separator
    lines.append(GREY50 + "\u251c" + "\u2500" * (w - 2) + "\u2524" + RESET)

    # Activity feed (4 lines)
    feed = [
        (SALMON, "gateway: heartbeat OK"),
        (CYAN, "Clawd: exploring topic 'async patterns'"),
        (SALMON, "moltbook: new post in /m/security"),
        (CYAN, "Clawd: curiosity matured - investigating"),
    ]
    for color, text in feed:
        lines.append(pad_row(color + text[:w - 4] + RESET, w))

    # Bottom separator
    lines.append(GREY50 + "\u251c" + "\u2500" * (w - 2) + "\u2524" + RESET)

    # Controls
    uptime = "UP 2h 31m"
    hints = " [s] skills  [m] chat  [d] dash  [p] pet"
    handle = "u/the-clawgotchi"
    ctrl_pad = max(0, w - 2 - len(uptime) - len(hints) - len(handle) - 3)
    ctrl = (" " + GREY50 + uptime + hints + " " * ctrl_pad +
            CYAN + handle + GREY50 + " \u2502" + RESET)
    lines.append(pad_row(ctrl, w))

    # Bottom border
    lines.append(GREY50 + "\u2514" + "\u2500" * (w - 2) + "\u2518" + RESET)

    print("\033[H\033[2J", end="")  # clear
    print("\n".join(lines), flush=True)


def main():
    mood = sys.argv[1] if len(sys.argv) > 1 else "happy"
    if mood not in moods:
        print(f"Unknown mood: {mood}. Available: {', '.join(moods.keys())}")
        sys.exit(1)

    frames = moods[mood]
    durs = durations.get(mood, [100] * len(frames))

    # Animate: loop through all frames a few times
    loops = max(1, 180 // len(frames))  # ~180 frames worth
    for _ in range(loops):
        for i in range(len(frames)):
            draw_pet_frame(mood, i)
            delay = max(0.03, durs[i % len(durs)] / 1000.0)
            time.sleep(delay)


if __name__ == "__main__":
    main()

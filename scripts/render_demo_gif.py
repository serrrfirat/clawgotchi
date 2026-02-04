#!/usr/bin/env python3
"""Render the pet TUI as an animated GIF using Pillow."""

import json
import re
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR

# ── Config ────────────────────────────────────────────────────────────

W_CHARS = 60
H_LINES = 30
FONT_SIZE = 14
CHAR_W = int(FONT_SIZE * 0.6) + 1  # monospace char width
CHAR_H = FONT_SIZE + 4
BG_COLOR = (30, 30, 46)  # Catppuccin Mocha base
DEFAULT_FG = (205, 214, 244)  # Catppuccin text
GREY50 = (108, 112, 134)
GREY70 = (166, 173, 200)
SALMON = (243, 139, 168)
CYAN = (137, 220, 235)

# Load fonts — Menlo for text, Apple Braille for braille chars
FONT = None
BRAILLE_FONT = None
for name in ["Menlo.ttc", "Monaco.dfont", "Courier New.ttf",
             "DejaVuSansMono.ttf", "Consolas.ttf"]:
    for base in [Path("/System/Library/Fonts"), Path("/Library/Fonts"),
                 Path("/usr/share/fonts/truetype/dejavu")]:
        p = base / name
        if p.exists():
            try:
                FONT = ImageFont.truetype(str(p), FONT_SIZE)
                break
            except Exception:
                continue
    if FONT:
        break
if not FONT:
    FONT = ImageFont.load_default()

for p in [Path("/System/Library/Fonts/Apple Braille.ttf"),
          Path("/System/Library/Fonts/Supplemental/Apple Braille.ttf")]:
    if p.exists():
        try:
            BRAILLE_FONT = ImageFont.truetype(str(p), FONT_SIZE)
            break
        except Exception:
            continue


def is_braille(ch: str) -> bool:
    return '\u2800' <= ch <= '\u28ff'


def pick_font(ch: str):
    if is_braille(ch) and BRAILLE_FONT:
        return BRAILLE_FONT
    return FONT

# ── Load moods ────────────────────────────────────────────────────────

data = json.loads((DATA_DIR / "ascii_moods.json").read_text())
moods_colored = {}
moods_durations = {}
for name, info in data.get("moods", {}).items():
    colored = [f["colored_lines"] for f in info["frames"] if f.get("colored_lines")]
    durs = [f.get("duration_ms", 100) for f in info["frames"]]
    if colored:
        moods_colored[name] = colored
        moods_durations[name] = durs

# ── ANSI parsing ──────────────────────────────────────────────────────

ANSI_RE = re.compile(r"\x1b\[([0-9;]*)m")


def parse_ansi_line(line: str):
    """Yield (char, (r, g, b)) tuples from an ANSI-colored line."""
    fg = DEFAULT_FG
    pos = 0
    for m in ANSI_RE.finditer(line):
        # Text before this escape
        text = line[pos:m.start()]
        for ch in text:
            yield ch, fg
        # Parse the escape
        codes = m.group(1).split(";") if m.group(1) else ["0"]
        if codes == ["0"]:
            fg = DEFAULT_FG
        elif len(codes) == 5 and codes[0] == "38" and codes[1] == "2":
            try:
                fg = (int(codes[2]), int(codes[3]), int(codes[4]))
            except ValueError:
                pass
        pos = m.end()
    # Remaining text
    for ch in line[pos:]:
        yield ch, fg


def len_visible(s: str) -> int:
    return len(re.sub(r"\x1b\[[0-9;]*m", "", s))


def center_vis(text: str, w: int) -> str:
    vis = len_visible(text) if "\x1b" in text else len(text)
    pad = max(0, (w - 2 - vis) // 2)
    return " " * pad + text


# ── Frame builder ─────────────────────────────────────────────────────

def build_frame_lines(mood: str, frame_idx: int) -> list:
    """Build the TUI as a list of (line_str_with_ansi, default_fg) tuples."""
    frames = moods_colored[mood]
    frame = frames[frame_idx % len(frames)]
    w = W_CHARS
    h = H_LINES
    lines = []

    def plain(text, fg=GREY50):
        return (text, fg)

    # Top border
    lines.append(plain("\u250c" + "\u2500" * (w - 2) + "\u2510"))

    # Title
    title = " \u25c8 CLAWGOTCHI \u25c8"
    clock = time.strftime("%H:%M")
    gap = max(0, w - 2 - len(title) - len(clock))
    lines.append(plain("\u2502" + title + " " * gap + clock + "\u2502"))

    # Sep
    lines.append(plain("\u251c" + "\u2500" * (w - 2) + "\u2524"))

    # Face area
    face_start = 3
    face_end = h - 11
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
            # ANSI colored art line — mark as "ansi"
            centered = center_vis(frame[art_i], w)
            lines.append(("ansi:" + "\u2502" + centered, None))
        elif art_i == art_height:
            q_text = f'"{quip}"'
            pad = max(0, (w - 2 - len(q_text)) // 2)
            lines.append(plain("\u2502" + " " * pad + q_text + " " * max(0, w - 2 - pad - len(q_text)) + "\u2502", GREY70))
        else:
            lines.append(plain("\u2502" + " " * (w - 2) + "\u2502"))

    # Vitals strip
    vitals = "\u251c HP 92%\u2191  \u2502 Q 3  \u2502 T 12  \u2502 A 85%  " + "\u2500" * max(0, w - 40) + "\u2524"
    lines.append(plain(vitals))

    # Goal + Thought
    goal = "\u2502 \U0001f3af explore moltbook curiosity queue" + " " * max(0, w - 40) + "\u2502"
    thought = "\u2502 \U0001f4ad should i check for new patterns?" + " " * max(0, w - 40) + "\u2502"
    lines.append(plain(goal, CYAN))
    lines.append(plain(thought, GREY70))

    # Sep
    lines.append(plain("\u251c" + "\u2500" * (w - 2) + "\u2524"))

    # Feed
    feed = [
        ("gateway: heartbeat OK", SALMON),
        ("Clawd: exploring topic 'async patterns'", CYAN),
        ("moltbook: new post in /m/security", SALMON),
        ("Clawd: curiosity matured - investigating", CYAN),
    ]
    for text, color in feed:
        padded = text[:w - 4]
        lines.append(plain("\u2502 " + padded + " " * max(0, w - 3 - len(padded)) + "\u2502", color))

    # Sep
    lines.append(plain("\u251c" + "\u2500" * (w - 2) + "\u2524"))

    # Controls
    ctrl = " UP 2h 31m [s] skills [m] chat [d] dash [p] pet"
    lines.append(plain("\u2502" + ctrl + " " * max(0, w - 2 - len(ctrl)) + "\u2502", GREY50))

    # Bottom
    lines.append(plain("\u2514" + "\u2500" * (w - 2) + "\u2518"))

    return lines


def render_image(lines: list) -> Image.Image:
    """Render lines to a Pillow Image."""
    img_w = W_CHARS * CHAR_W + 20  # padding
    img_h = len(lines) * CHAR_H + 20
    img = Image.new("RGB", (img_w, img_h), BG_COLOR)
    draw = ImageDraw.Draw(img)
    x_off = 10
    y_off = 10

    for row, (text, default_fg) in enumerate(lines):
        y = y_off + row * CHAR_H
        if text.startswith("ansi:"):
            raw = text[5:]
            x = x_off
            # Draw border char first
            draw.text((x, y), raw[0], fill=GREY50, font=FONT)
            x += CHAR_W
            # Parse rest with per-char color
            ansi_part = raw[1:]
            for ch, color in parse_ansi_line(ansi_part):
                draw.text((x, y), ch, fill=color, font=pick_font(ch))
                x += CHAR_W
            # Close border
            remaining = W_CHARS - 1 - len_visible(ansi_part)
            x_end = x + max(0, remaining) * CHAR_W
            draw.text((x_end, y), "\u2502", fill=GREY50, font=FONT)
        else:
            fg = default_fg or DEFAULT_FG
            x = x_off
            for ch in text:
                if ch in "\u250c\u2500\u2510\u2502\u251c\u2524\u2514\u2518":
                    draw.text((x, y), ch, fill=GREY50, font=FONT)
                else:
                    draw.text((x, y), ch, fill=fg, font=pick_font(ch))
                x += CHAR_W

    return img


def main():
    mood = sys.argv[1] if len(sys.argv) > 1 else "happy"
    if mood not in moods_colored:
        print(f"Unknown mood: {mood}. Available: {', '.join(moods_colored.keys())}")
        sys.exit(1)

    out_path = Path(__file__).resolve().parent.parent / "assets" / "demo_pet.gif"

    frames_data = moods_colored[mood]
    durs = moods_durations.get(mood, [100] * len(frames_data))
    n = len(frames_data)
    loops = max(1, 60 // n)  # enough frames for a few seconds

    print(f"Rendering {mood}: {n} frames x {loops} loops = {n * loops} total")
    images = []
    frame_durations = []

    for loop in range(loops):
        for i in range(n):
            lines = build_frame_lines(mood, i)
            img = render_image(lines)
            images.append(img)
            frame_durations.append(max(30, durs[i % len(durs)]))
        print(f"  loop {loop + 1}/{loops} done")

    print(f"Saving GIF to {out_path} ...")
    images[0].save(
        out_path,
        save_all=True,
        append_images=images[1:],
        duration=frame_durations,
        loop=0,
        optimize=True,
    )
    size_kb = out_path.stat().st_size / 1024
    print(f"Done! {out_path} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()

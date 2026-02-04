#!/usr/bin/env python3
"""Generate ASCII art mood animations from Tenor cat GIFs.

Run with ascii_maker's venv:
    /Users/firatsertgoz/Documents/ascii_maker/.venv/bin/python \
        skills/ascii-moods/scripts/generate_moods.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add ascii_maker to import path
sys.path.insert(0, str(Path.home() / "Documents" / "ascii_maker"))

from ascii_maker.core.reader import open_media
from ascii_maker.core.processor import process_frame, Settings
from ascii_maker.core.charsets import CharsetName
from ascii_maker.core.color import ColorMode

# ── Settings ──────────────────────────────────────────────────────────

MAX_FRAMES = 64
ASCII_WIDTH = 40
ASCII_HEIGHT = 12

SETTINGS = Settings(
    charset=CharsetName.BRAILLE,
    color_mode=ColorMode.TRUECOLOR,
    dither=True,
    brightness=0,
    contrast=100,
    invert=False,
    width=ASCII_WIDTH,
    height=ASCII_HEIGHT,
)

# ── Curated Tenor GIF URLs (direct CDN links) ────────────────────────

TENOR_URLS = {
    "happy": "https://media.tenor.com/1SXIh2VpnhQAAAAj/cat.gif",
    "grateful": "https://media.tenor.com/qoLatyHHBkgAAAAj/meong-cat.gif",
    "cool": "https://media1.tenor.com/m/JAZzfZupTTcAAAAC/gil-cat.gif",
    "excited": "https://media.tenor.com/Ec-7QKfHZMgAAAAi/jump-up.gif",
    "thinking": "https://media.tenor.com/JFu3-alzcf0AAAAi/peach-goma.gif",
    "lonely": "https://media.tenor.com/SHu3aMt_2CYAAAAi/%E0%B9%82%E0%B8%94%E0%B8%94%E0%B9%80%E0%B8%94%E0%B8%B5%E0%B9%88%E0%B8%A2%E0%B8%A7-lonely.gif",
    "sad": "https://media.tenor.com/uf4rihPX8ScAAAAi/happy-labour-day.gif",
    "bored": "https://media.tenor.com/Rz8ZfJUj_O8AAAAi/waiting-bored.gif",
    "sleeping": "https://media.tenor.com/lGCUA-L5gi0AAAAi/goma-sleep.gif",
    "intense": "https://media1.tenor.com/m/li4RaKl6PpoAAAAd/cat-drinking-cat-drinking-water.gif",
    "confused": "https://media1.tenor.com/m/kZrteNCDoHAAAAAC/cat-cat-turning-head.gif",
    "listening": "https://media.tenor.com/2aSuT7p_a_UAAAAi/peachcat-cat.gif",
    "speaking": "https://media.tenor.com/n9pGkaQF0ocAAAAi/schmooda.gif",
    "shy": "https://media.tenor.com/BBS_EGuWfVsAAAAi/peach-shy.gif",
    "curious": "https://media.tenor.com/QUSMUwP4DX4AAAAi/plink-cat-blink.gif",
    "proud": "https://media.tenor.com/rWxbLNAJEpwAAAAi/hump-proud.gif",
    "error": "https://media.tenor.com/6f7jyh-p-OsAAAAi/blub-blub-coin.gif",
    "offline": "https://media.tenor.com/C7qUq8vEEygAAAAC/cat-waiting.gif",
}

# ── Output path ───────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
OUTPUT_FILE = PROJECT_ROOT / "data" / "ascii_moods.json"


def sample_frames(frames: list, max_n: int) -> list:
    """Sample evenly-spaced frames down to max_n."""
    if len(frames) <= max_n:
        return frames
    step = len(frames) / max_n
    return [frames[int(i * step)] for i in range(max_n)]


def generate_mood(emotion: str, url: str) -> dict | None:
    """Process a single Tenor GIF into ASCII frames."""
    print(f"  [{emotion}] downloading {url}")
    try:
        reader = open_media(url)
    except Exception as e:
        print(f"  [{emotion}] FAILED to open: {e}")
        return None

    raw_frames = list(reader.frames())
    if not raw_frames:
        print(f"  [{emotion}] no frames found")
        return None

    sampled = sample_frames(raw_frames, MAX_FRAMES)
    print(f"  [{emotion}] {len(raw_frames)} frames -> {len(sampled)} sampled")

    ascii_frames = []
    for frame in sampled:
        processed = process_frame(frame, SETTINGS)
        # Pad plain lines to exact width
        lines = []
        for line in processed.lines:
            if len(line) < ASCII_WIDTH:
                line = line + " " * (ASCII_WIDTH - len(line))
            elif len(line) > ASCII_WIDTH:
                line = line[:ASCII_WIDTH]
            lines.append(line)
        while len(lines) < ASCII_HEIGHT:
            lines.append(" " * ASCII_WIDTH)

        # Colored lines (with ANSI escapes) — same count, already correct width
        colored = list(processed.colored_lines[:ASCII_HEIGHT])
        while len(colored) < ASCII_HEIGHT:
            colored.append(" " * ASCII_WIDTH)

        ascii_frames.append({
            "lines": lines,
            "colored_lines": colored,
            "duration_ms": frame.duration_ms,
        })

    return {
        "frames": ascii_frames,
        "frame_count": len(ascii_frames),
        "source_url": url,
    }


def main():
    print(f"Generating ASCII moods -> {OUTPUT_FILE}")
    print(f"Settings: {ASCII_WIDTH}x{ASCII_HEIGHT}, charset=braille, truecolor, dither")
    print()

    moods = {}
    failed = []

    for emotion, url in TENOR_URLS.items():
        result = generate_mood(emotion, url)
        if result:
            moods[emotion] = result
        else:
            failed.append(emotion)

    output = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "settings": {
            "charset": "braille",
            "color_mode": "truecolor",
            "dither": True,
            "width": ASCII_WIDTH,
            "height": ASCII_HEIGHT,
        },
        "moods": moods,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))

    file_size = OUTPUT_FILE.stat().st_size
    print()
    print(f"Done! {len(moods)} moods generated, {len(failed)} failed")
    if failed:
        print(f"Failed: {', '.join(failed)}")
    print(f"Output: {OUTPUT_FILE} ({file_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()

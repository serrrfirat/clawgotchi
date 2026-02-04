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

MAX_FRAMES = 8
ASCII_WIDTH = 40
ASCII_HEIGHT = 12

SETTINGS = Settings(
    charset=CharsetName.SIMPLE,
    color_mode=ColorMode.NONE,
    dither=False,
    brightness=0,
    contrast=100,
    invert=False,
    width=ASCII_WIDTH,
    height=ASCII_HEIGHT,
)

# ── Curated Tenor GIF URLs (direct CDN links) ────────────────────────

TENOR_URLS = {
    "happy": "https://media.tenor.com/bFdcfUkgSk8AAAAC/happy-cat.gif",
    "grateful": "https://media.tenor.com/GryShwZXsRMAAAAC/thank-you-cat.gif",
    "cool": "https://media.tenor.com/Wsi1MAoE5y0AAAAC/cool-cat.gif",
    "excited": "https://media.tenor.com/on2GxLDlcikAAAAC/cat-excited.gif",
    "thinking": "https://media.tenor.com/MYZgsN2TDJAAAAAC/thinking-cat.gif",
    "lonely": "https://media.tenor.com/6ExvCbk5HbUAAAAC/sad-cat.gif",
    "sad": "https://media.tenor.com/TqxfP2EGsFcAAAAC/crying-cat.gif",
    "bored": "https://media.tenor.com/mlKdp6M4TssAAAAC/bored-cat.gif",
    "sleeping": "https://media.tenor.com/Ow7oBePxqMgAAAAC/sleeping-cat.gif",
    "intense": "https://media.tenor.com/c4Cg4BfI_mMAAAAC/intense-cat.gif",
    "confused": "https://media.tenor.com/rG8dN0MqZJIAAAAC/confused-cat.gif",
    "listening": "https://media.tenor.com/3TGh0FUk9m0AAAAC/cat-listening.gif",
    "speaking": "https://media.tenor.com/WgmOpmqVXRoAAAAC/talking-cat.gif",
    "shy": "https://media.tenor.com/R0gMiaNGMBEAAAAC/shy-cat.gif",
    "curious": "https://media.tenor.com/0AVv1oJSXjYAAAAC/curious-cat.gif",
    "proud": "https://media.tenor.com/gnRSK_yL85IAAAAC/proud-cat.gif",
    "error": "https://media.tenor.com/cXxwJMPW_LAAAAAC/shocked-cat.gif",
    "offline": "https://media.tenor.com/euMOB4d3TzcAAAAC/cat-waiting.gif",
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
        # Pad each line to exact width
        lines = []
        for line in processed.lines:
            if len(line) < ASCII_WIDTH:
                line = line + " " * (ASCII_WIDTH - len(line))
            elif len(line) > ASCII_WIDTH:
                line = line[:ASCII_WIDTH]
            lines.append(line)
        # Pad to exact height
        while len(lines) < ASCII_HEIGHT:
            lines.append(" " * ASCII_WIDTH)

        ascii_frames.append({
            "lines": lines,
            "duration_ms": frame.duration_ms,
        })

    return {
        "frames": ascii_frames,
        "frame_count": len(ascii_frames),
        "source_url": url,
    }


def main():
    print(f"Generating ASCII moods -> {OUTPUT_FILE}")
    print(f"Settings: {ASCII_WIDTH}x{ASCII_HEIGHT}, charset=simple, no color")
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
            "charset": "simple",
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

---
name: ascii-moods
description: Use this skill to generate or regenerate ASCII art mood animations
  for Clawgotchi. Converts cat GIFs from Tenor into animated ASCII frames using
  ascii_maker, producing data/ascii_moods.json that drives the TUI face display.
---

# ASCII Moods

Converts cat emotion GIFs from Tenor into multi-line animated ASCII art for the TUI pet face.

## How It Works

1. `scripts/generate_moods.py` downloads curated Tenor GIFs for each of 18 emotions
2. Each GIF is processed through `ascii_maker` to produce plain-text ASCII frames
3. Output is written to `data/ascii_moods.json`
4. The TUI loads this JSON at startup and renders animated multi-line faces

## Running the Generator

Requires `ascii_maker`'s venv (has PIL/numpy/cv2):

```bash
/Users/firatsertgoz/Documents/ascii_maker/.venv/bin/python \
  skills/ascii-moods/scripts/generate_moods.py
```

## Output Format

`data/ascii_moods.json` contains frames for each emotion. Each frame is a list of 12 strings, each 40 chars wide. The TUI reads this at startup with zero additional runtime dependencies.

## Regenerating

To update the ASCII art (e.g. after finding better GIFs), edit `TENOR_URLS` in the generation script and re-run.

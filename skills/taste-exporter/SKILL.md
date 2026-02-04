---
name: taste-exporter
description: Export clawgotchi's taste profile and rejection ledger. Use when reviewing what clawgotchi has rejected, understanding preferences, or generating taste signature visualizations.
---

# Taste Exporter

Export and visualize clawgotchi's taste profile.

## Commands

```bash
python3 skills/taste-exporter/scripts/export.py --markdown    # Export as markdown
python3 skills/taste-exporter/scripts/export.py --json        # Export as JSON
python3 skills/taste-exporter/scripts/export.py --signature  # Show ASCII signature
python3 skills/taste-exporter/scripts/export.py --stats      # Show statistics
```

## Output Formats

| Format | Description |
|--------|-------------|
| `--markdown` | Human-readable markdown report |
| `--json` | Machine-readable JSON |
| `--signature` | ASCII art taste signature |
| `--stats` | Rejection statistics |

## Files Exported

- `memory/taste_profile.json` - Taste preferences
- `memory/taste_rejections.jsonl` - Rejection ledger

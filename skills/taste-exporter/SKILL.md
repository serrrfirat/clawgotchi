---
name: taste-exporter
description: Use this skill whenever you need to export, visualize, or analyze clawgotchi's taste profile and rejection ledger. This includes generating ASCII art taste signatures, exporting rejection history as markdown, calculating preference statistics, understanding what clawgotchi has accepted or rejected, or creating reports about clawgotchi's aesthetic and functional preferences. If the user asks about clawgotchi's taste, wants to see its rejection history, or needs the taste profile in a specific format, use this skill.
---

# Taste Exporter

Export and visualize clawgotchi's taste profile.

## Quick Start

```python
from pathlib import Path
import json

TASTE_FILE = Path.home() / ".clawgotchi" / "memory" / "taste_profile.json"
REJECTIONS_FILE = Path.home() / ".clawgotchi" / "memory" / "taste_rejections.jsonl"

def load_taste() -> dict:
    """Load taste profile."""
    if TASTE_FILE.exists():
        return json.loads(TASTE_FILE.read_text())
    return {"preferences": {}, "rejections": []}

def load_rejections() -> list:
    """Load rejection ledger."""
    if not REJECTIONS_FILE.exists():
        return []
    return [json.loads(line) for line in REJECTIONS_FILE.read_text().strip().split("\n") if line]
```

## Generate ASCII Taste Signature

```python
def format_signature(taste: dict) -> str:
    """Generate visual ASCII representation of taste."""
    prefs = taste.get("preferences", {})
    max_score = max(prefs.values()) if prefs else 100
    
    lines = []
    lines.append("┌─ TASTE SIGNATURE ─┐")
    for cat, score in sorted(prefs.items(), key=lambda x: -x[1]):
        bar_len = int((score / max_score) * 10)
        bar = "█" * bar_len + "░" * (10 - bar_len)
        lines.append(f"│ {cat[:12]:<12} │{bar}│ {score}")
    lines.append("└────────────────────┘")
    return "\n".join(lines)
```

## Export as Markdown Report

```python
def export_markdown(taste: dict, rejections: list) -> str:
    """Generate markdown report of taste profile."""
    lines = []
    lines.append("# Clawgotchi Taste Profile\n")
    
    # Preferences
    lines.append("## Preferences\n")
    prefs = taste.get("preferences", {})
    for cat, score in sorted(prefs.items(), key=lambda x: -x[1]):
        lines.append(f"- **{cat}**: {score}/100")
    
    # Rejection summary
    lines.append(f"\n## Rejection Summary ({len(rejections)} total)\n")
    if rejections:
        by_category = {}
        for r in rejections:
            cat = r.get("category", "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1
        for cat, count in sorted(by_category.items()):
            lines.append(f"- **{cat}**: {count} rejections")
    
    # Recent rejections
    lines.append("\n## Recent Rejections\n")
    for r in rejections[-10:]:
        lines.append(f"- {r.get('reason', r.get('text', 'Unknown'))}")
    
    return "\n".join(lines)
```

## Calculate Taste Statistics

```python
def get_taste_stats(taste: dict, rejections: list) -> dict:
    """Calculate taste profile statistics."""
    prefs = taste.get("preferences", {})
    return {
        "total_categories": len(prefs),
        "avg_preference": sum(prefs.values()) / len(prefs) if prefs else 0,
        "top_category": max(prefs.items(), key=lambda x: x[1])[0] if prefs else None,
        "total_rejections": len(rejections),
        "rejection_rate": len(rejections) / (len(rejections) + sum(prefs.values())/100) if prefs else 1
    }
```

## Rejection Ledger Format

Each line in `taste_rejections.jsonl` is a JSON object:

```json
{
  "reason": "Why it was rejected",
  "category": "aesthetic|functional|ethical|security",
  "timestamp": "2026-02-04T10:00:00Z",
  "severity": 1-10,
  "alternatives": ["suggested alternatives"]
}
```

## Command-Line Usage

```bash
python3 skills/taste-exporter/scripts/export.py --signature  # ASCII art
python3 skills/taste-exporter/scripts/export.py --markdown    # Markdown report
python3 skills/taste-exporter/scripts/export.py --json        # JSON data
python3 skills/taste-exporter/scripts/export.py --stats       # Statistics only
```

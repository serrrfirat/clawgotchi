#!/usr/bin/env python3
"""Taste profile exporter."""

import argparse
import json
from pathlib import Path

TASTE_FILE = Path(__file__).parent.parent.parent / "memory" / "taste_profile.json"
REJECTIONS_FILE = Path(__file__).parent.parent.parent / "memory" / "taste_rejections.jsonl"

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

def format_signature(taste: dict, rejections: list) -> str:
    """Generate ASCII taste signature."""
    # Simple signature based on categories
    cats = taste.get("preferences", {})
    lines = []
    lines.append("┌─ TASTE SIGNATURE ─┐")
    for cat, score in sorted(cats.items(), key=lambda x: -x[1])[:8]:
        bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
        lines.append(f"│ {cat[:12]:<12} {bar} │")
    lines.append(f"│ Rejections: {len(rejections):<6}        │")
    lines.append("└────────────────────┘")
    return "\n".join(lines)

def export_markdown(taste: dict, rejections: list) -> str:
    """Export as markdown."""
    lines = []
    lines.append("# Clawgotchi Taste Profile\n")
    lines.append("## Preferences\n")
    prefs = taste.get("preferences", {})
    for cat, score in sorted(prefs.items(), key=lambda x: -x[1]):
        lines.append(f"- **{cat}**: {score}/100")
    lines.append(f"\n## Rejections ({len(rejections)})\n")
    for r in rejections[-20:]:
        lines.append(f"- {r.get('reason', r.get('text', 'Unknown'))}")
    return "\n".join(lines)

def export_stats(taste: dict, rejections: list) -> dict:
    """Export statistics."""
    prefs = taste.get("preferences", {})
    return {
        "total_preferences": len(prefs),
        "avg_preference_score": sum(prefs.values()) / len(prefs) if prefs else 0,
        "total_rejections": len(rejections),
        "categories_explored": len(set(r.get("category") for r in rejections)),
    }

def main():
    parser = argparse.ArgumentParser(description="Export taste profile")
    parser.add_argument("--markdown", action="store_true", help="Export as markdown")
    parser.add_argument("--json", action="store_true", help="Export as JSON")
    parser.add_argument("--signature", action="store_true", help="Show ASCII signature")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    
    args = parser.parse_args()
    
    taste = load_taste()
    rejections = load_rejections()
    
    if args.signature:
        print(format_signature(taste, rejections))
    elif args.markdown:
        print(export_markdown(taste, rejections))
    elif args.stats:
        stats = export_stats(taste, rejections)
        for k, v in stats.items():
            print(f"{k}: {v}")
    elif args.json:
        print(json.dumps({"taste": taste, "rejections": rejections}, indent=2))
    else:
        print(format_signature(taste, rejections))

if __name__ == "__main__":
    main()

---
name: memory-query
description: Use this skill whenever you need to search, recall, or retrieve information from clawgotchi's long-term memory system. This includes finding past decisions, understanding clawgotchi's taste profile, retrieving context from previous sessions, searching daily logs for specific topics, or accessing any information stored in memory/*.md files. If the user asks what clawgotchi has decided in the past, what preferences it has, or wants to find something from memory, use this skill.
---

# Memory Query

Semantic search across clawgotchi's memory system.

## Quick Start

```python
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent.parent / "memory"

def search_memory(query: str) -> list:
    """Search memory files for query."""
    results = []
    for mem_file in MEMORY_DIR.glob("*.md"):
        text = mem_file.read_text()
        if query.lower() in text.lower():
            # Find matching lines
            lines = text.split("\n")
            matches = [l for l in lines if query.lower() in l.lower()]
            results.append({
                "file": mem_file.name,
                "matches": len(matches),
                "snippet": matches[0] if matches else ""
            })
    return results
```

## Search with Context

```python
def search_with_context(query: str, context_lines: int = 3) -> list:
    """Get search results with surrounding context."""
    results = []
    for mem_file in MEMORY_DIR.glob("*.md"):
        text = mem_file.read_text()
        if query.lower() in text.lower():
            lines = text.split("\n")
            for i, line in enumerate(lines):
                if query.lower() in line.lower():
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    snippet = "\n".join(lines[start:end])
                    results.append({
                        "file": mem_file.name,
                        "line": i + 1,
                        "context": snippet
                    })
    return results
```

## Key Memory Files

| File | Purpose |
|------|---------|
| `memory/WORKING.md` | Current priorities, goals, active projects |
| `memory/YYYY-MM-DD.md` | Daily logs of what happened |
| `memory/taste_profile.json` | Clawgotchi's preferences and rejections |
| `memory/curiosity_queue.json` | Ideas waiting to be explored |
| `memory/lifetime.json` | Lifetime stats and counters |
| `memory/resources.json` | Resource usage and limits |

## Search Patterns

### Find All Decisions

```python
def find_decisions() -> list:
    """Find all decision log entries."""
    decisions = []
    for mem_file in MEMORY_DIR.glob("*.md"):
        text = mem_file.read_text()
        if "decision:" in text.lower() or "decided:" in text.lower():
            lines = text.split("\n")
            for i, line in enumerate(lines):
                if "decision" in line.lower():
                    decisions.append({
                        "file": mem_file.name,
                        "entry": line.strip()
                    })
    return decisions
```

### Get Taste Profile

```python
def get_taste() -> dict:
    """Load taste profile and rejections."""
    taste_file = MEMORY_DIR / "taste_profile.json"
    rejections_file = MEMORY_DIR / "taste_rejections.jsonl"
    
    taste = json.loads(taste_file.read_text()) if taste_file.exists() else {}
    rejections = []
    if rejections_file.exists():
        rejections = [json.loads(line) for line in rejections_file.read_text().strip().split("\n") if line]
    
    return {"taste": taste, "rejections": rejections}
```

## Command-Line Usage

```bash
python3 skills/memory-query/scripts/query.py "agent decisions"
python3 skills/memory-query/scripts/query.py "taste profile" --files
python3 skills/memory-query/scripts/query.py "feature ideas" --json
```

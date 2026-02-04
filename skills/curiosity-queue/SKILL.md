---
name: curiosity-queue
description: Use this skill whenever you need to view, manage, or interact with clawgotchi's curiosity-driven exploration queue. This includes listing pending curiosities, adding new ideas to explore, marking curiosities as complete, prioritizing exploration items, or reviewing what clawgotchi wants to investigate next. If the user asks what's on clawgotchi's mind, what ideas are waiting to be explored, or wants to add something to the curiosity queue, use this skill.
---

# Curiosity Queue

Manage clawgotchi's curiosity-driven exploration queue.

## Quick Start

```python
from pathlib import Path
import json

QUEUE_FILE = Path.home() / ".clawgotchi" / "memory" / "curiosity_queue.json"

def load_queue() -> dict:
    """Load curiosity queue."""
    if not QUEUE_FILE.exists():
        return {"curiosities": [], "next_id": 1}
    return json.loads(QUEUE_FILE.read_text())

def list_curiosities(status: str = None) -> list:
    """List curiosities, optionally filtered by status."""
    queue = load_queue()
    items = queue.get("curiosities", [])
    if status:
        items = [c for c in items if c.get("status") == status]
    return sorted(items, key=lambda x: -x.get("priority", 0))
```

## Add New Curiosity

```python
def add_curiosity(text: str, priority: int = 5, category: str = "general") -> dict:
    """Add a new curiosity to the queue."""
    queue = load_queue()
    curiosity = {
        "id": queue.get("next_id", 1),
        "text": text,
        "priority": priority,
        "category": category,
        "status": "pending",
        "created": datetime.now().isoformat()
    }
    queue["curiosities"].append(curiosity)
    queue["next_id"] = curiosity["id"] + 1
    QUEUE_FILE.write_text(json.dumps(queue, indent=2))
    return curiosity
```

## Mark Complete

```python
def complete_curiosity(curiosity_id: int) -> bool:
    """Mark a curiosity as explored."""
    queue = load_queue()
    for c in queue.get("curiosities", []):
        if c["id"] == curiosity_id:
            c["status"] = "complete"
            c["completed"] = datetime.now().isoformat()
            QUEUE_FILE.write_text(json.dumps(queue, indent=2))
            return True
    return False
```

## Queue Structure

```json
{
  "curiosities": [
    {
      "id": 1,
      "text": "Explore X for potential feature",
      "priority": 7,
      "category": "feature",
      "status": "pending",
      "created": "2026-02-04T10:00:00Z",
      "explored": null
    }
  ],
  "next_id": 2
}
```

## Priority Levels

| Priority | Meaning |
|----------|---------|
| 1-3 | Low - nice to explore when idle |
| 4-6 | Medium - should explore soon |
| 7-10 | High - urgent exploration needed |

## Common Tasks

### Get Next Curiosity to Explore

```python
def get_next() -> dict:
    """Get highest priority pending curiosity."""
    pending = [c for c in list_curiosities("pending") if c.get("priority", 0) >= 5]
    return pending[0] if pending else None
```

### Get Curiosity Stats

```python
def get_stats() -> dict:
    """Get queue statistics."""
    queue = load_queue()
    items = queue.get("curiosities", [])
    return {
        "total": len(items),
        "pending": len([c for c in items if c.get("status") == "pending"]),
        "complete": len([c for c in items if c.get("status") == "complete"]),
        "avg_priority": sum(c.get("priority", 0) for c in items) / len(items) if items else 0
    }
```

## Command-Line Usage

```bash
python3 skills/curiosity-queue/scripts/queue.py --list          # Show all
python3 skills/curiosity-queue/scripts/queue.py --next          # Top priority
python3 skills/curiosity-queue/scripts/queue.py --add "idea"    # Add new
python3 skills/curiosity-queue/scripts/queue.py --complete 1    # Mark done
```

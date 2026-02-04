---
name: curiosity-queue
description: View and manage clawgotchi's curiosity queue. Use when exploring what ideas clawgotchi wants to investigate, adding new curiosities, or reviewing pending explorations.
---

# Curiosity Queue

Manage clawgotchi's curiosity-driven exploration queue.

## Commands

```bash
python3 skills/curiosity-queue/scripts/queue.py --list          # Show all curiosities
python3 skills/curiosity-queue/scripts/queue.py --next          # Get top priority
python3 skills/curiosity-queue/scripts/queue.py --add "idea"    # Add new curiosity
python3 skills/curiosity-queue/scripts/queue.py --complete ID   # Mark as explored
```

## Queue Format

```json
{
  "curiosities": [
    {"id": 1, "text": "Explore X", "priority": 5, "status": "pending"}
  ]
}
```

## Priority Levels

- 1-3: Low priority (nice to explore)
- 4-6: Medium priority
- 7-10: High priority (urgent exploration)

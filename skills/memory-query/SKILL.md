---
name: memory-query
description: Semantic search of clawgotchi's memory files. Use when recalling past decisions, finding context from previous sessions, or searching for specific topics in long-term memory.
---

# Memory Query

Semantic search across clawgotchi's memory system.

## Quick Search

```bash
python3 skills/memory-query/scripts/query.py "agent decisions"
python3 skills/memory-query/scripts/query.py "taste profile" --files
python3 skills/memory-query/scripts/query.py "feature ideas" --json
```

## Commands

| Flag | Description |
|------|-------------|
| `--files` | List matching files only |
| `--json` | Output as JSON |
| `--context N` | Include N lines of context |

## Memory Locations

- `memory/WORKING.md` - Current priorities
- `memory/YYYY-MM-DD.md` - Daily logs
- `memory/taste_profile.json` - Taste rejections
- `memory/curiosity_queue.json` - Ideas to explore

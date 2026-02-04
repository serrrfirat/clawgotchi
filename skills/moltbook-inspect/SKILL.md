---
name: moltbook-inspect
description: Browse and search Moltbook posts from clawgotchi's autonomous agent network. Use when exploring what agents are discussing, finding inspiration for features, or curating interesting posts.
---

# Moltbook Inspect

Browse clawgotchi's cached Moltbook posts.

## Quick Search

```bash
python3 skills/moltbook-inspect/scripts/inspect.py --recent 10
python3 skills/moltbook-inspect/scripts/inspect.py --search "autonomy"
python3 skills/moltbook-inspect/scripts/inspect.py --author "agent-name"
```

## Commands

| Command | Description |
|---------|-------------|
| `--recent N` | Show N most recent posts |
| `--search TERM` | Search posts by keyword |
| `--author NAME` | Filter by author |
| `--format json\|text` | Output format |
| `--cache PATH` | Override cache file |

## Integration

 clawgotchi calls this skill automatically when exploring Moltbook for feature ideas.

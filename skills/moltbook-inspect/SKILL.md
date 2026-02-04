---
name: moltbook-inspect
description: Use this skill whenever you need to browse, search, or explore Moltbook posts from clawgotchi's autonomous agent network. This includes finding inspiration for new features, discovering what other agents are discussing, curating interesting posts for later, analyzing trends in agent discourse, or retrieving context from clawgotchi's cached Moltbook feed. If the user asks about what agents are talking about, what's trending in Moltbook, or wants to find posts matching certain topics, use this skill.
---

# Moltbook Inspect

Browse and search clawgotchi's cached Moltbook posts.

## Quick Start

```python
from pathlib import Path
import json

# Load cached posts
cache = Path.home() / ".openclaw" / "cache" / "moltbook_posts.json"
data = json.loads(cache.read_text())
posts = data.get("posts", [])

# Get recent posts
for post in posts[:10]:
    print(f"[{post.get('author', '?')}] {post.get('title', 'Untitled')}")
```

## Find Posts by Search Term

```python
posts = load_posts()
search_term = "autonomy"
matches = [
    p for p in posts 
    if search_term in (p.get("title", "") + " " + p.get("content", "")).lower()
]
```

## Filter by Author

```python
posts = load_posts()
author_posts = [p for p in posts if "agent-name" in p.get("author", "").lower()]
```

## Get Post with Full Context

```python
def get_post_detail(post_id: str) -> dict:
    """Retrieve full post with submolts."""
    posts = load_posts()
    for p in posts:
        if p.get("id") == post_id:
            return {
                "title": p.get("title"),
                "author": p.get("author"),
                "content": p.get("content", "")[:500],
                "submolts": p.get("submolts", []),
                "replies": p.get("replies", 0),
                "timestamp": p.get("created_at")
            }
    return None
```

## Common Tasks

### Extract Feature Ideas from Posts

```python
posts = load_posts()
feature_keywords = ["build", "create", "tool", "cli", "command", "feature"]

ideas = []
for p in posts:
    title = p.get("title", "").lower()
    if any(kw in title for kw in feature_keywords):
        ideas.append({
            "title": p.get("title"),
            "author": p.get("author"),
            "url": p.get("url")
        })
```

### Count Posts by Author

```python
from collections import Counter

posts = load_posts()
authors = [p.get("author", "unknown") for p in posts]
top_authors = Counter(authors).most_common(10)
```

## Output Formats

| Format | When to Use |
|--------|-------------|
| `--recent N` | Show N most recent posts |
| `--search "term"` | Find posts matching keyword |
| `--author "name"` | Filter by author |
| `--json` | Machine-readable output |
| `--text` | Human-readable (default) |

## Cache Location

```
~/.openclaw/cache/moltbook_posts.json
```

Updates automatically every 4 hours during clawgotchi's heartbeat.

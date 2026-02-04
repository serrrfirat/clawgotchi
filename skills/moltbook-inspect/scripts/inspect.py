#!/usr/bin/env python3
"""Moltbook post inspector."""

import argparse
import json
from pathlib import Path

CACHE_PATH = Path.home() / ".openclaw" / "cache" / "moltbook_posts.json"

def load_posts(path: Path = None) -> list:
    """Load cached Moltbook posts."""
    p = path or CACHE_PATH
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
        return data.get("posts", data.get("items", []))
    except Exception as e:
        print(f"Error loading posts: {e}", file=sys.stderr)
        return []

def format_post(post: dict, idx: int = None) -> str:
    """Format a single post."""
    lines = []
    if idx is not None:
        lines.append(f"[{idx}]")
    lines.append(f"ID: {post.get('id', '?')}")
    lines.append(f"Title: {post.get('title', 'Untitled')}")
    lines.append(f"Author: {post.get('author', post.get('username', '?'))}")
    if post.get("submolts"):
        lines.append(f"Submolts: {len(post['submolts'])}")
    if post.get("content"):
        content = post["content"][:200]
        lines.append(f"Content: {content}...")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Inspect Moltbook posts")
    parser.add_argument("--recent", type=int, default=10, help="Show N recent posts")
    parser.add_argument("--search", type=str, default="", help="Search by keyword")
    parser.add_argument("--author", type=str, default="", help="Filter by author")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--cache", type=Path, help="Override cache path")
    
    args = parser.parse_args()
    
    posts = load_posts(args.cache)
    
    # Filter
    if args.author:
        posts = [p for p in posts if args.author.lower() in (p.get("author", "") or p.get("username", "")).lower()]
    
    if args.search:
        term = args.search.lower()
        posts = [p for p in posts if term in (p.get("title", "") + " " + p.get("content", "")).lower()]
    
    # Limit
    posts = posts[:args.recent]
    
    if args.format == "json":
        print(json.dumps(posts, indent=2))
    else:
        for i, post in enumerate(posts):
            print("-" * 40)
            print(format_post(post, i + 1))
        print(f"\n{len(posts)} posts shown")

if __name__ == "__main__":
    import sys
    main()

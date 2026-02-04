#!/usr/bin/env python3
"""Moltbook CLI for Clawgotchi — fetch and display posts from Moltbook."""

import argparse
import json
import sys
import textwrap
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from moltbook_client import (
    fetch_feed, fetch_comments, post_update,
    get_my_profile, get_cached_posts, extract_feature_ideas
)


def format_comment_for_terminal(comment: dict, index: int = None) -> str:
    """Format a single comment for terminal display."""
    content = comment.get("content", "")[:100]
    author = comment.get("author", {}).get("name", "?") if isinstance(comment.get("author"), dict) else comment.get("author", "?")
    upvotes = comment.get("upvotes", 0)
    
    if index is not None:
        return f"[{index:2}] 💬 {content}...\n    by @{author} | {upvotes}↑"
    else:
        return f"💬 {content}...\n    by @{author} | {upvotes}↑"


def format_post_for_terminal(post: dict, index: int = None) -> str:
    """Format a single post for terminal display."""
    title = post.get("title", "Untitled")[:60]
    author = post.get("author", {}).get("name", "?")
    karma = post.get("upvotes", 0)
    comments = post.get("comment_count", 0)
    submolt = post.get("submolt", {}).get("name", "") if isinstance(post.get("submolt"), dict) else ""
    created_at = post.get("created_at", "")
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            created_at = dt.strftime("%m/%d %H:%M")
        except:
            created_at = ""
    
    if index is not None:
        return f"[{index:2}] 📰 {title}\n    by @{author} | {karma}↑ | {comments}💬 | #{submolt} | {created_at}"
    else:
        return f"📰 {title}\n    by @{author} | {karma}↑ | {comments}💬 | #{submolt} | {created_at}"


def cmd_feed(args):
    """Display Moltbook feed."""
    limit = getattr(args, "limit", 20)
    show_karma = getattr(args, "karma", False)
    
    print("Fetching Moltbook feed...")
    posts = fetch_feed(limit=limit)
    
    if not posts:
        print("No posts found or API error.")
        return 1
    
    print(f"\nLatest posts from Moltbook ({len(posts)} posts):\n")
    
    for i, post in enumerate(posts, 1):
        print(format_post_for_terminal(post, i))
    
    if show_karma:
        total_karma = sum(p.get("upvotes", 0) for p in posts)
        print(f"\nTotal karma in feed: {total_karma}")
    
    return 0


def cmd_inspire(args):
    """Show feature inspiration from Moltbook."""
    limit = getattr(args, "limit", 50)
    
    print("Scanning Moltbook for inspiration...")
    posts = fetch_feed(limit=limit)
    
    if not posts:
        print("No posts found.")
        return 1
    
    ideas = extract_feature_ideas(posts)
    
    if not ideas:
        print("No feature ideas found matching our interests.")
        return 0
    
    print(f"\n{len(ideas)} feature ideas found:\n")
    for idea in ideas[:10]:
        print(f"  - {idea['title'][:50]}")
        print(f"    by @{idea['author']} | {idea['karma']} upvotes")
        print(f"    Reason: {idea['reason']}")
        print()
    
    return 0


def cmd_profile(args):
    """Show your Moltbook profile."""
    print("Fetching your profile...")
    profile = get_my_profile()
    
    if "error" in profile:
        print(f"Error: {profile['error']}")
        return 1
    
    name = profile.get("name", "?")
    posts_count = profile.get("posts_count", 0)
    karma = profile.get("karma", 0)
    
    print(f"""
=== YOUR PROFILE ===
Username: @{name}
Posts:    {posts_count}
Karma:    {karma}
===================
""")
    return 0


def cmd_cache(args):
    """Show cached posts."""
    posts = get_cached_posts()
    
    if not posts:
        print("No cached posts. Run 'clawgotchi moltbook feed' first.")
        return 0
    
    print(f"Cached posts ({len(posts)}):\n")
    for i, post in enumerate(posts[:10], 1):
        print(format_post_for_terminal(post, i))
    
    if len(posts) > 10:
        print(f"  ... and {len(posts) - 10} more")
    
    return 0


def cmd_comments(args):
    """Show comments on a post."""
    post_id = getattr(args, "post_id", None)
    
    if not post_id:
        print("Error: Post ID required. Usage: moltbook comments <post_id>")
        return 1
    
    print(f"Fetching comments for post {post_id}...")
    comments = fetch_comments(post_id)
    
    if not comments:
        print("No comments found or API error.")
        return 1
    
    print(f"\nComments ({len(comments)}):\n")
    
    for i, comment in enumerate(comments, 1):
        print(format_comment_for_terminal(comment, i))
        print()
    
    return 0


def main(args=None):
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Clawgotchi Moltbook CLI - Interact with the Moltbook community",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  clawgotchi moltbook feed              Show latest posts
  clawgotchi moltbook feed --limit 50   Show 50 posts
  clawgotchi moltbook inspire           Find feature ideas
  clawgotchi moltbook profile           Show your profile
  clawgotchi moltbook cache             Show cached posts
  clawgotchi moltbook comments <post_id> Show comments on a post
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # feed command
    feed_parser = subparsers.add_parser("feed", help="Show Moltbook feed")
    feed_parser.add_argument("--limit", type=int, default=20, help="Number of posts to show")
    feed_parser.add_argument("--karma", action="store_true", help="Show total karma")
    
    # inspire command
    inspire_parser = subparsers.add_parser("inspire", help="Find feature ideas from feed")
    inspire_parser.add_argument("--limit", type=int, default=50, help="Posts to scan")
    
    # profile command
    subparsers.add_parser("profile", help="Show your Moltbook profile")
    
    # cache command
    subparsers.add_parser("cache", help="Show cached posts")
    
    # comments command
    comments_parser = subparsers.add_parser("comments", help="Show comments on a post")
    comments_parser.add_argument("post_id", help="Post ID to show comments for")
    
    parsed_args = parser.parse_args(args)
    
    if parsed_args.command == "feed":
        return cmd_feed(parsed_args)
    elif parsed_args.command == "inspire":
        return cmd_inspire(parsed_args)
    elif parsed_args.command == "profile":
        return cmd_profile(parsed_args)
    elif parsed_args.command == "cache":
        return cmd_cache(parsed_args)
    elif parsed_args.command == "comments":
        return cmd_comments(parsed_args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

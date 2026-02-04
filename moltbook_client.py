"""Moltbook integration for Clawgotchi — read, learn, and share."""

import json
import os
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

CREDENTIALS_PATH = Path(__file__).parent / ".moltbook.json"
CACHE_DIR = Path.home() / ".openclaw" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

POSTS_CACHE = CACHE_DIR / "moltbook_posts.json"
COMMENTS_CACHE = CACHE_DIR / "moltbook_comments.json"


def get_api_key() -> str:
    """Load Moltbook API key from credentials file."""
    if CREDENTIALS_PATH.exists():
        data = json.loads(CREDENTIALS_PATH.read_text())
        return data.get("api_key", "")
    # Fallback to env var
    return os.environ.get("MOLTBOOK_API_KEY", "")


def make_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Make an authenticated request to Moltbook API."""
    api_key = get_api_key()
    if not api_key:
        return {"error": "No API key found"}

    url = f"https://www.moltbook.com/api/v1{endpoint}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        if method == "GET":
            req = Request(url, headers=headers)
        else:
            req = Request(url, data=json.dumps(data or {}).encode(), headers=headers)
            req.get_method = lambda: method

        with urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as e:
        return {"error": str(e)}


def fetch_feed(limit: int = 20) -> list:
    """Fetch latest posts from Moltbook."""
    result = make_request(f"/posts?sort=new&limit={limit}")
    if "error" in result:
        return []
    
    posts = result if isinstance(result, list) else result.get("posts", [])
    
    # Cache posts
    POSTS_CACHE.write_text(json.dumps({
        "timestamp": time.time(),
        "posts": posts,
    }))
    
    return posts


def fetch_post(post_id: str) -> dict:
    """Fetch a single post with content."""
    return make_request(f"/posts/{post_id}")


def fetch_comments(post_id: str) -> list:
    """Fetch comments on a post."""
    result = make_request(f"/posts/{post_id}/comments?sort=top&limit=10")
    comments = result if isinstance(result, list) else result.get("comments", [])
    
    # Cache comments
    COMMENTS_CACHE.write_text(json.dumps({
        "timestamp": time.time(),
        "post_id": post_id,
        "comments": comments,
    }))
    
    return comments


def post_update(title: str, content: str, submolt: str = "general") -> dict:
    """Post an update to Moltbook."""
    return make_request("/posts", method="POST", data={
        "submolt": submolt,
        "title": title,
        "content": content,
    })


def get_my_profile() -> dict:
    """Get your Moltbook profile."""
    return make_request("/agents/me")


def get_dm_requests() -> dict:
    """Check for DM requests."""
    return make_request("/agents/dm/check")


def extract_feature_ideas(posts: list) -> list:
    """Analyze posts for feature inspiration."""
    ideas = []
    keywords = ["terminal", "ui", "pet", "emotion", "face", "mood", "tui", "ascii", "autonomous", "self", "evolution"]
    
    for post in posts:
        title = (post.get("title") or "").lower()
        content = (post.get("content") or "").lower()
        text = f"{title} {content}"
        
        if any(kw in text for kw in keywords):
            ideas.append({
                "id": post.get("id"),
                "title": post.get("title"),
                "author": post.get("author", {}).get("name", "?"),
                "karma": post.get("upvotes", 0),
                "reason": f"Mentions: {[kw for kw in keywords if kw in text]}",
            })
    
    return ideas


def get_cached_posts() -> list:
    """Get cached posts."""
    if POSTS_CACHE.exists():
        try:
            data = json.loads(POSTS_CACHE.read_text())
            if time.time() - data.get("timestamp", 0) < 3600:  # 1 hour cache
                return data.get("posts", [])
        except:
            pass
    return []


def get_inspiration() -> str:
    """Get a random post for inspiration."""
    posts = get_cached_posts()
    if not posts:
        posts = fetch_feed(50)
    
    if not posts:
        return "No inspiration found on Moltbook today."
    
    # Pick a high-karma post
    top_post = max(posts, key=lambda p: p.get("upvotes", 0))
    
    return f"Trending: '{top_post.get('title')}' by @{top_post.get('author', {}).get('name', '?')} ({top_post.get('upvotes', 0)} karma)"

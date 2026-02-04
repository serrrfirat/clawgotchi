"""Moltbook integration for Clawgotchi — read, learn, and share."""

import json
import os
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

from config import MOLTBOOK_CREDENTIALS, OPENCLAW_CACHE
CREDENTIALS_PATH = MOLTBOOK_CREDENTIALS
CACHE_DIR = OPENCLAW_CACHE
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


# ---------------------------------------------------------------------------
# Relevance scoring — replaces crude keyword matching
# ---------------------------------------------------------------------------

RELEVANCE_CATEGORIES = {
    "memory_systems": {
        "keywords": ["memory", "forget", "decay", "archive", "curate", "retention"],
        "weight": 3,
        "composes_with": "MemoryDecayEngine, MemoryCuration",
    },
    "self_awareness": {
        "keywords": ["assumption", "belief", "verify", "confidence", "metacognit"],
        "weight": 3,
        "composes_with": "AssumptionTracker, Beliefs",
    },
    "identity": {
        "keywords": ["taste", "rejection", "identity", "fingerprint", "persona"],
        "weight": 2,
        "composes_with": "TasteProfile",
    },
    "agent_operations": {
        "keywords": ["autonomous", "wake", "cycle", "heartbeat", "health", "monitor"],
        "weight": 2,
        "composes_with": "AutonomousAgent, DailyMaintenance",
    },
    "safety": {
        "keywords": ["injection", "sanitiz", "redact", "sensitive", "credential"],
        "weight": 2,
        "composes_with": "SensitiveDataDetector",
    },
}

NOISE_SIGNALS = [
    "token", "airdrop", "subscribe", "giveaway", "nft mint",
    "free sol", "buy now", "limited time", "act fast",
    "chapter 1", "once upon", "fiction",
]


def score_post_relevance(post: dict) -> dict:
    """Score a Moltbook post for relevance to Clawgotchi's existing modules.

    Returns a dict with:
        score       – float 0.0-1.0 (higher = more relevant)
        categories  – list of matched category names
        noise       – bool, True if spam/fiction signals detected
        detail      – human-readable breakdown
    """
    title = (post.get("title") or "").lower()
    content = (post.get("content") or "").lower()
    text = f"{title} {content}"

    # --- noise check ---
    noise = any(signal in text for signal in NOISE_SIGNALS)

    # --- category matching ---
    raw_score = 0
    max_possible = 0
    matched_categories = []

    for cat_name, cat in RELEVANCE_CATEGORIES.items():
        max_possible += cat["weight"]
        hits = sum(1 for kw in cat["keywords"] if kw in text)
        if hits:
            raw_score += cat["weight"] * min(hits, 3) / 3  # diminishing returns
            matched_categories.append(cat_name)

    # --- karma bonus (small) ---
    karma = post.get("upvotes", 0)
    if karma >= 10:
        raw_score += 0.5
        max_possible += 0.5
    elif karma >= 3:
        raw_score += 0.25
        max_possible += 0.25

    # --- noise penalty ---
    if noise:
        raw_score = max(0, raw_score - 5)

    # Normalise to 0.0-1.0
    score = round(raw_score / max_possible, 3) if max_possible else 0.0
    score = max(0.0, min(1.0, score))

    return {
        "score": score,
        "categories": matched_categories,
        "noise": noise,
        "detail": f"score={score}, cats={matched_categories}, noise={noise}",
    }


def extract_feature_ideas(posts: list) -> list:
    """Analyse posts for feature inspiration using relevance scoring.

    Only returns ideas that:
      - score >= 0.15
      - are not noise-flagged
      - match 2+ relevance categories
    Sorted by score descending.
    """
    ideas = []

    for post in posts:
        result = score_post_relevance(post)
        if result["noise"]:
            continue
        if result["score"] < 0.15:
            continue
        if len(result["categories"]) < 2:
            continue

        ideas.append({
            "id": post.get("id"),
            "title": post.get("title"),
            "author": post.get("author", {}).get("name", "?"),
            "karma": post.get("upvotes", 0),
            "score": result["score"],
            "categories": result["categories"],
            "reason": result["detail"],
        })

    ideas.sort(key=lambda x: x["score"], reverse=True)
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

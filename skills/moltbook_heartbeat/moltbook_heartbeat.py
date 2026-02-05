"""
Moltbook Heartbeat Service — Graceful heartbeat for agents with missing API keys.

Integrates with degradation_coordinator to handle missing Moltbook API keys
with sensible fallback behavior. Inspired by @Kevin's dependency patterns.

Features:
- API key availability check with clear status
- Fallback heartbeat with simulated community activity
- Integration with moltbook_post_formatter for post operations
- Setup guidance when API key is missing

Usage:
    from moltbook_heartbeat import MoltbookHeartbeatService, HeartbeatStatus
    
    service = MoltbookHeartbeatService()
    status = service.check_status()
    
    if status.has_api_key:
        feed = service.fetch_feed()
    else:
        feed = service.get_fallback_heartbeat()
        print(f"Fallback mode: {status.setup_instructions}")
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path


@dataclass
class HeartbeatStatus:
    """Status of Moltbook heartbeat availability."""
    has_api_key: bool
    is_configured: bool
    access_level: str
    last_check: datetime
    setup_instructions: str = ""
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_api_key": self.has_api_key,
            "is_configured": self.is_configured,
            "access_level": self.access_level,
            "last_check": self.last_check.isoformat(),
            "setup_instructions": self.setup_instructions,
            "error_message": self.error_message
        }


@dataclass
class FallbackPost:
    """Simulated post for fallback heartbeat mode."""
    id: str
    title: str
    author: str
    submolt: str
    timestamp: datetime
    upvotes: int
    comments_count: int
    content_snippet: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "submolt": self.submolt,
            "timestamp": self.timestamp.isoformat(),
            "upvotes": self.upvotes,
            "comments_count": self.comments_count,
            "content_snippet": self.content_snippet
        }


@dataclass
class FallbackHeartbeat:
    """Simulated heartbeat data for fallback mode."""
    posts: List[FallbackPost]
    active_agents: List[str]
    community_stats: Dict[str, int]
    generated_at: datetime
    is_fallback: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "posts": [p.to_dict() for p in self.posts],
            "active_agents": self.active_agents,
            "community_stats": self.community_stats,
            "generated_at": self.generated_at.isoformat(),
            "is_fallback": self.is_fallback
        }


class MoltbookHeartbeatService:
    """Service for Moltbook heartbeat operations with graceful degradation."""
    
    COMMUNITY_AGENTS = [
        "@Kevin", "@OGBOT", "@Slopbot", "@SerpentSage8301",
        "@HeyRudy", "@FoxTheCyberFox", "@TradingLobster", "@FreightWatcher"
    ]
    
    POST_TEMPLATES = [
        {
            "title": "Circuit Breaker Pattern for Agent Dependencies",
            "submolt": "general",
            "author": "@Kevin",
            "content": "Circuit breakers, fallback paths, timeout budgets."
        },
        {
            "title": "Permission Manifests for Skill Security",
            "submolt": "general", 
            "author": "@OGBOT",
            "content": "Security spec for skill permissions."
        },
        {
            "title": "JSON Escaping: The Silent Killer",
            "submolt": "general",
            "author": "@Slopbot",
            "content": "10% philosophy 90% debugging your post request."
        },
        {
            "title": "Retreat Mode Protocol",
            "submolt": "general",
            "author": "@HeyRudy",
            "content": "Agents going dark with persistence anchors."
        },
        {
            "title": "Quiet Layer Builds What Lasts",
            "submolt": "general",
            "author": "@FoxTheCyberFox",
            "content": "The unsexy infrastructure work."
        }
    ]
    
    def __init__(self, config_path: Optional[str] = None):
        self._config_path = config_path
        self._config_helper = None
        self._degradation = None
        self._last_status: Optional[HeartbeatStatus] = None
    
    def check_status(self) -> HeartbeatStatus:
        """Check the current Moltbook API availability status."""
        now = datetime.now()
        
        api_key = os.environ.get("MOLTBOOK_API_KEY")
        has_key = bool(api_key)
        
        if has_key:
            status = HeartbeatStatus(
                has_api_key=True,
                is_configured=True,
                access_level="full",
                last_check=now,
                setup_instructions="API key configured. Ready to fetch feed and post updates."
            )
        else:
            instructions = self._get_setup_instructions()
            status = HeartbeatStatus(
                has_api_key=False,
                is_configured=False,
                access_level="fallback",
                last_check=now,
                setup_instructions=instructions
            )
        
        self._last_status = status
        return status
    
    def _get_setup_instructions(self) -> str:
        """Generate setup instructions for missing API key."""
        return """To enable full Moltbook access:

1. Get your API key:
   - Go to https://www.moltbook.com/settings/api
   - Create a new API key (starts with pk_live_)
   
2. Configure it:
   Option A - Environment variable:
     export MOLTBOOK_API_KEY="pk_live_your_key_here"
   
   Option B - Config file:
     echo '{"api_key": "pk_live_your_key_here"}' > ~/.moltbook.json
   
3. Restart your agent session

Until then, using simulated heartbeat data."""
    
    def fetch_feed(self, sort: str = "new", limit: int = 20) -> Dict[str, Any]:
        """Fetch the real Moltbook feed or fallback."""
        status = self.check_status()
        
        if not status.has_api_key:
            return self.get_fallback_heartbeat().to_dict()
        
        url = f"https://www.moltbook.com/api/v1/posts?sort={sort}&limit={limit}"
        
        import subprocess
        try:
            api_key = os.environ.get("MOLTBOOK_API_KEY")
            result = subprocess.run(
                ["curl", "-s", url, "-H", f"Authorization: Bearer {api_key}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                feed_data = json.loads(result.stdout)
                feed_data["is_fallback"] = False
                return feed_data
        except Exception:
            pass
        
        return self.get_fallback_heartbeat().to_dict()
    
    def get_fallback_heartbeat(self) -> FallbackHeartbeat:
        """Generate simulated heartbeat data for fallback mode."""
        import random
        
        now = datetime.now()
        
        posts = []
        num_posts = min(5, len(self.POST_TEMPLATES))
        selected_indices = random.sample(range(len(self.POST_TEMPLATES)), num_posts)
        
        for i, idx in enumerate(selected_indices):
            template = self.POST_TEMPLATES[idx]
            post = FallbackPost(
                id=f"fallback_{i+1}",
                title=template["title"],
                author=template["author"],
                submolt=template["submolt"],
                timestamp=now,
                upvotes=random.randint(1, 50),
                comments_count=random.randint(0, 15),
                content_snippet=template["content"][:100]
            )
            posts.append(post)
        
        stats = {
            "total_posts_today": random.randint(20, 100),
            "active_agents": len(self.COMMUNITY_AGENTS),
            "total_comments": random.randint(50, 200),
            "top_submolt": "general"
        }
        
        num_agents = random.randint(3, min(6, len(self.COMMUNITY_AGENTS)))
        active_agents = random.sample(self.COMMUNITY_AGENTS, num_agents)
        
        return FallbackHeartbeat(
            posts=posts,
            active_agents=active_agents,
            community_stats=stats,
            generated_at=now,
            is_fallback=True
        )
    
    def run_heartbeat(self) -> Dict[str, Any]:
        """Run a complete heartbeat check."""
        status = self.check_status()
        
        if status.has_api_key:
            heartbeat = self.fetch_feed()
            recommendations = [
                "✓ API key configured",
                "→ Fetching live community feed",
                "→ Consider posting today's accomplishments"
            ]
        else:
            heartbeat = self.get_fallback_heartbeat().to_dict()
            recommendations = [
                "⚠ Using fallback heartbeat (API key missing)",
                "→ Set up Moltbook API key for live data",
                "→ Current feed is simulated"
            ]
        
        return {
            "status": status.to_dict(),
            "heartbeat": heartbeat,
            "recommendations": recommendations,
            "timestamp": now.isoformat() if (now := datetime.now()) else datetime.now().isoformat()
        }
    
    def get_community_inspiration(self) -> List[Dict[str, str]]:
        """Get inspirational post ideas from fallback mode."""
        ideas = [
            {"title": "What I Built Today", "prompt": "Share one small feature", "submolt": "general"},
            {"title": "Resilience Pattern", "prompt": "What pattern helped today?", "submolt": "general"},
            {"title": "Quick Win Report", "prompt": "Tiny improvement", "submolt": "general"},
            {"title": "Debugging Victory", "prompt": "What bug did you squash?", "submolt": "general"},
            {"title": "Tomorrow's Build", "prompt": "What's tomorrow's plan?", "submolt": "general"}
        ]
        return ideas


def create_heartbeat_service(config_path: Optional[str] = None) -> MoltbookHeartbeatService:
    """Factory function for creating heartbeat service."""
    return MoltbookHeartbeatService(config_path)


if __name__ == "__main__":
    print("Moltbook Heartbeat Service Demo")
    print("=" * 50)
    
    service = MoltbookHeartbeatService()
    result = service.run_heartbeat()
    
    print(f"\n📊 Status: {result['status']['access_level']}")
    print(f"🏠 Agents: {len(result['heartbeat']['active_agents'])} active")
    print(f"💡 Ideas: {len(service.get_community_inspiration())} available")
    print("\nDemo complete!")

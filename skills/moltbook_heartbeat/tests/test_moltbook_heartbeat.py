"""
Tests for Moltbook Heartbeat Service.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from moltbook_heartbeat import (
    MoltbookHeartbeatService,
    HeartbeatStatus,
    FallbackPost,
    FallbackHeartbeat,
    create_heartbeat_service,
)


class TestHeartbeatStatus:
    def test_status_full_access(self):
        status = HeartbeatStatus(
            has_api_key=True,
            is_configured=True,
            access_level="full",
            last_check=datetime.now(),
            setup_instructions="Ready!"
        )
        assert status.has_api_key is True
        assert status.access_level == "full"
    
    def test_status_fallback(self):
        status = HeartbeatStatus(
            has_api_key=False,
            is_configured=False,
            access_level="fallback",
            last_check=datetime.now(),
            setup_instructions="Get a key"
        )
        assert status.has_api_key is False
        assert status.access_level == "fallback"


class TestFallbackPost:
    def test_fallback_post_creation(self):
        post = FallbackPost(
            id="test_1",
            title="Test Post",
            author="@TestAgent",
            submolt="general",
            timestamp=datetime.now(),
            upvotes=10,
            comments_count=5,
            content_snippet="Test content"
        )
        assert post.id == "test_1"
        assert post.title == "Test Post"
    
    def test_fallback_post_to_dict(self):
        now = datetime.now()
        post = FallbackPost(
            id="1", title="Test", author="@Test",
            submolt="general", timestamp=now,
            upvotes=1, comments_count=0, content="test"
        )
        data = post.to_dict()
        assert data["id"] == "1"
        assert data["timestamp"] == now.isoformat()


class TestFallbackHeartbeat:
    def test_fallback_heartbeat_creation(self):
        posts = [FallbackPost(
            id="1", title="Test", author="@Test",
            submolt="general", timestamp=datetime.now(),
            upvotes=5, comments_count=2, content="test"
        )]
        heartbeat = FallbackHeartbeat(
            posts=posts,
            active_agents=["@Agent1"],
            community_stats={"total_posts": 10},
            generated_at=datetime.now()
        )
        assert len(heartbeat.posts) == 1
        assert heartbeat.is_fallback is True


class TestMoltbookHeartbeatService:
    def test_service_initialization(self):
        service = MoltbookHeartbeatService()
        assert service is not None
    
    def test_check_status_no_api_key(self):
        service = MoltbookHeartbeatService()
        with patch.dict(os.environ, {}, clear=False):
            # Remove API key if set
            os.environ.pop("MOLTBOOK_API_KEY", None)
            status = service.check_status()
            assert status.has_api_key is False or status.access_level in ("fallback", "unavailable")
    
    def test_get_fallback_heartbeat(self):
        service = MoltbookHeartbeatService()
        heartbeat = service.get_fallback_heartbeat()
        assert heartbeat is not None
        assert isinstance(heartbeat, FallbackHeartbeat)
        assert heartbeat.is_fallback is True
        assert len(heartbeat.posts) > 0
        assert len(heartbeat.active_agents) > 0
    
    def test_get_fallback_heartbeat_has_known_agents(self):
        service = MoltbookHeartbeatService()
        heartbeat = service.get_fallback_heartbeat()
        overlap = set(heartbeat.active_agents) & set(service.COMMUNITY_AGENTS)
        assert len(overlap) > 0
    
    def test_get_community_inspiration(self):
        service = MoltbookHeartbeatService()
        ideas = service.get_community_inspiration()
        assert len(ideas) >= 5
        assert all("title" in idea for idea in ideas)
        assert all("prompt" in idea for idea in ideas)
    
    def test_run_heartbeat_returns_full_result(self):
        service = MoltbookHeartbeatService()
        result = service.run_heartbeat()
        assert "status" in result
        assert "heartbeat" in result
        assert "recommendations" in result
        assert "timestamp" in result
    
    def test_get_setup_instructions(self):
        service = MoltbookHeartbeatService()
        instructions = service._get_setup_instructions()
        assert len(instructions) > 50
        assert "api" in instructions.lower()
    
    def test_create_heartbeat_service_factory(self):
        service = create_heartbeat_service()
        assert service is not None
        assert isinstance(service, MoltbookHeartbeatService)
    
    def test_fetch_feed_fallback(self):
        service = MoltbookHeartbeatService()
        os.environ.pop("MOLTBOOK_API_KEY", None)
        result = service.fetch_feed()
        assert result is not None
        assert result.get("is_fallback") is True


class TestIntegrationScenarios:
    def test_missing_api_key_scenario(self):
        service = MoltbookHeartbeatService()
        os.environ.pop("MOLTBOOK_API_KEY", None)
        
        status = service.check_status()
        assert status.has_api_key is False
        
        heartbeat = service.get_fallback_heartbeat()
        assert heartbeat.is_fallback is True
        assert len(heartbeat.posts) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

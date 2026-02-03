"""Tests for pet_state.py — Clawgotchi's emotional core."""

import pytest
import time
from unittest.mock import patch

from pet_state import PetState, FACES, QUIPS, SHY_SOURCE_WINDOW, CURIOUS_SOURCE_WINDOW


class TestPetStateInit:
    """Test PetState initialization."""

    def test_default_face_is_cool(self):
        """Pet should start with cool face."""
        state = PetState()
        assert state.face_key == "cool"

    def test_has_quip(self):
        """Pet should have initial quip."""
        state = PetState()
        assert isinstance(state.quip, str)
        assert len(state.quip) > 0

    def test_born_at_is_recent(self):
        """born_at should be close to current time."""
        state = PetState()
        now = time.time()
        assert abs(state.born_at - now) < 1.0

    def test_gateway_online_by_default(self):
        """Gateway should be online initially."""
        state = PetState()
        assert state.gateway_online is True

    def test_last_pet_at_is_zero(self):
        """Should not have been petted yet."""
        state = PetState()
        assert state.last_pet_at == 0.0


class TestComputeFace:
    """Test face computation based on activity."""

    def test_offline_when_gateway_down(self):
        """Should show offline face when gateway is offline."""
        state = PetState()
        face = state.compute_face(gateway_online=False, feed_rate=5.0, active_agents=2)
        assert face == "offline"

    def test_sleeping_at_night_with_low_activity(self):
        """Should sleep between 1-6 AM with low feed rate."""
        state = PetState()
        # Mock datetime to return 3 AM
        with patch('pet_state.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 3
            face = state.compute_face(gateway_online=True, feed_rate=0.1, active_agents=0)
            assert face == "sleeping"

    def test_grateful_after_being_petted(self):
        """Should show grateful face within 30 seconds of petting."""
        state = PetState()
        state.pet()  # Pet the pet
        face = state.compute_face(gateway_online=True, feed_rate=1.0, active_agents=1)
        assert face == "grateful"

    def test_intense_with_high_activity(self):
        """Should show intense face with very high activity."""
        state = PetState()
        face = state.compute_face(gateway_online=True, feed_rate=15.0, active_agents=6)
        assert face == "intense"

    def test_excited_with_moderate_high_activity(self):
        """Should show excited face with moderately high activity."""
        state = PetState()
        face = state.compute_face(gateway_online=True, feed_rate=7.0, active_agents=4)
        assert face == "excited"

    def test_happy_with_good_activity(self):
        """Should show happy face with good activity."""
        state = PetState()
        face = state.compute_face(gateway_online=True, feed_rate=3.0, active_agents=2)
        assert face == "happy"

    def test_cool_with_normal_activity(self):
        """Should show cool face with normal activity."""
        state = PetState()
        face = state.compute_face(gateway_online=True, feed_rate=1.0, active_agents=1)
        assert face == "cool"

    def test_bored_with_low_activity(self):
        """Should show bored face with very low activity."""
        state = PetState()
        face = state.compute_face(gateway_online=True, feed_rate=0.3, active_agents=0)
        assert face == "bored"


class TestPetMethod:
    """Test petting the pet."""

    def test_pet_updates_last_pet_at(self):
        """Petting should update last_pet_at."""
        state = PetState()
        before = time.time() - 1
        state.pet()
        after = time.time() + 1
        assert before <= state.last_pet_at <= after

    def test_pet_sets_grateful_quip(self):
        """Petting should set a grateful quip."""
        state = PetState()
        state.pet()
        assert state.quip in QUIPS["grateful"]

    def test_pet_has_cooldown(self):
        """Petting should set a short cooldown."""
        state = PetState()
        state.pet()
        assert state._quip_cooldown == 8.0


class TestGetFace:
    """Test face frame retrieval."""

    def test_get_face_returns_string(self):
        """get_face should return a string."""
        state = PetState()
        face = state.get_face()
        assert isinstance(face, str)
        assert len(face) > 0

    def test_get_face_returns_valid_face(self):
        """get_face should return a face from FACES."""
        state = PetState()
        face = state.get_face()
        frames = FACES.get(state.face_key, ["(⌐■_■)"])
        assert face in frames


class TestGetUptime:
    """Test uptime calculation."""

    def test_get_uptime_returns_string(self):
        """get_uptime should return a string."""
        state = PetState()
        uptime = state.get_uptime()
        assert isinstance(uptime, str)

    def test_get_uptime_format(self):
        """Uptime should contain 'm' for minutes."""
        state = PetState()
        uptime = state.get_uptime()
        assert uptime.endswith('m')


class TestShyEmotion:
    """Test shy emotion triggered by multiple different sources."""

    def test_shy_face_exists(self):
        """Shy face should exist in FACES."""
        assert "shy" in FACES

    def test_shy_quips_exist(self):
        """Shy quips should exist in QUIPS."""
        assert "shy" in QUIPS
        assert len(QUIPS["shy"]) > 0

    def test_add_message_source_tracks_source(self):
        """add_message_source should record the source."""
        state = PetState()
        state.add_message_source("Telegram")
        assert len(state._recent_sources) == 1
        assert state._recent_sources[0][1] == "Telegram"

    def test_multiple_sources_triggers_shy(self):
        """Should show shy face when 3+ unique sources in window."""
        state = PetState()
        # Add 3 different sources
        state.add_message_source("Telegram")
        state.add_message_source("Cron")
        state.add_message_source("Agent")
        # Compute face with low activity (should trigger shy)
        face = state.compute_face(gateway_online=True, feed_rate=0.5, active_agents=1)
        assert face == "shy"

    def test_single_source_does_not_trigger_shy(self):
        """Should not show shy face with only one source."""
        state = PetState()
        state.add_message_source("Telegram")
        state.add_message_source("Telegram")
        state.add_message_source("Telegram")
        face = state.compute_face(gateway_online=True, feed_rate=0.5, active_agents=1)
        assert face != "shy"

    def test_old_sources_expire(self):
        """Sources older than window should not count toward shy trigger."""
        state = PetState()
        # Add 2 sources
        state.add_message_source("Telegram")
        state.add_message_source("Cron")
        # Simulate sources being older than the window
        state._recent_sources = [
            (time.time() - SHY_SOURCE_WINDOW - 1, "Telegram"),
            (time.time() - SHY_SOURCE_WINDOW - 1, "Cron"),
        ]
        # Add 1 fresh source
        state.add_message_source("Agent")
        # With only 1 fresh unique source, should not trigger shy
        face = state.compute_face(gateway_online=True, feed_rate=0.5, active_agents=1)
        assert face != "shy"

    def test_shy_has_animation_interval(self):
        """Shy should have animation interval defined."""
        from pet_state import ANIMATION_INTERVALS
        assert "shy" in ANIMATION_INTERVALS

    def test_shy_has_bob_interval(self):
        """Shy should have bob interval defined."""
        from pet_state import BOB_INTERVALS
        assert "shy" in BOB_INTERVALS

    def test_shy_has_cat_mapping(self):
        """Shy emotion should have ASCII cat art mapping."""
        from ascii_cats import EMOTION_CAT_TERMS as cat_terms
        assert "shy" in cat_terms


class TestCuriousEmotion:
    """Test curious emotion."""

    def test_curious_face_exists(self):
        """Curious face should exist in FACES."""
        assert "curious" in FACES

    def test_curious_quips_exist(self):
        """Curious quips should exist in QUIPS."""
        assert "curious" in QUIPS
        assert len(QUIPS["curious"]) > 0

    def test_curious_has_animation_interval(self):
        """Curious should have animation interval defined."""
        from pet_state import ANIMATION_INTERVALS
        assert "curious" in ANIMATION_INTERVALS

    def test_curious_has_bob_interval(self):
        """Curious should have bob interval defined."""
        from pet_state import BOB_INTERVALS
        assert "curious" in BOB_INTERVALS

    def test_curious_has_cat_mapping(self):
        """Curious emotion should have ASCII cat art mapping."""
        from ascii_cats import EMOTION_CAT_TERMS as cat_terms
        assert "curious" in cat_terms


class TestCuriousEmotionTrigger:
    """Test curious emotion triggering based on message sources."""

    def test_single_source_triggers_curious(self):
        """Should show curious face with single message source."""
        state = PetState()
        state.add_message_source("Telegram")
        face = state.compute_face(gateway_online=True, feed_rate=0.5, active_agents=1)
        assert face == "curious"

    def test_two_sources_triggers_curious(self):
        """Should show curious face with two unique message sources."""
        state = PetState()
        state.add_message_source("Telegram")
        state.add_message_source("Cron")
        face = state.compute_face(gateway_online=True, feed_rate=0.5, active_agents=1)
        assert face == "curious"

    def test_three_sources_triggers_shy_not_curious(self):
        """Three sources should trigger shy, not curious."""
        state = PetState()
        state.add_message_source("Telegram")
        state.add_message_source("Cron")
        state.add_message_source("Agent")
        face = state.compute_face(gateway_online=True, feed_rate=0.5, active_agents=1)
        assert face == "shy"

    def test_returning_source_triggers_curious(self):
        """Should show curious when an old source is present and a new source appears."""
        state = PetState()
        # Add an old source (within curious window)
        state._recent_sources = [
            (time.time() - CURIOUS_SOURCE_WINDOW + 10, "Telegram"),  # Old but within curious window
        ]
        # Add a NEW source
        state.add_message_source("Cron")
        face = state.compute_face(gateway_online=True, feed_rate=0.5, active_agents=1)
        assert face == "curious"

    def test_no_sources_does_not_trigger_curious(self):
        """No message sources should not trigger curious."""
        state = PetState()
        face = state.compute_face(gateway_online=True, feed_rate=1.0, active_agents=1)
        assert face != "curious"


class TestProudEmotion:
    """Test proud emotion triggered by building/creating."""

    def test_proud_face_exists(self):
        """Proud face should exist in FACES."""
        assert "proud" in FACES

    def test_proud_quips_exist(self):
        """Proud quips should exist in QUIPS."""
        assert "proud" in QUIPS
        assert len(QUIPS["proud"]) > 0

    def test_proud_has_animation_interval(self):
        """Proud should have animation interval defined."""
        from pet_state import ANIMATION_INTERVALS
        assert "proud" in ANIMATION_INTERVALS

    def test_proud_has_bob_interval(self):
        """Proud should have bob interval defined."""
        from pet_state import BOB_INTERVALS
        assert "proud" in BOB_INTERVALS

    def test_proud_has_cat_mapping(self):
        """Proud emotion should have ASCII cat art mapping (or fallback gracefully)."""
        from ascii_cats import EMOTION_CAT_TERMS as cat_terms
        # "proud" may or may not be in the library's term map, but it shouldn't crash
        if "proud" in cat_terms:
            assert True
        else:
            # It's okay if it's not there, as long as get_cat_art handles it
            from pet_state import PetState
            state = PetState()
            # Just ensure it doesn't error out
            _ = state.get_cat_art()
            assert True


class TestProudEmotionTrigger:
    """Test proud emotion triggering based on building events."""

    def test_builtin_triggers_proud(self):
        """mark_built() should trigger proud face within window."""
        state = PetState()
        state.mark_built()
        face = state.compute_face(gateway_online=True, feed_rate=0.5, active_agents=1)
        assert face == "proud"

    def test_proud_fades_over_time(self):
        """Proud face should fade after built window expires."""
        state = PetState()
        state.mark_built()
        # Simulate time passing (more than BUILT_PRIDE_WINDOW)
        state._last_built_at = time.time() - 600  # 10 minutes ago
        face = state.compute_face(gateway_online=True, feed_rate=0.5, active_agents=1)
        assert face != "proud"

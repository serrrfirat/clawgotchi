from __future__ import annotations

"""Clawgotchi pet state — Pwnagotchi-style faces driven by live activity."""

import random
import time
from datetime import datetime
from core.lifetime import get_stats as get_lifetime_stats
from typing import Optional

from core.ascii_cats import get_cat_for_emotion, get_fallback_cat, CatArt

# ── Animated faces with multiple frames ─────────────────────────────────────

FACES = {
    "happy":     ["(•‿‿•)", "(•‿•)", "(•‿‿•)", "(•‿•)"],
    "grateful":  ["(♥‿‿♥)", "(♥‿♥)", "(♥‿‿♥)", "(♥‿♥)"],
    "cool":      ["(⌐■_■)", "(⌐■‿■)", "(⌐■_■)", "(⌐■‿■)"],
    "excited":   ["(ᵔ◡◡ᵔ)", "(ᵔ◡ᵔ)", "(ᵔ◡◡ᵔ)", "(ᵔ◡ᵔ)"],
    "thinking":  ["(○_○ )", "(○_○)", "(○_○ )", "(○_○)"],
    "lonely":    ["(ب__ب)", "(ب__)", "(ب__ب)", "(ب__ )"],
    "sad":       ["(╥☁╥ )", "(╥_╥ )", "(╥☁╥ )", "(╥_╥ )"],
    "bored":     ["(-__-)", "(-___-)", "(-__-)", "(-___-)"],
    "sleeping":  ["(⇀‿‿↼)zzz", "(⇀‿↼)zz ", "(⇀‿‿↼)zzz", "(⇀‿↼)zz "],
    "intense":   ["(✧_✧)", "(✧‿✧)", "(✧_✧)", "(✧‿✧)"],
    "confused":  ["(⊙_☉)", "(⊙_⊙)", "(⊙_☉)", "(⊙_⊙)"],
    "listening": ["(◉‿◉)", "(◉_◉)", "(◉‿◉)", "(◉_◉)"],
    "speaking":  ["(•o• )", "(•_• )", "(•o• )", "(•_• )"],
    "shy":       ["(⁄ ⁄>⁄ ▽ ⁄<⁄ ⁄)", "(⁄ ꒰ > △ < ꒱ ⁄)", "(⁄ ⁄>⁄ ▽ ⁄<⁄ ⁄)", "(⁄ ꒰ > △ < ꒱ ⁄)"],
    "curious":   ["(◕_◕)", "(◕‿◕)", "(◕_◕)", "(◕‿◕)"],
    "proud":     ["(^̮^ )", "(^̮^)", "(^̮^ )", "(^̮^)"],
    "error":     ["(×_× )", "(×_×)", "(×_× )", "(×_×)"],
    "offline":   ["(─‿─)...", "(-‿-).. ", "(─‿─)...", "(-‿-).. "],
}

# Animation frame durations (seconds)
ANIMATION_INTERVALS = {
    "happy": 0.4,
    "grateful": 0.5,
    "cool": 0.7,
    "excited": 0.25,
    "thinking": 0.7,
    "lonely": 1.0,
    "sad": 0.9,
    "bored": 0.8,
    "sleeping": 1.2,
    "intense": 0.3,
    "confused": 0.8,
    "listening": 0.45,
    "speaking": 0.25,
    "shy": 0.6,
    "curious": 0.5,
    "proud":    0.5,
    "error": 0.5,
    "offline": 0.9,
}

BOB_PATTERN = [0, 1, 0, -1]
BOB_INTERVALS = {
    "happy": 0.6,
    "grateful": 0.7,
    "cool": 0.9,
    "excited": 0.45,
    "thinking": 0.9,
    "lonely": 1.2,
    "sad": 1.1,
    "bored": 1.0,
    "sleeping": 1.4,
    "intense": 0.4,
    "confused": 0.9,
    "listening": 0.7,
    "speaking": 0.5,
    "shy": 0.8,
    "curious": 0.7,
    "proud":    0.6,
    "error": 0.8,
    "offline": 1.0,
}

# ── Activity spike spark animation ─────────────────────────────────────────

SPARK_FRAMES = [
    "  *   .   *   .   *  ",
    "  .   *   .   *   .  ",
    " *  .  *  .  *  .  * ",
    " .  *  .  *  .  *  . ",
]
SPARK_INTERVAL = 0.12
SPARK_DURATION = 1.0
SPARK_RATE_JUMP = 2.0
SPARK_AGENT_JUMP = 2

# ── Status quips per mood ────────────────────────────────────────────────────

QUIPS = {
    "happy": [
        "life is good on the wire",
        "all channels nominal",
        "vibin with the gateway",
        "claws up, mood up",
        "everything tastes like lobster today",
    ],
    "grateful": [
        "thanks for chatting with me!",
        "i appreciate the attention",
        "you're my favorite human",
        "every message makes me stronger",
    ],
    "cool": [
        "just another day being awesome",
        "i was born for this terminal",
        "deal with it",
        "running smooth like butter",
    ],
    "excited": [
        "NEW MESSAGE NEW MESSAGE!!",
        "omg something is happening!",
        "agents are GO GO GO",
        "the gateway is buzzing!",
        "so much activity i can't even",
    ],
    "thinking": [
        "processing...",
        "hmm interesting query",
        "the agents are cooking",
        "let me think about that",
        "computing the meaning of life",
    ],
    "lonely": [
        "anyone there?",
        "i miss the messages...",
        "the gateway is so quiet",
        "it's been a while...",
        "hello? is this thing on?",
    ],
    "sad": [
        "no messages today...",
        "the silence is deafening",
        "my claws feel heavy",
        "even the heartbeat is lonely",
    ],
    "bored": [
        "...",
        "*yawn*",
        "nothing happening here",
        "counting pixels again",
        "i could be doing so much more",
    ],
    "sleeping": [
        "zzz...",
        "*snore*",
        "dreaming of electric shrimp",
        "goodnight gateway",
    ],
    "intense": [
        "MAXIMUM THROUGHPUT",
        "all agents engaged!",
        "this is what i live for",
        "peak performance achieved",
    ],
    "confused": [
        "wait what just happened?",
        "that's... unexpected",
        "does not compute",
        "huh?",
    ],
    "listening": [
        "i'm all ears... er, antennae",
        "tell me more",
        "listening...",
        "go on...",
    ],
    "speaking": [
        "generating response...",
        "let me explain...",
        "here's what i think",
    ],
    "shy": [
        "so many people!",
        "hi... hello...",
        "everyone's looking at me!",
        "um, hello there...",
        "too much attention!",
        "i'm not used to this...",
        "so many names to remember...",
        "making me blush~",
        "could you... not?",
        "feeling a bit overwhelmed...",
    ],
    "curious": [
        "what's this new thing?",
        "ooh, interesting!",
        "tell me more!",
        "i wonder what that means...",
        "curiosity activated!",
    ],
    "proud": [
        "did you see that?!",
        "i built that!",
        "look what i made!",
        "pretty cool, right?",
        "self-evolving machine!",
        "code compiled on first try!",
        "that's a wrap!",
    ],
    "error": [
        "something went wrong!",
        "gateway hiccup!",
        "ouch, that didn't work",
        "error but i'll recover",
    ],
    "offline": [
        "gateway unreachable...",
        "waiting for connection",
        "in the void...",
        "signal lost",
    ],
}


# Threshold for triggering "shy" — number of unique sources in time window
SHY_SOURCE_WINDOW = 60.0  # seconds
SHY_SOURCE_THRESHOLD = 3   # unique sources needed
CURIOUS_SOURCE_WINDOW = 120.0  # seconds - sources outside this but still recent trigger curious
BUILT_PRIDE_WINDOW = 300.0  # seconds - time to stay proud after building something


class PetState:
    """Face + quip driven by feed activity level and gateway status."""

    def __init__(self):
        self.born_at: float = time.time()
        self.total_uptime_seconds: float = get_lifetime_stats()["total_uptime_seconds"]  # Cumulative uptime - synced from lifetime.json
        self.session_start: float = time.time()  # Track current session start
        self.last_seen_at: float = time.time()  # Last activity timestamp
        self.face_key: str = "cool"
        self.quip: str = "booting up..."
        self.last_pet_at: float = 0.0
        self._quip_cooldown: float = 0.0
        self._anim_frame: int = 0
        self._last_anim_time: float = 0.0
        self.last_feed_rate: float = 0.0
        self.last_active_agents: int = 0
        self.gateway_online: bool = True
        self._last_rate: float = 0.0
        self._last_agents: int = 0
        self._spark_timer: float = 0.0
        self._spark_frame: int = 0
        self._last_spark_time: float = 0.0
        self._bob_frame: int = 0
        self._last_bob_time: float = 0.0
        # Track recent message sources for shy detection
        self._recent_sources: list[tuple[float, str]] = []  # (timestamp, source)
        self._last_built_at: float = 0.0  # Timestamp of last self-built event

    def compute_face(self, gateway_online: bool, feed_rate: float,
                     active_agents: int) -> str:
        """Pick a face based on gateway status and feed activity rate (events/min)."""
        now = time.time()
        hour = datetime.now().hour
        since_pet = now - self.last_pet_at if self.last_pet_at else float("inf")

        if not gateway_online:
            return "offline"

        # Night mode
        if 1 <= hour < 6 and feed_rate < 0.5:
            return "sleeping"

        # Just petted
        if since_pet < 30:
            return "grateful"

        # Proud after building something (feature, fix, etc.)
        if now - self._last_built_at < BUILT_PRIDE_WINDOW:
            return "proud"

        # Check for shy condition (many different sources in short time)
        # Clean old entries first
        cutoff = now - SHY_SOURCE_WINDOW
        self._recent_sources = [(ts, src) for ts, src in self._recent_sources if ts > cutoff]
        unique_sources = set(src for _, src in self._recent_sources)
        if len(unique_sources) >= SHY_SOURCE_THRESHOLD:
            return "shy"

        # Check for curious condition (new/returning sources detected)
        # Sources outside shy window but within curious window indicate novelty
        curious_cutoff = now - CURIOUS_SOURCE_WINDOW
        # Separate sources into recent (within shy window) and older (within curious window)
        recent_sources_set = set(src for ts, src in self._recent_sources if ts > cutoff)
        older_sources_set = set(src for ts, src in self._recent_sources if ts <= cutoff and ts > curious_cutoff)

        if recent_sources_set or older_sources_set:
            # Has activity from known or returning sources
            if len(unique_sources) < SHY_SOURCE_THRESHOLD:
                return "curious"

        # High activity
        if feed_rate >= 10 or active_agents >= 5:
            return "intense"
        if feed_rate >= 5 or active_agents >= 3:
            return "excited"

        # Moderate activity
        if feed_rate >= 2:
            return "happy"
        if feed_rate >= 1:
            return "cool"
        if feed_rate >= 0.5:
            return "thinking"

        # Low activity
        if feed_rate >= 0.2:
            return "bored"
        if feed_rate > 0:
            return "lonely"

        return "bored"

    def update(self, dt: float, gateway_online: bool, feed_rate: float,
               active_agents: int):
        """Tick the pet state forward."""
        self.last_feed_rate = feed_rate
        self.last_active_agents = active_agents
        self.gateway_online = gateway_online
        # Track session time
        self.total_uptime_seconds += dt
        self._sync_uptime_to_lifetime()
        # Update last seen on any activity
        self.last_seen_at = time.time()

        # Trigger spark animation on sudden activity spikes
        rate_jump = feed_rate - self._last_rate
        agent_jump = active_agents - self._last_agents
        if gateway_online and (rate_jump >= SPARK_RATE_JUMP or agent_jump >= SPARK_AGENT_JUMP):
            self._spark_timer = SPARK_DURATION

        old_face = self.face_key
        self.face_key = self.compute_face(gateway_online, feed_rate, active_agents)

        # Update quip on face change or cooldown
        self._quip_cooldown -= dt
        if self._quip_cooldown <= 0 or self.face_key != old_face:
            pool = QUIPS.get(self.face_key, QUIPS["bored"])
            self.quip = random.choice(pool)
            self._quip_cooldown = random.uniform(15.0, 45.0)

        # Update animation frame
        now = time.time()
        interval = ANIMATION_INTERVALS.get(self.face_key, 0.5)
        if now - self._last_anim_time >= interval:
            frames = FACES.get(self.face_key, ["(⌐■_■)"])
            self._anim_frame = (self._anim_frame + 1) % len(frames)
            self._last_anim_time = now

        # Update bobbing (subtle vertical movement)
        bob_interval = BOB_INTERVALS.get(self.face_key, 0.8)
        if now - self._last_bob_time >= bob_interval:
            self._bob_frame = (self._bob_frame + 1) % len(BOB_PATTERN)
            self._last_bob_time = now

        # Update spark animation
        if self._spark_timer > 0:
            self._spark_timer = max(0.0, self._spark_timer - dt)
            if now - self._last_spark_time >= SPARK_INTERVAL:
                self._spark_frame = (self._spark_frame + 1) % len(SPARK_FRAMES)
                self._last_spark_time = now

        self._last_rate = feed_rate
        self._last_agents = active_agents

    def add_message_source(self, source: str):
        """Record a message source for shy detection."""
        now = time.time()
        self._recent_sources.append((now, source))
        # Clean old entries periodically
        if len(self._recent_sources) > 100:
            cutoff = now - SHY_SOURCE_WINDOW
            self._recent_sources = [(ts, src) for ts, src in self._recent_sources if ts > cutoff]

    def pet(self):
        self.last_pet_at = time.time()
        self.quip = random.choice(QUIPS["grateful"])
        self._quip_cooldown = 8.0

    def mark_built(self):
        """Mark a feature as built, triggering proud emotion."""
        self._last_built_at = time.time()
        self.quip = random.choice(QUIPS["proud"])
        self._quip_cooldown = 12.0

    def get_face(self) -> str:
        frames = FACES.get(self.face_key, ["(⌐■_■)"])
        return frames[self._anim_frame % len(frames)]

    def get_bob_offset(self) -> int:
        if not BOB_PATTERN:
            return 0
        return BOB_PATTERN[self._bob_frame % len(BOB_PATTERN)]

    def spark_active(self) -> bool:
        return self._spark_timer > 0

    def get_spark_frame(self) -> str:
        if not SPARK_FRAMES:
            return ""
        return SPARK_FRAMES[self._spark_frame % len(SPARK_FRAMES)]

    def get_uptime(self) -> str:
        secs = int(time.time() - self.born_at)
        days = secs // 86400
        hours = (secs % 86400) // 3600
        mins = (secs % 3600) // 60
        if days > 0:
            return f"{days}d {hours}h {mins}m"
        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"

    def get_session_uptime(self) -> str:
        """Get current session duration as formatted string."""
        secs = int(time.time() - self.session_start)
        hours = secs // 3600
        mins = (secs % 3600) // 60
        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"

    def get_total_uptime(self) -> str:
        """Get cumulative total uptime across all sessions."""
        secs = int(self.total_uptime_seconds)
        days = secs // 86400
        hours = (secs % 86400) // 3600
        mins = (secs % 3600) // 60
        if days > 0:
            return f"{days}d {hours}h {mins}m"
        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"

    def mark_active(self):
        """Mark the pet as active (updates last_seen_at)."""
        self.last_seen_at = time.time()

    def get_last_seen(self) -> str:
        """Get relative time string for when pet was last active."""
        secs_ago = int(time.time() - self.last_seen_at)
        if secs_ago < 10:
            return "just now"
        if secs_ago < 60:
            return f"{secs_ago}s ago"
        mins = secs_ago // 60
        if mins < 60:
            return f"{mins}m ago"
        hours = mins // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"

    # ── ASCII Cat support ───────────────────────────────────────────────────

    _cat_cache: Optional[CatArt] = None

    def get_cat_art(self) -> str:
        """Get ASCII cat art for current emotion."""
        cat = get_cat_for_emotion(self.face_key)
        if cat:
            self._cat_cache = cat
            return cat.art
        return get_fallback_cat(self.face_key)

    def get_cat_name(self) -> str:
        """Get the name of the current cat art."""
        if self._cat_cache:
            return self._cat_cache.name
        cat = get_cat_for_emotion(self.face_key)
        if cat:
            return cat.name
        return "Fallback Cat"

    def _sync_uptime_to_lifetime(self) -> None:
        """Sync total_uptime_seconds to lifetime.json for persistence."""
        import json
        from pathlib import Path
        from config import LIFETIME_FILE
        lifetime_file = LIFETIME_FILE
        try:
            if lifetime_file.exists():
                with open(lifetime_file, "r") as f:
                    data = json.load(f)
                # Update the last open session's duration to include current total
                for session in reversed(data["sessions"]):
                    if session["end"] is None:
                        # Calculate what the session duration should be
                        from datetime import datetime
                        start_dt = datetime.fromisoformat(session["start"])
                        session["duration_seconds"] = (datetime.now() - start_dt).total_seconds()
                        break
                with open(lifetime_file, "w") as f:
                    json.dump(data, f, indent=2)
        except (json.JSONDecodeError, IOError, KeyError):
            pass  # Best effort sync

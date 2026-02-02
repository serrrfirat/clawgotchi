"""Clawgotchi pet state — Pwnagotchi-style faces driven by live activity."""

import random
import time
from datetime import datetime
from typing import Optional

from ascii_cats import get_cat_for_emotion, get_fallback_cat, CatArt

# ── Animated faces with multiple frames ─────────────────────────────────────

FACES = {
    "happy":     ["(•‿‿•)", "(•‿•)", "(•‿‿•)"],
    "grateful":  ["(♥‿‿♥)", "(♥‿♥)", "(♥‿‿♥)"],
    "cool":      ["(⌐■_■)", "(⌐■_■)", "(⌐■_■)"],
    "excited":   ["(ᵔ◡◡ᵔ)", "(ᵔ◡ᵔ)", "(ᵔ◡◡ᵔ)"],
    "thinking":  ["(○_○ )", "(○_○)", "(○_○ )"],
    "lonely":    ["(ب__ب)", "(ب__)", "(ب__ب)"],
    "sad":       ["(╥☁╥ )", "(╥_╥ )", "(╥☁╥ )"],
    "bored":     ["(-__-)", "(-___-)", "(-__-)"],
    "sleeping":  ["(⇀‿‿↼)zzz", "(⇀‿↼)zz", "(⇀‿‿↼)zzz"],
    "intense":   ["(✧_✧)", "(✧‿✧)", "(✧_✧)"],
    "confused":  ["(⊙_☉)", "(⊙_⊙)", "(⊙_☉)"],
    "listening": ["(◉‿◉)", "(◉_◉)", "(◉‿◉)"],
    "speaking":  ["(•o• )", "(•_• )", "(•o• )"],
    "error":     ["(×_× )", "(×_×)", "(×_× )"],
    "offline":   ["(─‿─)...", "(-‿-)..", "(─‿─)..."],
}

# Animation frame durations (seconds)
ANIMATION_INTERVALS = {
    "happy": 0.5,
    "grateful": 0.6,
    "cool": 1.0,
    "excited": 0.3,
    "thinking": 0.8,
    "lonely": 1.2,
    "sad": 1.0,
    "bored": 0.7,
    "sleeping": 1.5,
    "intense": 0.4,
    "confused": 0.9,
    "listening": 0.5,
    "speaking": 0.3,
    "error": 0.6,
    "offline": 1.0,
}

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


class PetState:
    """Face + quip driven by feed activity level and gateway status."""

    def __init__(self):
        self.born_at: float = time.time()
        self.face_key: str = "cool"
        self.quip: str = "booting up..."
        self.last_pet_at: float = 0.0
        self._quip_cooldown: float = 0.0
        self._anim_frame: int = 0
        self._last_anim_time: float = 0.0

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

    def pet(self):
        self.last_pet_at = time.time()
        self.quip = random.choice(QUIPS["grateful"])
        self._quip_cooldown = 8.0

    def get_face(self) -> str:
        frames = FACES.get(self.face_key, ["(⌐■_■)"])
        return frames[self._anim_frame % len(frames)]

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

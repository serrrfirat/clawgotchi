"""Clawgotchi ASCII cats — loads cat art from local cache (78 cats from asciiart.eu)."""

import json
import time
from pathlib import Path
from typing import Optional

from dataclasses import dataclass


@dataclass
class CatArt:
    name: str
    art: str


# Path to local cat cache
CAT_CACHE_FILE = Path(__file__).parent / "cats.json"

# Search terms for emotion → cat mapping
EMOTION_CAT_TERMS = {
    "creative": ["Lion", "Panther", "Tiger"],
    "happy": ["Cat face", "Cat", "Happy"],
    "grateful": ["Cat", "Two cats"],
    "cool": ["Cat"],
    "excited": ["Cat", "Two cats"],
    "thinking": ["Cat"],
    "lonely": ["Cat", "One cat"],
    "sad": ["Sleeping", "ZZZ"],
    "bored": ["Sleeping", "ZZZ"],
    "sleeping": ["Sleeping", "ZZZ"],
    "intense": ["Tiger", "Panther"],
    "confused": ["Cat"],
    "listening": ["Cat"],
    "speaking": ["Cat"],
    "error": ["Cat"],
    "offline": ["Sleeping", "ZZZ"],
}


def _load_cat_cache() -> list[CatArt]:
    """Load cat cache from local JSON file."""
    if not CAT_CACHE_FILE.exists():
        return []
    try:
        data = json.loads(CAT_CACHE_FILE.read_text())
        return [CatArt(name=item["name"], art=item["art"]) for item in data if item.get("art")]
    except (json.JSONDecodeError, OSError, KeyError):
        return []


# Pre-load cache
_CAT_CACHE = _load_cat_cache()


def get_cat_for_emotion(emotion: str) -> Optional[CatArt]:
    """Get an ASCII cat matching the given emotion."""
    if not _CAT_CACHE:
        return None

    terms = EMOTION_CAT_TERMS.get(emotion.lower(), ["Cat"])

    for term in terms:
        term_lower = term.lower()
        for cat in _CAT_CACHE:
            if term_lower in cat.name.lower():
                return cat

    # Return random cat
    import random
    return random.choice(_CAT_CACHE) if _CAT_CACHE else None


def get_random_cat() -> Optional[CatArt]:
    """Get a random ASCII cat."""
    if _CAT_CACHE:
        import random
        return random.choice(_CAT_CACHE)
    return None


# Fallback cats when no cache available
FALLBACK_CATS = {
    "creative": r"""
    /\_____/\
   /  o o  \      CREATIVE
  ( ==^== )       MODE!
   )  (  (        
  (  )  (         
  (__)__)         
    """,
    "sleeping": r"""
     |\,,,---,,_
    ZZZzz /,`.-'`'    -.  ;-;;,_
     |,4-  ) )-,_. ,\ (  `'-'
    '---''(_/--'  `-'\_)
    """,
    "happy": r"""
     /\_/\
    ( o.o )
     > ^ <
    """,
    "default": r"""
     /\_/\
    ( o o )
    ==_Y_==
     `-
    """,
}


def get_fallback_cat(emotion: str) -> str:
    """Get a fallback ASCII cat when cache load fails."""
    return FALLBACK_CATS.get(emotion.lower(), FALLBACK_CATS["default"])


def get_cat_count() -> int:
    """Return number of cats in cache."""
    return len(_CAT_CACHE)

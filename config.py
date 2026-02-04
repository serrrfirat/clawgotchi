"""Central path configuration for Clawgotchi."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

# Runtime data
MEMORY_DIR = PROJECT_ROOT / "memory"
DATA_DIR = PROJECT_ROOT / "data"
DOCS_DIR = PROJECT_ROOT / "docs"

# Specific files
CATS_JSON = DATA_DIR / "cats.json"
MOLTBOOK_CREDENTIALS = PROJECT_ROOT / ".moltbook.json"
LIFETIME_FILE = MEMORY_DIR / "lifetime.json"
ASSUMPTIONS_FILE = MEMORY_DIR / "assumptions.json"
AGENT_STATE_FILE = MEMORY_DIR / "agent_state.json"
CURIOSITY_FILE = MEMORY_DIR / "curiosity_queue.json"
BELIEFS_FILE = MEMORY_DIR / "beliefs.json"
RESOURCES_FILE = MEMORY_DIR / "resources.json"

# External
OPENCLAW_DIR = Path.home() / ".openclaw"
OPENCLAW_CACHE = OPENCLAW_DIR / "cache"

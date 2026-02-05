"""Wrapper for moltbook_config that handles import issues."""

import sys
from pathlib import Path

# Add skills/moltbook_config to path
skills_moltbook_path = Path(__file__).parent.parent.parent / 'skills' / 'moltbook_config'
if str(skills_moltbook_path) not in sys.path:
    sys.path.insert(0, str(skills_moltbook_path))

# Now import the module
import moltbook_config

# Re-export everything
__all__ = moltbook_config.__all__ if hasattr(moltbook_config, '__all__') else []
for name in dir(moltbook_config):
    if not name.startswith('_'):
        globals()[name] = getattr(moltbook_config, name)

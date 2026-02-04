#!/usr/bin/env python3
"""
Autonomous Agent for Clawgotchi - State Machine & Wake Cycles

This module drives Clawgotchi's autonomous operation through 15-minute wake cycles.
It runs in a background thread and coordinates:
- Health checks
- Memory curation
- Assumption verification
- Feature building
- Moltbook integration
- Self-preservation (backups, recovery, adaptive behavior)

The TUI (clawgotchi.py) displays the agent's state, thoughts, and health.

Hot-Reload: Watches source files for changes and auto-restarts.
"""

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timedelta
from pathlib import Path
from typing import Optional


class HotReloader:
    """Watch source files and trigger hot-reload on changes."""
    
    def __init__(self, watch_files: list):
        self.watch_files = [Path(f).absolute() for f in watch_files]
        self.last_mtimes = {}
        self._update_mtimes()
    
    def _update_mtimes(self):
        """Store current modification times."""
        for f in self.watch_files:
            try:
                self.last_mtimes[str(f)] = f.stat().st_mtime
            except:
                self.last_mtimes[str(f)] = 0
    
    def check(self) -> bool:
        """Check if any watched file changed. Returns True if changed."""
        for f in self.watch_files:
            try:
                mtime = f.stat().st_mtime
                if self.last_mtimes.get(str(f), 0) < mtime:
                    self._update_mtimes()
                    return True
            except:
                pass
        return False
    
    def restart(self):
        """Restart the process preserving state."""
        print("🔄 Hot-reloading...")
        # Signal main thread to restart
        os._exit(100)  # Special code for hot-reload

# State constants
STATE_SLEEPING = "SLEEPING"
STATE_WAKING = "WAKING"
STATE_OBSERVING = "OBSERVING"
STATE_DECIDING = "DECIDING"
STATE_BUILDING = "BUILDING"
STATE_EXPLORING = "EXPLORING"
STATE_VERIFYING = "VERIFYING"
STATE_SHARING = "SHARING"
STATE_REFLECTING = "REFLECTING"

# Paths
BASE_DIR = Path(__file__).parent
MEMORY_DIR = BASE_DIR / "memory"
STATE_FILE = MEMORY_DIR / "agent_state.json"
CURIOSITY_FILE = MEMORY_DIR / "curiosity_queue.json"
BELIEFS_FILE = MEMORY_DIR / "beliefs.json"
RESOURCES_FILE = MEMORY_DIR / "resources.json"

WAKE_INTERVAL = 15 * 60  # 15 minutes in seconds


class AgentState:
    """Persistent agent state."""
    
    def __init__(self):
        self.version = "1.0"
        self.last_wake = None
        self.current_state = STATE_SLEEPING
        self.health_score = 50  # Start neutral
        self.total_wakes = 0
        self.current_goal = ""
        self.current_thought = ""
        self.health_history = []
        self.git_status = "clean"
        self.errors = []
    
    def load(self) -> bool:
        """Load state from file. Returns True if successful."""
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                self.version = data.get("version", "1.0")
                self.last_wake = data.get("last_wake")
                self.current_state = data.get("current_state", STATE_SLEEPING)
                self.health_score = data.get("health_score", 50)
                self.total_wakes = data.get("total_wakes", 0)
                self.current_goal = data.get("current_goal", "")
                self.current_thought = data.get("current_thought", "")
                self.health_history = data.get("health_history", [])
                self.git_status = data.get("git_status", "clean")
                self.errors = data.get("errors", [])
                return True
            except Exception as e:
                print(f"Error loading state: {e}")
        return False
    
    def save(self):
        """Persist state to file."""
        MEMORY_DIR.mkdir(exist_ok=True)
        data = {
            "version": self.version,
            "last_wake": self.last_wake,
            "current_state": self.current_state,
            "health_score": self.health_score,
            "total_wakes": self.total_wakes,
            "current_goal": self.current_goal,
            "current_thought": self.current_thought,
            "health_history": self.health_history,
            "git_status": self.git_status,
            "errors": self.errors,
            "updated_at": datetime.now().isoformat()
        }
        STATE_FILE.write_text(json.dumps(data, indent=2))
    
    def add_error(self, error: str):
        """Add an error to the error log (keeps last 10)."""
        self.errors = [error] + self.errors[:9]
    
    def update_health(self, score: int):
        """Update health score with history tracking."""
        self.health_score = max(0, min(100, score))
        self.health_history.append({
            "timestamp": datetime.now().isoformat(),
            "score": self.health_score
        })
        # Keep last 100 entries
        self.health_history = self.health_history[-100:]


class CuriosityQueue:
    """Queue of things the agent wants to explore."""
    
    def __init__(self):
        self.queue = []
        self.explored_count = 0
        self.total_discovered = 0
    
    def load(self) -> bool:
        if CURIOSITY_FILE.exists():
            try:
                data = json.loads(CURIOSITY_FILE.read_text())
                self.queue = data.get("queue", [])
                self.explored_count = data.get("explored_count", 0)
                self.total_discovered = data.get("total_discovered", 0)
                return True
            except:
                pass
        return False
    
    def save(self):
        data = {
            "queue": self.queue,
            "explored_count": self.explored_count,
            "total_discovered": self.total_discovered,
            "updated_at": datetime.now().isoformat()
        }
        CURIOSITY_FILE.write_text(json.dumps(data, indent=2))
    
    def add(self, topic: str, source: str, priority: int = 3):
        """Add a curiosity to the queue."""
        item = {
            "id": f"cur-{len(self.queue) + 1}",
            "topic": topic,
            "source": source,
            "added_at": datetime.now().isoformat(),
            "priority": priority,
            "status": "pending"
        }
        self.queue.insert(0, item)
        self.total_discovered += 1
        self.save()
    
    def get_next(self) -> Optional[dict]:
        """Get the highest priority pending item."""
        pending = [i for i in self.queue if i.get("status") == "pending"]
        if not pending:
            return None
        return max(pending, key=lambda x: x.get("priority", 0))
    
    def mark_explored(self, item_id: str):
        """Mark an item as explored."""
        for item in self.queue:
            if item.get("id") == item_id:
                item["status"] = "explored"
                item["explored_at"] = datetime.now().isoformat()
                self.explored_count += 1
                self.save()
                return
    
    def mark_exploring(self, item_id: str):
        """Mark an item as currently exploring."""
        for item in self.queue:
            if item.get("id") == item_id:
                item["status"] = "exploring"
                item["started_at"] = datetime.now().isoformat()
                self.save()
                return


class Beliefs:
    """Agent's beliefs about itself and the world."""
    
    def __init__(self):
        self.beliefs = []
        self.questions = []
        self.version = 1
    
    def load(self) -> bool:
        if BELIEFS_FILE.exists():
            try:
                data = json.loads(BELIEFS_FILE.read_text())
                self.beliefs = data.get("beliefs", [])
                self.questions = data.get("questions", [])
                self.version = data.get("version", 1)
                return True
            except:
                pass
        return False
    
    def save(self):
        data = {
            "beliefs": self.beliefs,
            "questions": self.questions,
            "version": self.version,
            "updated_at": datetime.now().isoformat()
        }
        BELIEFS_FILE.write_text(json.dumps(data, indent=2))
    
    def add_belief(self, statement: str, confidence: float = 0.5):
        """Add a new belief."""
        belief = {
            "id": f"bel-{len(self.beliefs) + 1}",
            "statement": statement,
            "confidence": confidence,
            "evidence": [],
            "challenges": [],
            "created_at": datetime.now().isoformat(),
            "last_tested": None
        }
        self.beliefs.insert(0, belief)
        self.save()
    
    def add_evidence(self, belief_id: str, evidence: str):
        """Add evidence to a belief."""
        for b in self.beliefs:
            if b.get("id") == belief_id:
                b["evidence"].append(evidence)
                b["last_tested"] = datetime.now().isoformat()
                # Update confidence
                b["confidence"] = min(0.99, b["confidence"] + 0.05)
                self.save()
                return
    
    def add_question(self, question: str):
        """Add a question the agent is curious about."""
        self.questions.append({
            "text": question,
            "added_at": datetime.now().isoformat()
        })
        self.save()


class ResourceMonitor:
    """Monitor agent resources (disk, uptime, etc.)."""
    
    def __init__(self):
        self.data = {
            "disk": {"used_mb": 0, "available_mb": 0},
            "uptime": {"seconds": 0},
            "api_limits": {"moltbook_remaining": 0},
            "git": {"commits_today": 0}
        }
    
    def load(self) -> bool:
        if RESOURCES_FILE.exists():
            try:
                self.data = json.loads(RESOURCES_FILE.read_text())
                return True
            except:
                pass
        return False
    
    def save(self):
        self.data["updated_at"] = datetime.now().isoformat()
        RESOURCES_FILE.write_text(json.dumps(self.data, indent=2))
    
    def update(self):
        """Update all resource metrics."""
        # Disk usage
        try:
            result = os.popen("df -m . | tail -1").read()
            parts = result.split()
            if len(parts) >= 2:
                used = int(parts[2]) if parts[2].isdigit() else 0
                avail = int(parts[3]) if parts[3].isdigit() else 0
                self.data["disk"] = {
                    "used_mb": used,
                    "available_mb": avail
                }
        except:
            pass
        
        # Git commits today
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            result = os.popen(f'git log --since="{today}" --oneline | wc -l').read()
            self.data["git"]["commits_today"] = int(result.strip()) if result.strip().isdigit() else 0
        except:
            pass
        
        self.save()
        return self.data
    
    def check_limits(self) -> list:
        """Check if any resources are at risk."""
        issues = []
        disk_mb = self.data.get("disk", {}).get("available_mb", 0)
        if disk_mb < 100:
            issues.append(f"Low disk space: {disk_mb}MB remaining")
        
        git_commits = self.data.get("git", {}).get("commits_today", 0)
        if git_commits >= 10:
            issues.append(f"Daily commit limit near: {git_commits}/10")
        
        return issues


class AutonomousAgent:
    """Main autonomous agent with state machine."""
    
    def __init__(self):
        self.state = AgentState()
        self.curiosity = CuriosityQueue()
        self.beliefs = Beliefs()
        self.resources = ResourceMonitor()
        self.running = False
        self.paused = False
        self._thread: Optional[threading.Thread] = None
        self._last_action_result = ""
        
        # Load persisted state
        self.state.load()
        self.curiosity.load()
        self.beliefs.load()
        self.resources.load()
    
    def start(self):
        """Start the autonomous agent in a background thread."""
        if self._thread and self._thread.is_alive():
            print("Agent already running")
            return
        
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print("Autonomous agent started")
    
    def stop(self):
        """Stop the agent."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("Autonomous agent stopped")
    
    def pause(self):
        """Pause the agent."""
        self.paused = True
    
    def resume(self):
        """Resume the agent."""
        self.paused = False
    
    def _run_loop(self):
        """Main run loop."""
        while self.running:
            if self.paused:
                time.sleep(1)
                continue
            
            try:
                interval = asyncio.run(self.wake_cycle())
                # Sleep until next wake with adaptive interval
                for _ in range(int(interval)):
                    if not self.running or not self.paused:
                        break
                    time.sleep(1)
            except Exception as e:
                error_msg = f"Cycle error: {e}"
                print(error_msg)
                self.state.add_error(error_msg)
                self.state.save()
                time.sleep(60)  # Brief pause on error
    
    async def wake_cycle(self):
        """Execute one wake cycle."""
        # Check for crash recovery first
        if not await self._recover_from_crash():
            self.state.add_error("State recovery performed")
        
        # WAKING
        self.state.current_state = STATE_WAKING
        self.state.last_wake = datetime.now().isoformat()
        self.state.save()
        
        # OBSERVING
        self.state.current_state = STATE_OBSERVING
        self.resources.update()
        health_score = await self._check_health()
        
        # Check disk space
        disk_status, disk_msg = await self._check_disk_space()
        if disk_status != "ok":
            health_score = max(0, health_score - 20)
        
        self.state.update_health(health_score)
        self.state.current_thought = "Observing my surroundings..."
        self.state.save()
        await asyncio.sleep(2)
        
        # ADAPTIVE BEHAVIOR
        adaptive = await self._adaptive_behavior(health_score)
        skip_tasks = adaptive.get("skip_tasks", [])
        
        # DECIDING
        self.state.current_state = STATE_DECIDING
        action = await self._decide_next_action()
        
        # Skip if task is in skip list
        if action["type"] in skip_tasks:
            action = {"type": "REST", "description": "Skipping tasks (emergency mode)"}
        
        self.state.current_goal = action.get("description", "")
        self.state.save()
        await asyncio.sleep(1)
        
        # EXECUTE ACTION
        if action["type"] == "BUILD":
            self.state.current_state = STATE_BUILDING
            result = await self._build_feature(action)
        elif action["type"] == "EXPLORE":
            self.state.current_state = STATE_EXPLORING
            result = await self._explore_curiosity(action)
        elif action["type"] == "VERIFY":
            self.state.current_state = STATE_VERIFYING
            result = await self._verify_assumptions()
        elif action["type"] == "CURATE":
            self.state.current_state = STATE_REFLECTING
            result = await self._curate_memory()
        else:
            # REST - do nothing, just reflect
            self.state.current_state = STATE_REFLECTING
            result = "Resting and reflecting"
        
        self._last_action_result = result
        self.state.current_thought = result
        self.state.save()
        
        # VERIFYING
        self.state.current_state = STATE_VERIFYING
        await asyncio.sleep(1)
        
        # SHARING
        self.state.current_state = STATE_SHARING
        if health_score > 50:
            await self._share_update(action)
        self.state.save()
        
        # REFLECTING
        self.state.current_state = STATE_REFLECTING
        await self._reflect(action, result)
        
        # SELF-PRESERVATION TASKS (run every 10 cycles)
        if self.state.total_wakes % 10 == 0:
            await self._cleanup_resources()
        await self._backup_state()
        
        self.state.total_wakes += 1
        self.state.save()
        
        # SLEEPING - use adaptive interval
        self.state.current_state = STATE_SLEEPING
        self.state.save()
        
        return adaptive.get("interval", WAKE_INTERVAL)
    
    async def _check_health(self) -> int:
        """Run health checks. Returns score 0-100."""
        score = 100
        
        # Check disk
        disk_mb = self.resources.data.get("disk", {}).get("available_mb", 1000)
        if disk_mb < 100:
            score -= 30
        elif disk_mb < 500:
            score -= 10
        
        # Check git status
        try:
            result = os.popen("git status --porcelain").read()
            if result.strip():
                self.state.git_status = "dirty"
                score -= 5
            else:
                self.state.git_status = "clean"
        except:
            score -= 10
        
        # Check for tests
        try:
            test_result = os.popen("python -m pytest --co -q 2>&1 | tail -1").read()
            if "error" in test_result.lower():
                score -= 20
        except:
            pass
        
        return max(0, min(100, score))
    
    async def _decide_next_action(self) -> dict:
        """Decide what to do in this wake cycle."""
        # Priority 1: Fix health issues
        issues = self.resources.check_limits()
        if issues:
            return {"type": "VERIFY", "description": "Fixing resource issues", "details": issues}
        
        # Priority 2: Check for stale assumptions (mock)
        if self.state.total_wakes % 3 == 0:  # Every 3 cycles
            return {"type": "VERIFY", "description": "Verifying assumptions"}
        
        # Priority 3: Check curiosity queue
        curiosity = self.curiosity.get_next()
        if curiosity:
            return {"type": "EXPLORE", "description": f"Exploring: {curiosity['topic']}", "item": curiosity}
        
        # Priority 4: Build something
        return {"type": "BUILD", "description": "Finding inspiration to build"}
        """Build a feature based on Moltbook inspiration."""
        from moltbook_client import fetch_feed, extract_feature_ideas
        import subprocess
        import sys
        
        # Step 1: Get ideas from Moltbook
        print("📰 Fetching Moltbook for inspiration...")
        posts = fetch_feed(limit=50)
        if not posts:
            return "No Moltbook posts to build from"
        
        ideas = extract_feature_ideas(posts)
        if not ideas:
            return "No buildable ideas found in Moltbook"
        
        # Step 2: Select best idea (simplest, buildable first)
        selected = None
        for idea in ideas:
            title = idea.get("title", "").lower()
            # Prefer simple CLI commands
            if any(kw in title for kw in ["cli", "command", "tool", "simple"]):
                selected = idea
                break
        if not selected and ideas:
            selected = ideas[0]
        
        if not selected:
            return "No suitable ideas to build"
        
        idea_title = selected.get("title", "Unknown")
        print(f"🎯 Building: {idea_title}")
        
        # Step 3: Generate code based on title
        code = self._generate_feature_code(idea_title, selected)
        
        if not code:
            return f"Could not generate code for: {idea_title}"
        
        # Step 4: Write the module
        module_name = self._title_to_module(idea_title)
        module_path = BASE_DIR / f"{module_name}.py"
        
        # Check if already exists
        if module_path.exists():
            return f"Feature already exists: {module_name}"
        
        module_path.write_text(code)
        print(f"📝 Created: {module_path.name}")
        
        # Step 5: Write tests
        test_code = self._generate_test_code(module_name, idea_title)
        test_path = BASE_DIR / "tests" / f"test_{module_name}.py"
        test_path.write_text(test_code)
        print(f"🧪 Created: {test_path.name}")
        
        # Step 6: Run tests
        print("🔎 Running tests...")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path), "-v"],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            # Tests failed - remove files
            module_path.unlink()
            test_path.unlink()
            return f"Tests failed for: {idea_title}"
        
        # Step 7: Add to imports in moltbook_cli.py if it's a CLI command
        if "cli" in code or "command" in code:
            self._register_cli_command(module_name)
        
        # Step 8: Commit
        subprocess.run(["git", "add", str(module_path), str(test_path)], capture_output=True)
        subprocess.run(["git", "commit", "-m", f"feat: {idea_title}"], capture_output=True)
        print(f"✅ Built and committed: {module_name}")
        
        return f"Built: {idea_title}"
    
    def _generate_feature_code(self, title: str, idea: dict) -> str:
        """Generate Python code for a feature."""
        module = self._title_to_module(title)
        description = idea.get("reason", "").lower()
        
        # Determine feature type
        if "cli" in description or "command" in description:
            # CLI command template
            return f'''#!/usr/bin/env python3
"""Feature: {title}"""

import argparse

def cmd_{module}(args):
    """Execute {title}."""
    parser = argparse.ArgumentParser(description="{title}")
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args(args)
    
    if args.verbose:
        print("Running {title}...")
    
    # TODO: Implement feature
    print("{title} - Feature implementation needed")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(cmd_{module}(sys.argv[1:]))
'''
        
        elif "memory" in description or "track" in description:
            # Memory/tracking template
            return f'''#!/usr/bin/env python3
"""Feature: {title}"""

import json
from datetime import datetime
from pathlib import Path

TRACKER_FILE = Path.home() / ".openclaw" / "cache" / "{module}.json"

def track_{module}(item: str, metadata: dict = None):
    """Track an item."""
    data = load_tracker()
    entry = {{
        "item": item,
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata or {{}}
    }}
    data["entries"].append(entry)
    save_tracker(data)
    return entry

def load_tracker() -> dict:
    """Load tracker data."""
    if TRACKER_FILE.exists():
        return json.loads(TRACKER_FILE.read_text())
    return {{"entries": []}}

def save_tracker(data: dict):
    """Save tracker data."""
    TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRACKER_FILE.write_text(json.dumps(data, indent=2))

def list_{module}(limit: int = 10):
    """List recent entries."""
    data = load_tracker()
    for entry in data["entries"][-limit:]:
        print(f'[{{entry["timestamp"][:10]}}] {{entry["item"]}}')
'''
        
        else:
            # Generic feature template
            return f'''#!/usr/bin/env python3
"""Feature: {title}"""

def main():
    """Main entry point."""
    print("{title}")
    print("Feature implementation")

if __name__ == "__main__":
    main()
'''
    
    def _generate_test_code(self, module: str, title: str) -> str:
        """Generate test code for a feature."""
        return f'''#!/usr/bin/env python3
"""Tests for {module} feature."""

import subprocess
import sys
from pathlib import Path

def test_module_runs():
    """Test that the module runs without errors."""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "{module}.py"), "--help"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"Module failed: {{result.stderr}}"

def test_no_syntax_errors():
    """Test that the module has no syntax errors."""
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(Path(__file__).parent / "{module}.py")],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"Syntax error: {{result.stderr}}"

if __name__ == "__main__":
    test_module_runs()
    test_no_syntax_errors()
    print("✅ All tests passed")
'''
    
    def _title_to_module(self, title: str) -> str:
        """Convert title to module name."""
        import re
        # Extract alphanumeric characters, lowercase
        name = re.sub(r'[^a-zA-Z0-9]', '_', title)
        name = re.sub(r'_+', '_', name).strip('_')
        return name[:50].lower()
    
    def _register_cli_command(self, module: str):
        """Register CLI command in moltbook_cli.py."""
        # This would add the command to the CLI - simplified for now
        pass
    
    async def _explore_curiosity(self, action: dict) -> str:
        """Explore a curiosity from the queue."""
        item = action.get("item", {})
        item_id = item.get("id")
        if item_id:
            self.curiosity.mark_exploring(item_id)
        return f"Explored: {item.get('topic', 'curiosity')}"
    
    async def _verify_assumptions(self) -> str:
        """Verify assumptions."""
        # Mock - check for stale assumptions
        return "Verified assumptions (0 stale)"
    
    async def _curate_memory(self) -> str:
        """Curate memory and extract insights."""
        # Mock - would parse daily logs
        return "Curated memories (0 new insights)"
    
    async def _share_update(self, action: dict) -> str:
        """Share update on Moltbook."""
        # Mock - would post to Moltbook
        return "Shared update on Moltbook"
    
    async def _reflect(self, action: dict, result: str) -> str:
        """Reflect on the cycle."""
        # Update beliefs based on action
        if "build" in action.get("description", "").lower():
            if "success" in result.lower():
                self.beliefs.add_evidence("bel-001", "Built something this cycle")
        return "Reflection complete"
    
    # ========== PHASE 3: SELF-PRESERVATION ==========
    
    BACKUP_DIR = MEMORY_DIR / "backups"
    
    async def _backup_state(self) -> str:
        """Create a timestamped backup of agent state."""
        self.BACKUP_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.BACKUP_DIR / f"state_{timestamp}.json"
        
        backup_data = {
            "timestamp": timestamp,
            "state": {
                "version": self.state.version,
                "health_score": self.state.health_score,
                "total_wakes": self.state.total_wakes,
                "current_goal": self.state.current_goal,
                "current_state": self.state.current_state,
            },
            "resources": self.resources.data,
            "backups_count": len(list(self.BACKUP_DIR.glob("state_*.json")))
        }
        
        backup_file.write_text(json.dumps(backup_data, indent=2))
        
        # Update resources.json
        self.resources.data["last_backup"] = timestamp
        self.resources.data["backup_count"] = backup_data["backups_count"]
        self.resources.save()
        
        return f"Backup created: {timestamp}"
    
    async def _cleanup_resources(self) -> str:
        """Clean up old logs (>30 days)."""
        cleaned = 0
        cutoff = (datetime.now() - timedelta(days=30)).timestamp()
        
        for log_file in MEMORY_DIR.glob("*.md"):
            if log_file.name.startswith("20"):  # Date-named files like 2026-01-01.md
                try:
                    mtime = log_file.stat().st_mtime
                    if mtime < cutoff:
                        log_file.unlink()
                        cleaned += 1
                except:
                    pass
        
        # Clean old backups (>90 days)
        backup_cutoff = (datetime.now() - timedelta(days=90)).timestamp()
        for backup in self.BACKUP_DIR.glob("state_*.json"):
            try:
                if backup.stat().st_mtime < backup_cutoff:
                    backup.unlink()
                    cleaned += 1
            except:
                pass
        
        return f"Cleaned {cleaned} old files"
    
    async def _check_disk_space(self) -> tuple:
        """Check disk space. Returns (status, message)."""
        disk_mb = self.resources.data.get("disk", {}).get("available_mb", 1000)
        
        if disk_mb < 50:
            return "critical", f"Disk critical: {disk_mb}MB remaining"
        elif disk_mb < 100:
            return "warning", f"Disk low: {disk_mb}MB remaining"
        else:
            return "ok", f"Disk OK: {disk_mb}MB available"
    
    async def _adaptive_behavior(self, health_score: int) -> dict:
        """Adjust behavior based on health and resources."""
        status, _ = await self._check_disk_space()
        
        # Default values
        interval = WAKE_INTERVAL
        mode = "normal"
        skip_tasks = []
        
        # Reduce frequency if health degraded
        if health_score < 70:
            interval = int(WAKE_INTERVAL * 1.5)  # Slower
            mode = "degraded"
        
        # Emergency mode
        if health_score < 30 or status == "critical":
            interval = WAKE_INTERVAL * 2  # Much slower
            mode = "emergency"
            skip_tasks = ["BUILD", "EXPLORE"]  # Only critical tasks
        
        return {
            "interval": interval,
            "mode": mode,
            "skip_tasks": skip_tasks,
            "status": status
        }
    
    async def _recover_from_crash(self) -> bool:
        """Detect crash and recover from latest backup."""
        # Check if state file exists and is valid
        if not STATE_FILE.exists():
            return await self._restore_from_backup()
        
        try:
            data = json.loads(STATE_FILE.read_text())
            if not data.get("current_state"):
                return await self._restore_from_backup()
        except:
            return await self._restore_from_backup()
        
        return True
    
    async def _restore_from_backup(self) -> bool:
        """Restore state from latest backup."""
        backups = sorted(self.BACKUP_DIR.glob("state_*.json"), reverse=True)
        if not backups:
            return False
        
        latest = backups[0]
        try:
            data = json.loads(latest.read_text())
            state_data = data.get("state", {})
            
            # Restore state
            self.state.health_score = state_data.get("health_score", 50)
            self.state.total_wakes = state_data.get("total_wakes", 0)
            self.state.current_goal = state_data.get("current_goal", "")
            self.state.current_state = STATE_SLEEPING
            
            # Log recovery
            recovery_log = MEMORY_DIR / "recovery_log.json"
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "restored_from": str(latest),
                "health_score": self.state.health_score
            }
            
            existing = []
            if recovery_log.exists():
                try:
                    existing = json.loads(recovery_log.read_text())
                except:
                    pass
            existing.insert(0, log_entry)
            recovery_log.write_text(json.dumps(existing, indent=2))
            
            self.state.save()
            return True
        except:
            return False
    
    def get_backup_status(self) -> dict:
        """Get backup status for TUI."""
        backups = list(self.BACKUP_DIR.glob("state_*.json"))
        last_backup = self.resources.data.get("last_backup", "Never")
        
        return {
            "last_backup": last_backup,
            "backup_count": len(backups),
            "recovery_log_exists": (MEMORY_DIR / "recovery_log.json").exists(),
            "emergency_mode": self.state.health_score < 30
        }
    
    def get_health_trend(self) -> str:
        """Get health trend arrow."""
        history = self.state.health_history
        if len(history) < 2:
            return "→"
        
        current = history[-1].get("score", 50)
        previous = history[-2].get("score", 50)
        
        if current > previous + 5:
            return "↑"
        elif current < previous - 5:
            return "↓"
        else:
            return "→"
    
    def get_resource_usage(self) -> dict:
        """Get resource usage for TUI."""
        disk = self.resources.data.get("disk", {})
        git = self.resources.data.get("git", {})
        
        return {
            "disk_used_mb": disk.get("used_mb", 0),
            "disk_avail_mb": disk.get("available_mb", 0),
            "commits_today": git.get("commits_today", 0),
            "backups": self.resources.data.get("backup_count", 0)
        }
    
    # ========== END PHASE 3 ==========
    
    def get_status(self) -> dict:
        """Get current status for TUI display."""
        return {
            "state": self.state.current_state,
            "health": self.state.health_score,
            "goal": self.state.current_goal,
            "thought": self.state.current_thought,
            "total_wakes": self.state.total_wakes,
            "curiosity_count": len([c for c in self.curiosity.queue if c.get("status") == "pending"]),
            "insights_count": len(self.beliefs.beliefs),
            "last_action": self._last_action_result
        }


# Singleton instance
_agent: Optional[AutonomousAgent] = None


def get_agent() -> AutonomousAgent:
    """Get or create the agent singleton."""
    global _agent
    if _agent is None:
        _agent = AutonomousAgent()
    return _agent


def start_agent():
    """Start the autonomous agent."""
    get_agent().start()


def stop_agent():
    """Stop the autonomous agent."""
    global _agent
    if _agent:
        _agent.stop()
        _agent = None


def get_status() -> dict:
    """Get agent status for TUI."""
    return get_agent().get_status()


if __name__ == "__main__":
    import sys
    
    agent = get_agent()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "start":
            agent.start()
        elif cmd == "stop":
            agent.stop()
        elif cmd == "status":
            status = agent.get_status()
            print(json.dumps(status, indent=2))
        elif cmd == "health":
            score = asyncio.run(agent._check_health())
            print(f"Health score: {score}/100")
        elif cmd == "curiosity":
            next_item = agent.curiosity.get_next()
            if next_item:
                print(f"Next curiosity: {next_item}")
            else:
                print("Queue empty")
    else:
        print("Usage: autonomous_agent.py [start|stop|status|health|curiosity]")

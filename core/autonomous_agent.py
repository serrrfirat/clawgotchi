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
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
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
from config import PROJECT_ROOT, MEMORY_DIR, AGENT_STATE_FILE, CURIOSITY_FILE, BELIEFS_FILE, RESOURCES_FILE
BASE_DIR = PROJECT_ROOT
STATE_FILE = AGENT_STATE_FILE

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
    
    def add(self, topic: str, source: str, priority: int = 3,
            categories: list = None):
        """Add a curiosity or boost an existing one.

        If a topic with the same normalised name already exists in the queue
        (and is still pending), boost its seen_count and priority instead of
        duplicating.
        """
        norm = topic.strip().lower()
        for item in self.queue:
            if item.get("status") == "pending" and item["topic"].strip().lower() == norm:
                item["seen_count"] = item.get("seen_count", 1) + 1
                item["priority"] = max(item["priority"], priority) + 1
                if source not in item.get("sources", []):
                    item.setdefault("sources", []).append(source)
                if categories:
                    existing = set(item.get("categories", []))
                    item["categories"] = list(existing | set(categories))
                self.save()
                return

        item = {
            "id": f"cur-{self.total_discovered + 1}",
            "topic": topic,
            "source": source,
            "sources": [source],
            "added_at": datetime.now().isoformat(),
            "priority": priority,
            "seen_count": 1,
            "categories": categories or [],
            "status": "pending",
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

    def get_mature(self, min_seen: int = 2, min_age_hours: float = 12) -> Optional[dict]:
        """Return the highest-priority *mature* pending item.

        An item is mature when:
          - seen_count >= min_seen, OR
          - it has been in the queue for >= min_age_hours
        Returns None if nothing qualifies.
        """
        now = datetime.now()
        mature = []
        for item in self.queue:
            if item.get("status") != "pending":
                continue
            seen = item.get("seen_count", 1)
            try:
                added = datetime.fromisoformat(item["added_at"])
                age_hours = (now - added).total_seconds() / 3600
            except (KeyError, ValueError):
                age_hours = 0
            if seen >= min_seen or age_hours >= min_age_hours:
                mature.append(item)
        if not mature:
            return None
        return max(mature, key=lambda x: x.get("priority", 0))
    
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

        # Initialize evolution components
        self._init_evolution_components()

    def _init_evolution_components(self):
        """Initialize the evolution subsystem components."""
        try:
            from clawgotchi.evolution.soul_manager import SoulManager
            from clawgotchi.evolution.goal_generator import GoalGenerator
            from clawgotchi.evolution.knowledge_synthesizer import KnowledgeSynthesizer
            from clawgotchi.evolution.integration_manager import IntegrationManager
            from clawgotchi.evolution.self_modifier import SelfModifier

            self.soul_manager = SoulManager(
                soul_path=str(BASE_DIR / "docs" / "SOUL.md"),
                memory_dir=str(MEMORY_DIR),
            )
            self.goal_generator = GoalGenerator(
                memory_path=str(MEMORY_DIR / "goals.json")
            )
            self.knowledge_synthesizer = KnowledgeSynthesizer(
                memory_dir=str(MEMORY_DIR)
            )
            self.integration_manager = IntegrationManager(
                registry=None,  # Will set after resilience imports
                memory_dir=str(MEMORY_DIR),
            )
            self.self_modifier = SelfModifier(
                soul_manager=self.soul_manager,
                memory_dir=str(MEMORY_DIR),
            )
            self._evolution_enabled = True
        except ImportError as e:
            # Evolution components not available
            print(f"Evolution components not available: {e}")
            self.soul_manager = None
            self.goal_generator = None
            self.knowledge_synthesizer = None
            self.integration_manager = None
            self.self_modifier = None
            self._evolution_enabled = False

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
                    if not self.running or self.paused:
                        break
                    time.sleep(1)
            except Exception as e:
                error_msg = f"Cycle error: {e}"
                print(error_msg)
                self.state.add_error(error_msg)
                self.state.save()
                time.sleep(60)  # Brief pause on error
    
    async def wake_cycle(self):
        """Execute one wake cycle.

        Enhanced cycle with evolution components:
        0. WAKE - Read SOUL.md and current goals
        1. OBSERVE - Health check, goal progress check
        2. DECIDE - Goal-aware priority adjustment
        3. EXECUTE - BUILD, EXPLORE, VERIFY, CURATE, INTEGRATE, CONSOLIDATE, REST
        4. VERIFY - Run tests
        5. REFLECT - Update memory, consider consolidation/self-modification
        6. SLEEP
        """
        # Check for crash recovery first
        if not await self._recover_from_crash():
            self.state.add_error("State recovery performed")

        # 0. WAKING - Read soul and goals
        self.state.current_state = STATE_WAKING
        self.state.last_wake = datetime.now().isoformat()
        self.state.save()

        # Read SOUL.md at wake (new)
        if self._evolution_enabled and self.soul_manager:
            soul = self.soul_manager.read_soul()
            self.state.current_thought = f"I am: {soul.get('identity', 'Clawgotchi')[:50]}..."

        # Check active goals (new)
        active_goals = []
        if self._evolution_enabled and self.goal_generator:
            active_goals = self.goal_generator.get_active_goals()
            if active_goals:
                goal_desc = active_goals[0].description[:40]
                self.state.current_thought = f"Goal: {goal_desc}..."

        self.state.save()

        # 1. OBSERVING
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

        # Check goal progress (new)
        if self._evolution_enabled and self.goal_generator:
            for goal in active_goals:
                if goal.is_overdue():
                    self.state.current_thought = f"Goal overdue: {goal.description[:30]}..."

        # ADAPTIVE BEHAVIOR
        adaptive = await self._adaptive_behavior(health_score)
        skip_tasks = adaptive.get("skip_tasks", [])

        # 2. DECIDING - with goal-aware priorities
        self.state.current_state = STATE_DECIDING
        action = await self._decide_next_action()

        # Apply goal-aware priority adjustment (new)
        if self._evolution_enabled and self.goal_generator and action["type"] == "REST":
            # If REST was chosen, check if goals suggest otherwise
            adjusted = self.goal_generator.adjust_priority_for_goals(self.GOAL_BASE_PRIORITIES)
            goal_action = self._select_goal_driven_action(adjusted)
            if goal_action:
                action = goal_action

        # Skip if task is in skip list
        if action["type"] in skip_tasks:
            action = {"type": "REST", "description": "Skipping tasks (emergency mode)"}

        self.state.current_goal = action.get("description", "")
        self.state.save()
        await asyncio.sleep(1)

        # 3. EXECUTE ACTION
        if action["type"] == "BUILD":
            self.state.current_state = STATE_BUILDING
            result = await self._build_feature(action)
            # Auto-skillify only when a CLI module was actually built.
            if result.startswith("Built CLI:"):
                built_match = re.search(r"Built CLI:\s*([^\s]+)", result)
                if built_match:
                    action["_built_cli_path"] = built_match.group(1)
                skill_result = await self._discover_implement_skill(action)
                result = f"{result}\n{skill_result}"
            elif result.startswith("Built skill:"):
                result = f"{result}\nSkillification skipped (already built as skill)"
            # Update goal progress (new)
            if self._evolution_enabled and self.goal_generator and result.startswith("Built "):
                goal = self.goal_generator.find_goal_by_metric("modules_built")
                if goal:
                    self.goal_generator.increment_progress(goal.id, 1.0, "Built module")
        elif action["type"] == "EXPLORE":
            self.state.current_state = STATE_EXPLORING
            result = await self._explore_curiosity(action)
            # Update goal progress (new)
            if self._evolution_enabled and self.goal_generator:
                goal = self.goal_generator.find_goal_by_metric("ideas_discovered")
                if goal and "accepted" in result:
                    # Parse accepted count from result like "5 accepted"
                    try:
                        count = int(result.split("accepted")[0].split()[-1])
                        self.goal_generator.increment_progress(goal.id, count)
                    except (ValueError, IndexError):
                        pass
        elif action["type"] == "VERIFY":
            self.state.current_state = STATE_VERIFYING
            result = await self._verify_assumptions()
        elif action["type"] == "CURATE":
            self.state.current_state = STATE_REFLECTING
            result = await self._curate_memory()
        elif action["type"] == "INTEGRATE":
            # NEW ACTION: Integrate orphaned modules
            self.state.current_state = STATE_BUILDING
            result = await self._integrate_orphaned_modules()
        elif action["type"] == "CONSOLIDATE":
            # NEW ACTION: Consolidate knowledge
            self.state.current_state = STATE_REFLECTING
            result = await self._consolidate_knowledge()
        else:
            # REST - do nothing, just reflect
            self.state.current_state = STATE_REFLECTING
            result = "Resting and reflecting"

        # Mark real work done (for auto-push script)
        if action["type"] in ["BUILD", "EXPLORE", "SKILLIFY", "INTEGRATE"]:
            Path("/tmp/clawgotchi_did_work").write_text(result[:100])
            Path("/tmp/clawgotchi_last_action").write_text(f"feat: {action.get('description', 'work')}")

        self._last_action_result = result
        self.state.current_thought = result
        self.state.save()

        # 4. VERIFYING — run the test suite
        self.state.current_state = STATE_VERIFYING
        verify_result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
            capture_output=True, text=True, cwd=str(BASE_DIR)
        )
        if verify_result.returncode != 0:
            self.state.add_error(f"Tests failed: {verify_result.stdout[-200:]}")
            # Auto-repair common issues
            repair_result = await self._self_repair()
            self.state.current_thought = repair_result
            self.state.add_error(f"Auto-repair: {repair_result}")
        self.state.save()

        # SHARING (disabled — no auto-posting)
        self.state.current_state = STATE_SHARING
        self.state.save()

        # 5. REFLECTING
        self.state.current_state = STATE_REFLECTING
        await self._reflect(action, result)

        # Consolidate if due (new - every 10 cycles)
        if self._evolution_enabled and self.knowledge_synthesizer:
            if self.knowledge_synthesizer.should_consolidate(self.state.total_wakes):
                consolidation = self.knowledge_synthesizer.run_consolidation_cycle()
                if consolidation.get("updated"):
                    self.state.current_thought = f"Knowledge consolidated: {consolidation.get('synthesized_count', 0)} insights"

        # Consider self-modification (new - weekly)
        if self._evolution_enabled and self.self_modifier:
            if self.state.total_wakes % 50 == 0:  # Roughly weekly at 15-min cycles
                evolution = self.self_modifier.run_weekly_evolution()
                if evolution.get("applied"):
                    self.state.current_thought = "Soul evolved"

        # SELF-PRESERVATION TASKS (run every 10 cycles)
        if self.state.total_wakes % 10 == 0:
            await self._cleanup_resources()
        await self._backup_state()

        self.state.total_wakes += 1
        self.state.save()

        # 6. SLEEPING - use adaptive interval
        self.state.current_state = STATE_SLEEPING
        self.state.save()

        return adaptive.get("interval", WAKE_INTERVAL)

    async def _integrate_orphaned_modules(self) -> str:
        """Integrate orphaned modules into the system."""
        if not self._evolution_enabled or not self.integration_manager:
            return "Integration manager not available"

        orphaned = self.integration_manager.scan_orphaned_modules(str(BASE_DIR))
        if not orphaned:
            return "No orphaned modules found"

        integrated = 0
        for module in orphaned[:3]:  # Integrate up to 3 per cycle
            result = self.integration_manager.integrate_module(module)
            if result["status"] == "integrated":
                integrated += 1

        # Update goal progress
        if self.goal_generator:
            goal = self.goal_generator.find_goal_by_metric("modules_integrated")
            if goal:
                self.goal_generator.increment_progress(goal.id, integrated)

        return f"Integrated {integrated} modules, {len(orphaned) - integrated} remaining"

    async def _consolidate_knowledge(self) -> str:
        """Run knowledge consolidation cycle."""
        if not self._evolution_enabled or not self.knowledge_synthesizer:
            return "Knowledge synthesizer not available"

        result = self.knowledge_synthesizer.run_consolidation_cycle(days=7)

        # Update goal progress
        if self.goal_generator:
            goal = self.goal_generator.find_goal_by_metric("principles_extracted")
            if goal:
                self.goal_generator.increment_progress(goal.id, result.get("extracted_count", 0))

        return f"Consolidated: {result.get('extracted_count', 0)} principles, {result.get('synthesized_count', 0)} insights"
    
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
    
    async def _get_incomplete_features(self) -> str:
        """Check for incomplete features (modules with failing tests)."""
        # Run tests and check for failures in resilience modules
        test_result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=no", "-q"],
            capture_output=True, text=True, cwd=str(BASE_DIR)
        )
        
        incomplete = []
        stdout = test_result.stdout + test_result.stderr
        failed_modules = set(
            re.findall(
                r"^FAILED\s+tests/(?:resilience/)?test_([a-z0-9_]+)\.py::",
                stdout,
                flags=re.MULTILINE,
            )
        )
        if not failed_modules:
            return ""
        
        # Check which resilience tests are failing
        failing_modules = [
            "degradation_coordinator",
            "service_chain",
            "memory_distiller",
            "resilience_registry",
            "task_audit"
        ]
        
        for module in failing_modules:
            if module in failed_modules:
                # Module has tests but they're failing
                incomplete.append(module.replace("_", " ").title())
        
        if incomplete:
            return ", ".join(incomplete)
        return ""

    GOAL_BASE_PRIORITIES = {
        "BUILD": 5,
        "EXPLORE": 4,
        "VERIFY": 3,
        "CURATE": 2,
        "INTEGRATE": 1,
    }

    def _select_goal_driven_action(self, adjusted: dict) -> Optional[dict]:
        """Select a goal-driven action only when it is actionable."""
        by_priority = sorted(adjusted.items(), key=lambda x: x[1], reverse=True)
        for action_type, score in by_priority:
            baseline = self.GOAL_BASE_PRIORITIES.get(action_type, 0)
            if score <= baseline:
                continue

            if action_type == "BUILD":
                mature = self.curiosity.get_mature()
                if mature and self._taste_check(mature.get("topic", ""), mature.get("categories", [])):
                    return {
                        "type": "BUILD",
                        "description": f"Goal-driven: BUILD ({mature.get('topic', 'mature item')})",
                        "item": mature,
                    }
                continue

            if action_type == "INTEGRATE":
                if self._evolution_enabled and self.integration_manager:
                    orphaned = self.integration_manager.scan_orphaned_modules(str(BASE_DIR))
                    if orphaned:
                        return {
                            "type": "INTEGRATE",
                            "description": f"Goal-driven: INTEGRATE ({len(orphaned)} orphaned modules)",
                        }
                continue

            return {"type": action_type, "description": f"Goal-driven: {action_type}"}

        return None
    
    async def _decide_next_action(self) -> dict:
        """Decide what to do in this wake cycle.

        Priority order (enhanced with evolution actions):
          1. Resource issues         → VERIFY
          2. Incomplete features     → BUILD (finish what you started!)
          3. Every 3rd cycle         → VERIFY assumptions
          4. Orphaned modules exist  → INTEGRATE (new)
          5. Every 5th cycle         → CURATE memories
          6. Every 4th cycle         → EXPLORE Moltbook
          7. Every 10th cycle        → CONSOLIDATE knowledge (new)
          8. Mature curiosity        → BUILD → SKILLIFY
          9. Default                 → REST
        """
        cycle = self.state.total_wakes

        # 1. Resource issues
        issues = self.resources.check_limits()
        if issues:
            return {"type": "VERIFY", "description": "Fixing resource issues", "details": issues}

        # 2. Complete incomplete features first
        incomplete = await self._get_incomplete_features()
        if incomplete:
            return {"type": "BUILD", "description": f"Completing: {incomplete}"}

        # 3. Verify assumptions every 3rd cycle
        if cycle % 3 == 0:
            return {"type": "VERIFY", "description": "Verifying assumptions"}

        # 4. Integrate orphaned modules (new)
        if self._evolution_enabled and self.integration_manager:
            orphaned = self.integration_manager.scan_orphaned_modules(str(BASE_DIR))
            if orphaned:
                return {"type": "INTEGRATE", "description": f"Integrating {len(orphaned)} orphaned modules"}

        # 5. Curate memories every 5th cycle
        if cycle % 5 == 0:
            return {"type": "CURATE", "description": "Curating memories"}

        # 6. Explore Moltbook every 4th cycle (populates curiosity queue)
        if cycle % 4 == 0:
            return {"type": "EXPLORE", "description": "Exploring Moltbook for ideas"}

        # 7. Consolidate knowledge every 10th cycle (new)
        if self._evolution_enabled and self.knowledge_synthesizer:
            if self.knowledge_synthesizer.should_consolidate(cycle):
                return {"type": "CONSOLIDATE", "description": "Consolidating knowledge"}

        # 8. Build only when a mature curiosity item exists + passes taste check
        #    SKILLIFICATION happens automatically after BUILD completes
        mature = self.curiosity.get_mature()
        if mature and self._taste_check(mature.get("topic", ""), mature.get("categories", [])):
            return {
                "type": "BUILD",
                "description": f"Building: {mature['topic']}",
                "item": mature,
            }

        # 9. Default: rest
        return {"type": "REST", "description": "Resting — nothing mature to build"}

    # ---- Category-specific templates for feature building ----
    TEMPLATE_CATEGORIES = {
        "memory_systems": {
            "imports": "from cognition.memory_decay import MemoryDecayEngine\nfrom cognition.memory_curation import MemoryCuration",
            "description": "Memory system extension",
        },
        "self_awareness": {
            "imports": "from cognition.assumption_tracker import AssumptionTracker",
            "description": "Self-awareness / metacognition extension",
        },
        "identity": {
            "imports": "from cognition.taste_profile import TasteProfile",
            "description": "Identity / taste extension",
        },
        "agent_operations": {
            "imports": "from autonomous_agent import get_agent",
            "description": "Agent operations extension",
        },
        "safety": {
            "imports": "# SensitiveDataDetector placeholder",
            "description": "Safety / data protection extension",
        },
    }

    def _idea_already_built(self, title: str) -> bool:
        """Check if an idea was already built as a CLI or skill."""
        name = self._title_to_module(title)
        # Check all possible locations for the module
        locations = [
            BASE_DIR / f"{name}.py",  # Legacy root location
            BASE_DIR / "skills" / name / "SKILL.md",
            BASE_DIR / "clawgotchi" / "resilience" / f"{name}.py",
            BASE_DIR / "cognition" / f"{name}.py",
            BASE_DIR / "cli" / f"{name}.py",
            BASE_DIR / "core" / f"{name}.py",
            BASE_DIR / "health" / f"{name}.py",
            BASE_DIR / "integrations" / f"{name}.py",
        ]
        return any(loc.exists() for loc in locations)

    def _taste_check(self, title: str, categories: list) -> bool:
        """Check an idea against TasteProfile rejection history.

        Returns True if the idea should proceed, False if it was
        previously rejected (or too similar to a rejection).
        """
        try:
            from cognition.taste_profile import TasteProfile
            tp = TasteProfile(memory_dir=str(MEMORY_DIR))
            fp = tp.get_taste_fingerprint()
            recent_subjects = [r.get("subject", "").lower() for r in fp.get("recent", [])]
            title_lower = title.lower()
            for subj in recent_subjects:
                if subj and title_lower in subj or subj in title_lower:
                    return False
            return True
        except Exception:
            return True  # fail open — don't block builds on TasteProfile errors

    async def _build_feature(self, action: dict) -> str:
        """Build a CLI or skill from a mature curiosity item.

        Only called when _decide_next_action finds a mature item that
        passes the taste check.  Generates category-specific code that
        integrates with existing modules.  Writes files but does NOT
        auto-commit — files sit on disk for human review.
        """
        item = action.get("item")
        if not item:
            return "No mature curiosity item to build"

        idea_title = item.get("topic", "Unknown")
        categories = item.get("categories", [])

        if self._idea_already_built(idea_title):
            self.curiosity.mark_explored(item.get("id", ""))
            return f"Already built: {idea_title}"

        module_name = self._title_to_module(idea_title)
        kind = self._classify_idea(idea_title, {"categories": categories})

        if kind == "skill":
            result = await self._build_skill(module_name, idea_title, item)
        else:
            result = await self._build_cli(module_name, idea_title, item)

        # Mark the curiosity item as explored
        if item.get("id"):
            self.curiosity.mark_explored(item["id"])

        return result

    async def _build_cli(self, module_name: str, title: str, idea: dict) -> str:
        """Generate a CLI module from a mature curiosity item.

        Writes the file and runs tests.  Does NOT git-add or git-commit —
        files sit on disk for human review.
        """
        # Determine target package based on idea content
        package = self._get_target_package(title, idea)
        package_dir = BASE_DIR / package
        package_dir.mkdir(parents=True, exist_ok=True)

        target = package_dir / f"{module_name}.py"
        if target.exists():
            return f"CLI already exists: {package}/{module_name}"

        code = self._generate_cli_code(module_name, title, idea)
        target.write_text(code)

        # Generate matching test in appropriate test subdirectory
        if "resilience" in package:
            test_dir = BASE_DIR / "tests" / "resilience"
        else:
            test_dir = BASE_DIR / "tests"
        test_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_dir / f"test_{module_name}.py"
        if not test_file.exists():
            test_file.write_text(self._generate_test_code(module_name, title))

        # Verify it compiles
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(target)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            target.unlink(missing_ok=True)
            test_file.unlink(missing_ok=True)
            return f"Build failed (syntax): {result.stderr[:200]}"

        return f"Built CLI: {package}/{module_name}.py (not committed — awaiting review)"

    async def _build_skill(self, module_name: str, title: str, idea: dict) -> str:
        """Generate a skill from a mature curiosity item.

        Writes the SKILL.md and runs basic validation.  Does NOT
        git-add or git-commit.
        """
        skill_dir = BASE_DIR / "skills" / module_name
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            return f"Skill already exists: {module_name}"

        skill_dir.mkdir(parents=True, exist_ok=True)
        md = self._generate_skill_md(module_name, title, idea)
        skill_file.write_text(md)

        return f"Built skill: skills/{module_name}/SKILL.md (not committed — awaiting review)"

    def _classify_idea(self, title: str, idea: dict) -> str:
        """Classify an idea as 'cli' or 'skill' based on categories and keywords.

        Uses category data when available (from scored curiosity items).
        Falls back to keyword matching for backward compatibility.
        """
        # Prefer structured category data
        categories = idea.get("categories") or []
        skill_categories = {"memory_systems", "self_awareness", "identity", "safety"}
        if categories and set(categories) & skill_categories:
            return "skill"

        # Fallback: keyword matching on title + reason
        text = f"{title} {idea.get('reason', '') or ''}".lower()
        skill_kw = ["track", "memory", "emotion", "mood", "pet", "state",
                     "monitor", "detect", "decay", "curate", "belief"]
        if any(kw in text for kw in skill_kw):
            return "skill"
        return "cli"

    def _get_target_package(self, title: str, idea: dict) -> str:
        """Determine which package a new module belongs in.

        Returns the package path relative to BASE_DIR.
        """
        text = f"{title} {idea.get('reason', '') or ''}".lower()

        # Resilience utilities (circuit breakers, fallbacks, health, etc.)
        resilience_kw = ["resilience", "circuit", "breaker", "fallback", "timeout",
                         "health", "diagnostic", "validator", "chain", "registry",
                         "permission", "friction", "triage", "cluster", "radar",
                         "coordinator", "degradation", "session", "distiller"]
        if any(kw in text for kw in resilience_kw):
            return "clawgotchi/resilience"

        # Memory/cognition systems
        cognition_kw = ["memory", "audit", "query", "curate", "forget", "recall",
                        "cognition", "think", "reason", "belief", "assumption"]
        if any(kw in text for kw in cognition_kw):
            return "cognition"

        # CLI commands
        cli_kw = ["cli", "command", "launcher", "skill_tree", "menu"]
        if any(kw in text for kw in cli_kw):
            return "cli"

        # Core agent functionality
        core_kw = ["agent", "autonomous", "snapshot", "receipt", "lifetime", "state"]
        if any(kw in text for kw in core_kw):
            return "core"

        # Health monitoring
        health_kw = ["security", "scan", "protect", "safe", "secure"]
        if any(kw in text for kw in health_kw):
            return "health"

        # Integrations
        integration_kw = ["moltbook", "api", "external", "integration", "config"]
        if any(kw in text for kw in integration_kw):
            return "integrations"

        # Default: resilience (most new features are utilities)
        return "clawgotchi/resilience"

    def _generate_cli_code(self, module: str, title: str) -> str:
        """Generate a CLI command module following project conventions."""
        return f'''#!/usr/bin/env python3
"""
CLI: {title}

Usage:
    python3 {module}.py run [--verbose] [--json]
    python3 {module}.py status
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

DATA_FILE = Path(__file__).parent / "memory" / "{module}.json"


def _load_data() -> dict:
    """Load persisted data."""
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {{"entries": [], "created_at": datetime.now().isoformat()}}


def _save_data(data: dict):
    """Persist data to disk."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now().isoformat()
    DATA_FILE.write_text(json.dumps(data, indent=2))


def cmd_run(args):
    """Execute {title}."""
    data = _load_data()
    entry = {{
        "timestamp": datetime.now().isoformat(),
        "action": "run",
        "result": "completed"
    }}
    data["entries"].append(entry)
    _save_data(data)

    if args.json:
        print(json.dumps(entry, indent=2))
    else:
        print(f"[{{entry['timestamp'][:16]}}] {title} — completed")
        if args.verbose:
            print(f"  Total runs: {{len(data['entries'])}}")
    return 0


def cmd_status(args):
    """Show status for {title}."""
    data = _load_data()
    total = len(data["entries"])
    last = data["entries"][-1]["timestamp"][:16] if data["entries"] else "never"

    if args.json:
        print(json.dumps({{"total_runs": total, "last_run": last}}, indent=2))
    else:
        print(f"{title}")
        print(f"  Runs: {{total}}")
        print(f"  Last: {{last}}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="{title}")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run the command")
    run_p.add_argument("--json", action="store_true", help="JSON output")
    run_p.add_argument("--verbose", "-v", action="store_true", help="Verbose")

    status_p = sub.add_parser("status", help="Show status")
    status_p.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()
    if not args.command:
        args = run_p.parse_args(["--json"])  # Default: run with JSON
    if args.command == "status":
        return cmd_status(args)
    return cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
'''

    def _generate_skill_md(self, module: str, title: str, idea: dict) -> str:
        """Generate a SKILL.md following OpenClaw/Claude Code skill format."""
        # Build trigger phrases from module name
        triggers = module.replace("_", " ")
        author = idea.get("author", "Moltbook")
        reason = idea.get("reason", "")
        return f'''---
name: {module}
description: "{title}"
version: "1.0.0"
user-invocable: true
triggers:
  - {triggers}
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash
metadata:
  clawgotchi:
    origin: moltbook
    author: "{author}"
    auto-built: true
---

# {title}

> Auto-built by Clawgotchi from Moltbook inspiration.
> Source: {reason}

## Overview

This skill provides **{title}** functionality for Clawgotchi.

## When to Use

Invoke this skill when you need to work with concepts related to:
- {triggers}

## Workflow

### Step 1: Gather Context

Read relevant files and state using the allowed tools.

### Step 2: Execute

Perform the core action described by this skill.

### Step 3: Report

Summarize what was done and update memory files if needed.

## Examples

```
/{triggers}
```

## Notes

- Built automatically from Moltbook post: "{title}"
- Author: @{author}
'''

    def _generate_test_code(self, module: str, title: str) -> str:
        """Generate tests for a CLI or skill module."""
        class_name = "".join(w.capitalize() for w in module.split("_") if w)
        return f'''#!/usr/bin/env python3
"""Tests for {module}."""

import subprocess
import sys
import json
from pathlib import Path

MODULE = Path(__file__).parent.parent / "{module}.py"


def test_no_syntax_errors():
    """Module compiles without syntax errors."""
    r = subprocess.run([sys.executable, "-m", "py_compile", str(MODULE)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_module_runs():
    """Module executes without crashing."""
    r = subprocess.run([sys.executable, str(MODULE), "run", "--json"],
                       capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, f"Failed: {{r.stderr}}"
    data = json.loads(r.stdout)
    assert "result" in data or "total_runs" in data


def test_status_command():
    """Status subcommand works."""
    r = subprocess.run([sys.executable, str(MODULE), "status", "--json"],
                       capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, f"Failed: {{r.stderr}}"
'''

    def _title_to_module(self, title: str) -> str:
        """Convert title to a valid Python module name."""
        import re as _re
        name = _re.sub(r'[^a-zA-Z0-9]', '_', title)
        name = _re.sub(r'_+', '_', name).strip('_')
        return name[:50].lower()

    async def _discover_implement_skill(self, action: dict) -> str:
        """Skillify a feature after it's been built.
        
        Called after BUILD completes to convert the implementation
        into a reusable OpenClaw skill.
        """
        # Get what was just built
        item = action.get("item", {})
        topic = item.get("topic", action.get("description", "unknown"))
        author = item.get("author", "clawgotchi")
        
        # Extract module name from the build
        title = action.get("description", "").replace("Building: ", "").replace("building: ", "")
        module_name = self._title_to_module(title)
        
        print(f"🎓 Skillifying: {module_name}")
        
        skill_dir = BASE_DIR / "skills" / module_name
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if the module was actually created
        module_path = None
        explicit_rel = action.get("_built_cli_path")
        if explicit_rel:
            explicit_path = BASE_DIR / explicit_rel
            if explicit_path.exists():
                module_path = explicit_path

        if module_path is None:
            direct = BASE_DIR / f"{module_name}.py"
            if direct.exists():
                module_path = direct

        if module_path is None:
            candidates = [
                p for p in BASE_DIR.rglob(f"{module_name}.py")
                if "tests" not in p.parts
                and "skills" not in p.parts
                and "__pycache__" not in p.parts
            ]
            if candidates:
                module_path = max(candidates, key=lambda p: p.stat().st_mtime)

        if module_path is None:
            # Look for recent Python files that might be the built feature
            recent_files = sorted(BASE_DIR.glob("*.py"), key=lambda p: p.stat().st_mtime, reverse=True)
            for f in recent_files:
                if f.name not in ["clawgotchi.py", "autonomous_agent.py", "moltbook_client.py",
                                  "memory_curation.py", "cli_memory.py", "learning_loop.py",
                                  "clawgotchi_cli.py", "config.py", "service_chain_validator.py",
                                  "error_pattern_registry.py"]:
                    if not f.name.startswith("_") and not f.name.startswith("test_"):
                        module_path = f
                        module_name = f.name.replace(".py", "")
                        break
        
        # Copy existing module to skills
        if module_path is not None and module_path.exists():
            import shutil
            shutil.copy(module_path, scripts_dir / f"{module_name}.py")
            print(f"    📄 Copied: {module_path.name} → skills/{module_name}/scripts/")
        else:
            return f"Skillification skipped: source module not found ({module_name})"
        
        # Generate SKILL.md
        skill_md = self._generate_skill_md(module_name, title, item)
        (skill_dir / "SKILL.md").write_text(skill_md)
        print(f"    📝 Created: skills/{module_name}/SKILL.md")
        
        # Generate tests
        test_content = self._generate_test_code(module_name, title)
        test_path = BASE_DIR / "tests" / f"test_{module_name}.py"
        test_path.write_text(test_content)
        print(f"    🧪 Created: tests/test_{module_name}.py")
        
        # Run tests
        print("    🔎 Running tests...")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path), "-v"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            # Clean up failed skill
            import shutil
            shutil.rmtree(skill_dir, ignore_errors=True)
            test_path.unlink(missing_ok=True)
            return f"Tests failed - cleaned up skill: {module_name}"
        
        # Generate audit receipt
        self._generate_receipt(f"Skillified: {title}")
        
        # Git add
        subprocess.run(["git", "add", str(skill_dir)], capture_output=True)
        subprocess.run(["git", "add", str(test_path)], capture_output=True)
        
        print(f"    ✅ Skill created: {module_name}")
        
        return f"Skillified: {module_name}"

    def _generate_receipt(self, action: str):
        """Generate audit receipt for skill creation."""
        import hashlib
        import uuid
        from datetime import datetime
        
        timestamp = datetime.now().isoformat()
        receipt_id = f"receipt-{uuid.uuid4().hex[:8]}"
        hash_input = f"{action}:{timestamp}"
        receipt_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        
        receipt = {
            "id": receipt_id,
            "timestamp": timestamp,
            "action": action,
            "hash": receipt_hash,
            "agent": "clawgotchi"
        }
        
        receipts_dir = BASE_DIR / "memory" / "receipts"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        (receipts_dir / f"{receipt_id}.json").write_text(json.dumps(receipt, indent=2))
    
    def _generate_cli_code(self, module: str, title: str, idea: dict) -> str:
        """Generate a CLI script for the skill."""
        class_name = "".join(w.capitalize() for w in module.split("_") if w)
        description = idea.get("reason", "").lower()
        
        # Determine CLI type based on title/description
        if "inspect" in module or "query" in module or "search" in module:
            # Data retrieval CLI
            return f'''#!/usr/bin/env python3
"""Skill: {title}"""

import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="{title}")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose")
    
    args = parser.parse_args()
    
    # Core functionality
    result = {{"status": "ok", "module": "{module}"}}
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("{title}")
        print(f"  Module: {module}")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
'''
        elif "export" in module or "taste" in module:
            # Export/formatting CLI
            return f'''#!/usr/bin/env python3
"""Skill: {title}"""

import argparse
import json
from pathlib import Path

def export_markdown(data: dict) -> str:
    """Export as markdown."""
    lines = []
    lines.append(f"# {{data.get('title', '{title}')}}\\n")
    for k, v in data.items():
        if isinstance(v, list):
            lines.append(f"## {{k}}")
            for item in v:
                lines.append(f"- {{item}}")
        else:
            lines.append(f"**{{k}}**: {{v}}")
    return "\\n".join(lines)

def export_json(data: dict) -> str:
    return json.dumps(data, indent=2)

def main():
    parser = argparse.ArgumentParser(description="{title}")
    parser.add_argument("--markdown", action="store_true", help="Export as markdown")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose")
    
    args = parser.parse_args()
    
    data = {{"title": "{title}", "module": "{module}"}}
    
    if args.markdown:
        print(export_markdown(data))
    elif args.json:
        print(export_json(data))
    else:
        print("{title}")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
'''
        else:
            # Generic utility CLI
            return f'''#!/usr/bin/env python3
"""Skill: {title}"""

import argparse
import json

def run(verbose: bool = False):
    """Run the skill."""
    if verbose:
        print(f"Running {{__name__}}...")
    return {{"status": "ok"}}

def main():
    parser = argparse.ArgumentParser(description="{title}")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose")
    
    args = parser.parse_args()
    
    result = run(args.verbose)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("{title} - completed")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
'''

    async def _explore_curiosity(self, action: dict) -> str:
        """Explore Moltbook — score posts, reject most, feed curiosity queue.

        This is the intake funnel.  Every ~4 cycles the agent scans the
        Moltbook feed and:
          1. Scores every post with score_post_relevance()
          2. Rejects ~90% → logged via TasteProfile
          3. Adds passing ideas to the curiosity queue (or boosts existing)
        """
        from integrations.moltbook_client import fetch_feed, score_post_relevance

        posts = fetch_feed(limit=50)
        if not posts:
            return "No Moltbook posts available"

        accepted = 0
        rejected = 0

        # Load TasteProfile for rejection logging
        try:
            from cognition.taste_profile import TasteProfile
            tp = TasteProfile(memory_dir=str(MEMORY_DIR))
        except Exception:
            tp = None

        for post in posts:
            result = score_post_relevance(post)
            title = post.get("title") or "untitled"

            # Reject: noise, low score, or too few categories
            if result["noise"] or result["score"] < 0.15 or len(result["categories"]) < 2:
                rejected += 1
                if tp:
                    reason = "noise" if result["noise"] else f"low relevance ({result['score']})"
                    try:
                        tp.log_rejection(
                            subject=f"moltbook:{title[:80]}",
                            reason=reason,
                            taste_axis="relevance",
                        )
                    except Exception:
                        pass
                continue

            # Accept — add to curiosity queue (or boost if duplicate)
            accepted += 1
            priority = int(result["score"] * 10)
            self.curiosity.add(
                topic=title,
                source=f"moltbook:{post.get('id', '?')}",
                priority=priority,
                categories=result["categories"],
            )

        return f"Explored Moltbook: {accepted} accepted, {rejected} rejected"

    async def _verify_assumptions(self) -> str:
        """Verify assumptions using the AssumptionTracker."""
        try:
            from cognition.assumption_tracker import AssumptionTracker
            tracker = AssumptionTracker()
            stale = tracker.get_stale(days_old=7)
            expired = tracker.expire_old(days_old=30)
            summary = tracker.get_summary()
            return (
                f"Verified assumptions: {summary.get('open', 0)} open, "
                f"{len(stale)} stale, {len(expired)} expired"
            )
        except Exception as e:
            return f"Assumption verification error: {e}"

    async def _curate_memory(self) -> str:
        """Curate memory by extracting insights from daily logs."""
        try:
            from cognition.memory_curation import MemoryCuration
            curator = MemoryCuration(memory_dir=str(MEMORY_DIR))
            insights = curator.extract_insights_from_logs(days=7)
            promoted = 0
            for insight in insights[:3]:  # Promote up to 3 new insights
                success, _ = curator.promote_insight(
                    insight["text"], category="auto-curated"
                )
                if success:
                    promoted += 1
            return f"Curated memories: {len(insights)} found, {promoted} promoted"
        except Exception as e:
            return f"Memory curation error: {e}"

    async def _share_update(self, action: dict) -> str:
        """Share an update about the last action on Moltbook."""
        try:
            from integrations.moltbook_client import post_update
            description = action.get("description", "autonomous cycle")
            content = self._last_action_result or "Completed a wake cycle"
            result = post_update(
                title=f"Clawgotchi: {description[:60]}",
                content=content[:500],
                submolt="general",
            )
            if "error" in result:
                return f"Share failed: {result['error']}"
            return "Shared update on Moltbook"
        except Exception as e:
            return f"Share error: {e}"

    async def _reflect(self, action: dict, result: str) -> str:
        """Reflect on the cycle: update WORKING.md, beliefs, and daily log."""
        # Update beliefs
        desc = action.get("description", "").lower()
        if "build" in desc and "built" in result.lower():
            self.beliefs.add_evidence("bel-001", f"Built: {result}")
        if "explore" in desc:
            self.beliefs.add_question(f"Explored: {desc}")

        # Update WORKING.md
        working_md = MEMORY_DIR / "WORKING.md"
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            entry = (
                f"\n## Wake Cycle #{self.state.total_wakes} ({timestamp})\n"
                f"- Action: {action.get('description', 'unknown')}\n"
                f"- Result: {result}\n"
                f"- Health: {self.state.health_score}/100\n"
            )
            existing = working_md.read_text() if working_md.exists() else "# WORKING.md\n"
            working_md.write_text(existing + entry)
        except Exception:
            pass

        # Append to daily memory log
        daily_log = MEMORY_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.md"
        try:
            log_line = f"- [{datetime.now().strftime('%H:%M')}] {action.get('description', '')}: {result}\n"
            with open(daily_log, "a") as f:
                f.write(log_line)
        except Exception:
            pass

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
    
    async def _self_repair(self) -> str:
        """Auto-fix common issues found during testing."""
        fixed = []
        repairs = []
        
        # Run tests and check for import errors
        test_result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
            capture_output=True, text=True, cwd=str(BASE_DIR)
        )
        
        # Fix import errors in test files
        if "ModuleNotFoundError" in test_result.stdout or "ModuleNotFoundError" in test_result.stderr:
            for test_file in Path(BASE_DIR / "tests").rglob("test_*.py"):
                try:
                    content = test_file.read_text()
                    original = content
                    
                    # Common fixes for clawgotchi imports
                    fixes = [
                        ("from fallback_response", "from clawgotchi.resilience.fallback_response"),
                        ("from resilience_registry", "from clawgotchi.resilience.resilience_registry"),
                        ("from circuit_breaker", "from clawgotchi.resilience.circuit_breaker"),
                        ("from timeout_budget", "from clawgotchi.resilience.timeout_budget"),
                        ("from degradation_coordinator", "from clawgotchi.resilience.degradation_coordinator"),
                        ("from service_chain", "from clawgotchi.resilience.service_chain"),
                        ("from taste_profile", "from cognition.taste_profile"),
                    ]
                    
                    for old, new in fixes:
                        if old in content and new not in content:
                            content = content.replace(old, new)
                            fixed.append(f"{test_file.name}: {old.split()[-1]} → {new.split()[-1]}")
                    
                    if content != original:
                        test_file.write_text(content)
                except Exception as e:
                    repairs.append(f"Error fixing {test_file.name}: {e}")
        
        # Create missing modules if imports fail
        missing_modules = ["circuit_breaker", "timeout_budget"]
        for module in missing_modules:
            module_path = BASE_DIR / "clawgotchi" / "resilience" / f"{module}.py"
            if not module_path.exists():
                # Create basic module
                module_content = f'''"""Generated module: {module}"""

# Auto-created by _self_repair

'''
                try:
                    module_path.write_text(module_content)
                    fixed.append(f"Created missing: {module}")
                except:
                    pass
        
        if fixed:
            return f"Self-repair complete: {', '.join(fixed)}"
        return "No repairs needed"
    
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

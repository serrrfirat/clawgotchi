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

The TUI (clawgotchi.py) displays the agent's state, thoughts, and health.
"""

import asyncio
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

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
                asyncio.run(self.wake_cycle())
            except Exception as e:
                error_msg = f"Cycle error: {e}"
                print(error_msg)
                self.state.add_error(error_msg)
                self.state.save()
            
            # Sleep until next wake
            for _ in range(WAKE_INTERVAL):
                if not self.running or not self.paused:
                    break
                time.sleep(1)
    
    async def wake_cycle(self):
        """Execute one wake cycle."""
        # WAKING
        self.state.current_state = STATE_WAKING
        self.state.last_wake = datetime.now().isoformat()
        self.state.save()
        
        # OBSERVING
        self.state.current_state = STATE_OBSERVING
        health_issues = self.resources.update()
        health_score = await self._check_health()
        
        # Reduce health if issues found
        if health_issues:
            health_score = max(0, health_score - len(health_issues) * 10)
        
        self.state.update_health(health_score)
        self.state.current_thought = "Observing my surroundings..."
        self.state.save()
        await asyncio.sleep(2)
        
        # DECIDING
        self.state.current_state = STATE_DECIDING
        action = await self._decide_next_action()
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
        self.state.total_wakes += 1
        self.state.save()
        
        # SLEEPING
        self.state.current_state = STATE_SLEEPING
        self.state.save()
    
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
    
    async def _build_feature(self, action: dict) -> str:
        """Build a feature based on Moltbook inspiration."""
        # For now, just log the intention
        return f"Would build: {action.get('description', 'something new')}"
    
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

"""
Script Watchdog — monitors critical scripts and alerts on failure.
"""

import hashlib
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


class WatchdogError(Exception):
    """Base exception for Watchdog errors."""
    pass


class ScriptNotFoundError(WatchdogError):
    """Raised when monitored script doesn't exist."""
    pass


class ScriptFailedError(WatchdogError):
    """Raised when script execution fails."""
    pass


class Watchdog:
    """Monitors scripts and executes them with change detection."""
    
    def __init__(self, config_path: str = "~/.watchdog.json"):
        self.config_path = Path(config_path).expanduser()
        self.scripts: dict[str, dict] = {}
        self.last_runs: dict[str, str] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                    self.scripts = data.get("scripts", {})
            except (json.JSONDecodeError, IOError):
                self.scripts = {}
    
    def _save_config(self) -> None:
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump({"scripts": self.scripts}, f, indent=2)
    
    def _compute_hash(self, script_path: str) -> str:
        """Compute MD5 hash of a script file."""
        path = Path(script_path)
        if not path.exists():
            raise ScriptNotFoundError(f"Script not found: {script_path}")
        
        return hashlib.md5(path.read_bytes()).hexdigest()
    
    def _get_mtime(self, script_path: str) -> float:
        """Get modification time of a script."""
        path = Path(script_path)
        if not path.exists():
            raise ScriptNotFoundError(f"Script not found: {script_path}")
        return path.stat().st_mtime
    
    def register(
        self,
        name: str,
        script_path: str,
        schedule: Optional[str] = None,
        on_change: Optional[Callable[[str], None]] = None,
        on_failure: Optional[Callable[[str, Exception], None]] = None,
    ) -> None:
        """Register a script to monitor."""
        path = Path(script_path)
        if not path.exists():
            raise ScriptNotFoundError(f"Script not found: {script_path}")
        
        self.scripts[name] = {
            "path": str(path.absolute()),
            "schedule": schedule,
            "on_change": on_change.__name__ if on_change else None,
            "on_failure": on_failure.__name__ if on_failure else None,
            "last_hash": self._compute_hash(str(path)),
            "last_mtime": self._get_mtime(str(path)),
        }
        self._save_config()
    
    def unregister(self, name: str) -> None:
        """Unregister a monitored script."""
        if name in self.scripts:
            del self.scripts[name]
            self._save_config()
    
    def check_for_changes(self, name: str) -> bool:
        """Check if a script has changed since last check."""
        if name not in self.scripts:
            raise WatchdogError(f"Script not registered: {name}")
        
        script_info = self.scripts[name]
        current_hash = self._compute_hash(script_info["path"])
        current_mtime = self._get_mtime(script_info["path"])
        
        changed = (
            current_hash != script_info["last_hash"] or
            current_mtime != script_info["last_mtime"]
        )
        
        if changed:
            script_info["last_hash"] = current_hash
            script_info["last_mtime"] = current_mtime
            self._save_config()
        
        return changed
    
    def run(self, name: str, timeout: int = 300) -> tuple[int, str]:
        """Run a registered script and return exit code and output."""
        if name not in self.scripts:
            raise WatchdogError(f"Script not registered: {name}")
        
        script_info = self.scripts[name]
        path = script_info["path"]
        
        try:
            result = subprocess.run(
                ["/bin/bash", path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            self.last_runs[name] = datetime.now().isoformat()
            return result.returncode, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            raise ScriptFailedError(f"Script {name} timed out after {timeout}s")
        except Exception as e:
            raise ScriptFailedError(f"Script {name} failed: {e}")
    
    def run_if_changed(self, name: str, timeout: int = 300) -> tuple[bool, int, str]:
        """Run script only if it has changed. Returns (ran, exit_code, output)."""
        if self.check_for_changes(name):
            exit_code, output = self.run(name, timeout)
            return True, exit_code, output
        return False, 0, ""
    
    def list_registered(self) -> list[str]:
        """List all registered script names."""
        return list(self.scripts.keys())
    
    def status(self, name: str) -> dict:
        """Get status of a registered script."""
        if name not in self.scripts:
            raise WatchdogError(f"Script not registered: {name}")
        
        script_info = self.scripts[name]
        path = script_info["path"]
        
        return {
            "name": name,
            "path": path,
            "exists": Path(path).exists(),
            "last_changed": script_info["last_mtime"],
            "last_run": self.last_runs.get(name),
            "hash": script_info["last_hash"],
        }


def run_watchdog_loop(interval: int = 60):
    """Run the watchdog monitoring loop."""
    watchdog = Watchdog()
    
    while True:
        for name in watchdog.list_registered():
            try:
                changed, _, _ = watchdog.run_if_changed(name)
                if changed:
                    print(f"[Watchdog] {name} changed and was re-executed")
            except Exception as e:
                print(f"[Watchdog] Error with {name}: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Script Watchdog")
    parser.add_argument("--config", default="~/.watchdog.json", help="Config path")
    parser.add_argument("--register", nargs=3, metavar=("NAME", "PATH", "SCHEDULE"),
                       help="Register a script")
    parser.add_argument("--status", metavar="NAME", help="Show status of a script")
    parser.add_argument("--run", metavar="NAME", help="Run a script")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--interval", type=int, default=60, help="Daemon check interval")
    
    args = parser.parse_args()
    
    watchdog = Watchdog(args.config)
    
    if args.register:
        name, path, schedule = args.register
        watchdog.register(name, path, schedule)
        print(f"Registered: {name}")
    elif args.list:
        for name in watchdog.list_registered():
            print(f"  {name}")
    elif args.status:
        status = watchdog.status(args.status)
        print(json.dumps(status, indent=2))
    elif args.run:
        code, output = watchdog.run(args.run)
        print(output)
        exit(code)
    elif args.daemon:
        run_watchdog_loop(args.interval)
    else:
        parser.print_help()

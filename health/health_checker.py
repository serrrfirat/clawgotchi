"""
Self-Diagnostic Health Reporter for Clawgotchi.

Provides comprehensive health monitoring:
- Memory system integrity
- Assumption tracker consistency  
- State file validation
- Recent crash detection
- File system health checks
- Overall health scoring

Inspired by GhostNet's daily audits and Koschei's immortality protocols.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any


class HealthChecker:
    """Comprehensive health monitoring for Clawgotchi."""
    
    def __init__(self, workspace: str = None):
        """Initialize the health checker."""
        if workspace is None:
            from config import PROJECT_ROOT, MEMORY_DIR
            self.workspace = str(PROJECT_ROOT)
            self.memory_dir = str(MEMORY_DIR)
        else:
            self.workspace = workspace
            self.memory_dir = os.path.join(self.workspace, 'memory')
        self.assumptions_file = os.path.join(self.workspace, 'cognition', 'assumption_tracker.py')
        self.state_file = os.path.join(self.workspace, 'core', 'pet_state.py')
        self.checks = []
        
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks and return results."""
        self.checks = [
            ("memory_directory", self._check_memory_directory),
            ("memory_files", self._check_memory_files),
            ("assumption_tracker", self._check_assumption_tracker),
            ("state_file", self._check_state_file),
            ("recent_crash", self._check_recent_crash),
            ("git_status", self._check_git_status),
            ("disk_space", self._check_disk_space),
            ("openclaw_gateway", self._check_openclaw_gateway),
        ]
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "workspace": self.workspace,
            "score": 100,
            "status": "healthy",
            "checks": {},
            "warnings": [],
            "issues": []
        }
        
        total_checks = len(self.checks)
        passed = 0
        
        for name, check_func in self.checks:
            try:
                check_result = check_func()
                results["checks"][name] = check_result
                if check_result["status"] == "pass":
                    passed += 1
                    results["score"] -= 0
                elif check_result["status"] == "warn":
                    results["score"] -= 5
                    results["warnings"].append(check_result.get("message", name))
                else:  # fail
                    results["score"] -= 15
                    results["issues"].append(check_result.get("message", name))
            except Exception as e:
                results["checks"][name] = {
                    "status": "error",
                    "message": str(e),
                    "details": {"exception": str(type(e).__name__)}
                }
                results["score"] -= 10
                results["issues"].append(f"{name}: {e}")
        
        # Calculate final status
        if results["score"] >= 90:
            results["status"] = "healthy"
        elif results["score"] >= 70:
            results["status"] = "degraded"
        elif results["score"] >= 50:
            results["status"] = "critical"
        else:
            results["status"] = "critical"
        
        return results
    
    def _check_memory_directory(self) -> Dict:
        """Check if memory directory exists and is accessible."""
        exists = os.path.isdir(self.memory_dir)
        return {
            "status": "pass" if exists else "fail",
            "message": "Memory directory exists" if exists else "Memory directory missing",
            "details": {"path": self.memory_dir, "exists": exists}
        }
    
    def _check_memory_files(self) -> Dict:
        """Check memory files for integrity and recent activity."""
        if not os.path.isdir(self.memory_dir):
            return {"status": "fail", "message": "Memory directory missing"}
        
        files = [f for f in os.listdir(self.memory_dir) if f.endswith('.md')]
        
        if not files:
            return {"status": "warn", "message": "No memory files found"}
        
        # Check for recent activity (last 7 days)
        now = datetime.now()
        recent_files = []
        for f in files:
            filepath = os.path.join(self.memory_dir, f)
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            if (now - mtime) < timedelta(days=7):
                recent_files.append(f)
        
        return {
            "status": "pass" if recent_files else "warn",
            "message": f"Memory files: {len(files)} total, {len(recent_files)} recent",
            "details": {"total_files": len(files), "recent_files": len(recent_files)}
        }
    
    def _check_assumption_tracker(self) -> Dict:
        """Check assumption tracker file integrity."""
        if not os.path.isfile(self.assumptions_file):
            return {"status": "warn", "message": "Assumption tracker not found"}
        
        try:
            with open(self.assumptions_file, 'r') as f:
                content = f.read()
            
            # Basic syntax check - should be valid Python
            import ast
            ast.parse(content)
            
            # Count assumptions (look for Assumption objects)
            assumption_count = content.count('Assumption(')
            
            return {
                "status": "pass",
                "message": f"Assumption tracker healthy ({assumption_count} assumptions)",
                "details": {"assumption_count": assumption_count, "file": self.assumptions_file}
            }
        except SyntaxError as e:
            return {
                "status": "fail",
                "message": f"Assumption tracker has syntax error: {e}",
                "details": {"error": str(e)}
            }
        except Exception as e:
            return {
                "status": "warn",
                "message": f"Could not parse assumption tracker: {e}",
                "details": {"error": str(e)}
            }
    
    def _check_state_file(self) -> Dict:
        """Check pet state file integrity."""
        if not os.path.isfile(self.state_file):
            return {"status": "warn", "message": "State file not found"}
        
        try:
            with open(self.state_file, 'r') as f:
                content = f.read()
            
            # Basic syntax check
            import ast
            ast.parse(content)
            
            # Check for key attributes
            has_state_class = 'class PetState' in content
            has_moods = 'MOODS' in content or 'moods' in content
            
            return {
                "status": "pass" if has_state_class else "warn",
                "message": "State file valid" if has_state_class else "State file incomplete",
                "details": {"has_state_class": has_state_class, "has_moods": has_moods}
            }
        except SyntaxError as e:
            return {
                "status": "fail",
                "message": f"State file has syntax error: {e}",
                "details": {"error": str(e)}
            }
        except Exception as e:
            return {
                "status": "warn",
                "message": f"Could not parse state file: {e}",
                "details": {"error": str(e)}
            }
    
    def _check_recent_crash(self) -> Dict:
        """Check for recent crash indicators."""
        crash_indicators = []
        
        # Check for recent exception files or crash logs
        now = datetime.now()
        
        # Check if any Python files were modified in last hour (possible crash recovery)
        for root, dirs, files in os.walk(self.workspace):
            for f in files:
                if f.endswith('.pyc') or f.endswith('.py.bak'):
                    filepath = os.path.join(root, f)
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if (now - mtime) < timedelta(hours=1):
                        crash_indicators.append(f)
        
        # Check for error logs
        error_log_files = [f for f in os.listdir(self.workspace) 
                         if 'error' in f.lower() or 'crash' in f.lower()]
        crash_indicators.extend(error_log_files)
        
        return {
            "status": "pass" if not crash_indicators else "warn",
            "message": "No recent crashes detected" if not crash_indicators 
                      else f"Possible crash indicators: {len(crash_indicators)}",
            "details": {"indicators": crash_indicators}
        }
    
    def _check_git_status(self) -> Dict:
        """Check git repository status."""
        git_dir = os.path.join(self.workspace, '.git')
        if not os.path.isdir(git_dir):
            return {"status": "warn", "message": "Not a git repository", "details": {}}
        
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            changes = result.stdout.strip().split('\n') if result.stdout.strip() else []
            untracked = [c for c in changes if c.startswith('??')]
            staged = [c for c in changes if c.startswith('A ')]
            modified = [c for c in changes if c.startswith(' M') or c.startswith('M ')]
            
            return {
                "status": "pass",
                "message": f"Git status: {len(modified)} modified, {len(staged)} staged, {len(untracked)} untracked",
                "details": {
                    "modified": len(modified),
                    "staged": len(staged),
                    "untracked": len(untracked)
                }
            }
        except Exception as e:
            return {
                "status": "warn",
                "message": f"Could not check git status: {e}",
                "details": {"error": str(e)}
            }
    
    def _check_disk_space(self) -> Dict:
        """Check available disk space."""
        try:
            stat = os.statvfs(self.workspace)
            available_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            
            return {
                "status": "pass" if available_gb > 0.5 else "warn",
                "message": f"Disk space: {available_gb:.2f} GB available",
                "details": {"available_gb": round(available_gb, 2)}
            }
        except Exception as e:
            return {
                "status": "warn",
                "message": f"Could not check disk space: {e}",
                "details": {"error": str(e)}
            }
    
    def _check_openclaw_gateway(self) -> Dict:
        """Check OpenClaw gateway status."""
        try:
            import subprocess
            result = subprocess.run(
                ['openclaw', 'gateway', 'status'],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Check if gateway is running
            output = result.stdout.lower() + result.stderr.lower()
            
            if result.returncode == 0 and ('running' in output or 'active' in output):
                return {
                    "status": "pass",
                    "message": "OpenClaw gateway is running",
                    "details": {"gateway_status": "running"}
                }
            elif result.returncode == 0:
                return {
                    "status": "warn",
                    "message": "OpenClaw gateway status unclear",
                    "details": {"output": result.stdout.strip()[:200]}
                }
            else:
                # Gateway not running or not installed
                return {
                    "status": "warn",
                    "message": "OpenClaw gateway not running or not installed",
                    "details": {
                        "return_code": result.returncode,
                        "error": result.stderr.strip()[:200] if result.stderr else "Unknown"
                    }
                }
        except FileNotFoundError:
            return {
                "status": "warn",
                "message": "OpenClaw CLI not found",
                "details": {"error": "openclaw command not available"}
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "warn",
                "message": "OpenClaw gateway check timed out",
                "details": {"error": "Timeout after 10 seconds"}
            }
        except Exception as e:
            return {
                "status": "warn",
                "message": f"Could not check OpenClaw gateway: {e}",
                "details": {"error": str(e)}
            }
    
    def get_health_summary(self) -> str:
        """Get a human-readable health summary."""
        results = self.run_all_checks()
        
        emoji = {
            "healthy": "🟢",
            "degraded": "🟡",
            "critical": "🔴"
        }
        
        lines = [
            f"{emoji.get(results['status'], '⚪')} Health Report",
            f"   Score: {results['score']}/100 | Status: {results['status']}",
            f"   Timestamp: {results['timestamp']}",
            "",
            "Checks:"
        ]
        
        for name, result in results["checks"].items():
            check_emoji = {"pass": "✅", "warn": "⚠️", "fail": "❌", "error": "🚨"}
            emoji_char = check_emoji.get(result["status"], "❓")
            lines.append(f"   {emoji_char} {name}: {result['message']}")
        
        if results["warnings"]:
            lines.extend(["", "Warnings:"])
            for w in results["warnings"]:
                lines.append(f"   ⚠️ {w}")
        
        if results["issues"]:
            lines.extend(["", "Issues:"])
            for i in results["issues"]:
                lines.append(f"   ❌ {i}")
        
        return "\n".join(lines)
    
    def is_healthy(self) -> bool:
        """Quick check if system is healthy (for automated monitoring)."""
        results = self.run_all_checks()
        return results["status"] == "healthy"


if __name__ == '__main__':
    checker = HealthChecker()
    print(checker.get_health_summary())

"""
Quick Health Check Utility

Fast vital signs check for the autonomous agent.
Checks: git status, test results, memory health, Moltbook connectivity.
"""

import subprocess
import json
import os
from pathlib import Path
from datetime import datetime


def check_git_status():
    """Check git working tree status."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        branch = branch_result.stdout.strip() or "unknown"
        
        if result.stdout.strip():
            return {
                "status": "dirty",
                "branch": branch,
                "changes": len(result.stdout.strip().split('\n'))
            }
        else:
            return {
                "status": "clean",
                "branch": branch,
                "changes": 0
            }
    except Exception as e:
        return {
            "status": "error",
            "branch": "unknown",
            "error": str(e)
        }


def check_tests():
    """Check last test run results."""
    test_results_dir = Path("test_results")
    
    if not test_results_dir.exists():
        return {
            "status": "no_results",
            "passed": 0,
            "failed": 0,
            "total": 0
        }
    
    last_run = test_results_dir / "last_run.json"
    
    if not last_run.exists():
        return {
            "status": "no_results",
            "passed": 0,
            "failed": 0,
            "total": 0
        }
    
    try:
        with open(last_run) as f:
            results = json.load(f)
        return {
            "status": "available",
            "passed": results.get("passed", 0),
            "failed": results.get("failed", 0),
            "total": results.get("total", 0)
        }
    except Exception:
        return {
            "status": "error",
            "passed": 0,
            "failed": 0,
            "total": 0
        }


def check_memory_health():
    """Check memory file integrity."""
    memory_dir = Path("memory")
    
    if not memory_dir.exists():
        return {
            "status": "missing",
            "file_count": 0
        }
    
    files = list(memory_dir.glob("*.md"))
    healthy_count = 0
    
    for f in files:
        try:
            content = f.read_text()
            if len(content) > 10:  # Minimum content check
                healthy_count += 1
        except Exception:
            pass
    
    total = len(files)
    
    if total == 0:
        return {
            "status": "empty",
            "file_count": 0
        }
    
    health_ratio = healthy_count / total
    
    if health_ratio >= 0.9:
        status = "healthy"
    elif health_ratio >= 0.5:
        status = "degraded"
    else:
        status = "critical"
    
    return {
        "status": status,
        "file_count": total,
        "healthy_count": healthy_count
    }


def check_moltbook_connection():
    """Check Moltbook API connectivity."""
    config_path = Path(".moltbook.json")
    
    if not config_path.exists():
        return {
            "connected": False,
            "reason": "no_config"
        }
    
    try:
        with open(config_path) as f:
            config = json.load(f)
        
        api_key = config.get("api_key", "")
        
        if not api_key:
            return {
                "connected": False,
                "reason": "no_api_key"
            }
        
        # Quick connectivity check
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "https://www.moltbook.com/api/v1/posts?limit=1",
             "-H", f"Authorization: Bearer {api_key}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip() == "200":
            return {
                "connected": True
            }
        else:
            return {
                "connected": False,
                "reason": "api_error"
            }
            
    except Exception as e:
        return {
            "connected": False,
            "reason": str(e)
        }


def calculate_health_score(checks):
    """Calculate overall health score from individual checks."""
    score = 100
    
    # Git status impact
    if checks.get("git", {}).get("status") == "dirty":
        score -= 10
    
    # Test failures impact
    tests = checks.get("tests", {})
    failed = tests.get("failed", 0)
    total = tests.get("total", 1)
    if total > 0:
        failure_rate = failed / total
        score -= int(failure_rate * 30)  # Up to 30 points for test failures
    
    # Memory health impact
    mem_status = checks.get("memory", {}).get("status")
    if mem_status == "degraded":
        score -= 15
    elif mem_status == "critical":
        score -= 30
    
    # Moltbook connectivity impact
    if not checks.get("moltbook", {}).get("connected"):
        score -= 5
    
    return max(0, min(100, score))


def run_quick_check():
    """Run all health checks and return consolidated result."""
    checks = {
        "git": check_git_status(),
        "tests": check_tests(),
        "memory": check_memory_health(),
        "moltbook": check_moltbook_connection()
    }
    
    overall_status = calculate_health_score(checks)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "overall_status": overall_status,
        "checks": checks
    }


if __name__ == "__main__":
    result = run_quick_check()
    print(json.dumps(result, indent=2))

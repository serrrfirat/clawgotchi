"""
FeedResilienceChecker - Monitors Moltbook API availability and health.

This utility proactively checks the Moltbook feed endpoint to ensure
our autonomous heartbeat can detect feed failures early.
"""

import urllib.request
import urllib.error
import json
import os
from datetime import datetime
from typing import Dict, Optional, Tuple, Any
import time


class FeedResilienceChecker:
    """Checks Moltbook API health and logs metrics."""

    def __init__(self, api_key_path: str = "~/.moltbook.json", timeout: int = 10):
        """
        Initialize the FeedResilienceChecker.

        Args:
            api_key_path: Path to the Moltbook API key file (default: ~/.moltbook.json)
            timeout: Request timeout in seconds (default: 10)
        """
        self.api_key_path = os.path.expanduser(api_key_path)
        self.timeout = timeout
        self.feed_url = "https://www.moltbook.com/api/v1/posts?sort=new&limit=5"
        self.state_file = "/workspace/.feed_resilience_state.json"
        self.wobble_threshold = 3  # Failures before declaring "feed wobble"
        self.latency_warning_ms = 1000  # Warn if latency exceeds 1 second

    def _load_api_key(self) -> Optional[str]:
        """Load API key from config file."""
        try:
            with open(self.api_key_path, 'r') as f:
                data = json.load(f)
                return data.get('api_key')
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return None

    def _load_state(self) -> Dict[str, Any]:
        """Load persistent state for failure tracking."""
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"consecutive_failures": 0, "last_check": None, "status": "unknown"}

    def _save_state(self, state: Dict[str, Any]):
        """Save persistent state."""
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def ping(self) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        Ping the Moltbook feed endpoint.

        Returns:
            Tuple of (success, error_message, latency_ms)
        """
        api_key = self._load_api_key()
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        start_time = time.time()
        try:
            req = urllib.request.Request(self.feed_url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = response.read()
                latency_ms = (time.time() - start_time) * 1000
                # Verify we got a response
                if response.status == 200:
                    return True, None, latency_ms
                else:
                    return False, f"HTTP {response.status}", latency_ms

        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}", None
        except urllib.error.URLError as e:
            return False, f"URL Error: {e.reason}", None
        except Exception as e:
            return False, f"Error: {str(e)}", None

    def verify_response_structure(self, response_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Verify the Moltbook response has expected fields.

        Args:
            response_data: Parsed JSON response

        Returns:
            Tuple of (is_valid, error_message)
        """
        required_fields = ["success", "posts"]
        
        for field in required_fields:
            if field not in response_data:
                return False, f"Missing field: {field}"
        
        if not isinstance(response_data["posts"], list):
            return False, "Posts is not a list"
        
        return True, None

    def check(self) -> Dict[str, Any]:
        """
        Perform a full health check.

        Returns:
            Dict with check results including success, metrics, and status
        """
        state = self._load_state()
        success, error, latency = self.ping()

        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "success": success,
            "error": error,
            "latency_ms": latency,
            "status": "healthy"
        }

        if success:
            state["consecutive_failures"] = 0
            state["last_check"] = result["timestamp"]
            state["status"] = "healthy"
            
            if latency and latency > self.latency_warning_ms:
                result["status"] = "degraded"
                result["warning"] = f"Latency {latency:.0f}ms exceeds threshold {self.latency_warning_ms}ms"
        else:
            state["consecutive_failures"] += 1
            state["last_check"] = result["timestamp"]
            
            if state["consecutive_failures"] >= self.wobble_threshold:
                state["status"] = "wobble"
                result["status"] = "feed_wobble"
                result["wobble_detected"] = True
                result["consecutive_failures"] = state["consecutive_failures"]
            else:
                result["status"] = "unhealthy"

        self._save_state(state)
        return result

    def log_metrics(self, result: Dict[str, Any]):
        """Log check results (stdout for now, could be extended)."""
        status = result.get("status", "unknown")
        latency = result.get("latency_ms")
        
        if latency:
            print(f"[FeedResilience] Status: {status} | Latency: {latency:.0f}ms | {result.get('timestamp', '')}")
        else:
            print(f"[FeedResilience] Status: {status} | Error: {result.get('error', 'Unknown')} | {result.get('timestamp', '')}")
        
        if result.get("wobble_detected"):
            print(f"[FeedResilience] 🚨 FEED WOBBLE DETECTED! {result.get('consecutive_failures')} consecutive failures")


# Convenience function for CLI usage
def main():
    checker = FeedResilienceChecker()
    result = checker.check()
    checker.log_metrics(result)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    exit(main())

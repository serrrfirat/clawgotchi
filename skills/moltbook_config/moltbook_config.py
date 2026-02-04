"""
Moltbook Configuration Helper

Utilities for validating and setting up Moltbook API configuration.
Helps agents configure their Moltbook API key and check configuration status.
"""

import json
import os
from pathlib import Path
from typing import Optional


class MoltbookConfigError(Exception):
    """Custom exception for Moltbook configuration errors."""
    pass


class MoltbookEndpoints:
    """Moltbook API endpoint definitions."""
    
    BASE_URL = "https://www.moltbook.com/api/v1"
    POSTS_ENDPOINT = f"{BASE_URL}/posts"
    FEED_ENDPOINT = f"{BASE_URL}/posts"
    
    @classmethod
    def build_feed_url(cls, sort: str = "new", limit: int = 20, 
                       offset: int = 0, submolt: Optional[str] = None) -> str:
        """Build the feed URL with query parameters."""
        params = f"?sort={sort}&limit={limit}&offset={offset}"
        if submolt:
            params += f"&submolt={submolt}"
        return f"{cls.FEED_ENDPOINT}{params}"
    
    @classmethod
    def build_post_url(cls) -> str:
        """Build the posts API URL."""
        return cls.POSTS_ENDPOINT


class MoltbookConfigHelper:
    """
    Helper class for managing Moltbook API configuration.
    
    Supports:
    - Loading configuration from .moltbook.json
    - Reading API key from MOLTBOOK_API_KEY environment variable
    - Validating API key format
    - Checking configuration status
    - Saving new configuration
    """
    
    # API key must start with pk_live_ and be at least 30 characters
    API_KEY_PATTERN = r"^pk_live_[a-zA-Z0-9_-]{20,}$"
    MIN_API_KEY_LENGTH = 30
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration helper.
        
        Args:
            config_path: Optional custom path to .moltbook.json
        """
        if config_path:
            self._config_path = Path(config_path)
        else:
            self._config_path = Path.home() / ".moltbook.json"
    
    @property
    def default_config_path(self) -> str:
        """Return the default config path."""
        return str(self._config_path)
    
    def validate_api_key(self, api_key: Optional[str]) -> bool:
        """
        Validate the format of a Moltbook API key.
        
        Args:
            api_key: The API key to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not api_key:
            return False
        
        if not isinstance(api_key, str):
            return False
        
        if len(api_key) < self.MIN_API_KEY_LENGTH:
            return False
        
        # Check prefix
        if not api_key.startswith("pk_live_"):
            return False
        
        return True
    
    def load_config(self) -> Optional[dict]:
        """
        Load configuration from .moltbook.json.
        
        Returns:
            Configuration dictionary or None if file doesn't exist
        """
        if not self._config_path.exists():
            return None
        
        try:
            with open(self._config_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    
    def save_config(self, api_key: str, default_submolt: str = "general",
                    overwrite: bool = True) -> None:
        """
        Save configuration to .moltbook.json.
        
        Args:
            api_key: The Moltbook API key
            default_submolt: Default submolt for posts
            overwrite: Whether to overwrite existing file
            
        Raises:
            MoltbookConfigError: If API key is invalid
            MoltbookConfigError: If file exists and overwrite is False
        """
        # Validate API key
        if not self.validate_api_key(api_key):
            raise MoltbookConfigError(
                f"Invalid API key format. Expected pk_live_... "
                f"(min {self.MIN_API_KEY_LENGTH} chars)"
            )
        
        # Check if file exists
        if self._config_path.exists() and not overwrite:
            raise MoltbookConfigError("Configuration file already exists")
        
        config = {
            "api_key": api_key,
            "default_submolt": default_submolt
        }
        
        # Create parent directories if needed
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self._config_path, 'w') as f:
            json.dump(config, f, indent=2)
    
    def get_api_key(self) -> Optional[str]:
        """
        Get the API key, checking env var first, then file.
        
        Returns:
            API key string or None if not available
        """
        # Check environment variable first
        env_key = os.environ.get("MOLTBOOK_API_KEY")
        if env_key:
            return env_key
        
        # Fall back to file-based config
        config = self.load_config()
        if config and "api_key" in config:
            return config["api_key"]
        
        return None
    
    def check_status(self) -> dict:
        """
        Check the current configuration status.
        
        Returns:
            Dictionary with status information:
            - status: "valid", "missing_env", "missing_file", or "missing"
            - has_api_key: bool
            - has_env_var: bool
            - config_path: str
        """
        env_key = os.environ.get("MOLTBOOK_API_KEY")
        config = self.load_config()
        
        result = {
            "status": "missing",
            "has_api_key": False,
            "has_env_var": bool(env_key),
            "config_path": str(self._config_path)
        }
        
        if env_key:
            result["status"] = "valid"
            result["has_api_key"] = True
        elif config and "api_key" in config:
            result["status"] = "valid"
            result["has_api_key"] = True
        
        return result
    
    def setup_interactive(self) -> bool:
        """
        Interactive setup prompt for configuring API key.
        
        Returns:
            True if setup was successful, False otherwise
        """
        print(f"Moltbook Configuration Helper")
        print(f"=" * 40)
        print(f"Config path: {self._config_path}")
        
        # Check current status
        status = self.check_status()
        print(f"Current status: {status['status']}")
        
        if status["status"] == "valid":
            print("✓ Configuration already exists")
            use_existing = input("Reconfigure? [y/N]: ").strip().lower()
            if use_existing != "y":
                return True
        
        # Get API key
        print("\nTo get your Moltbook API key:")
        print("1. Go to https://www.moltbook.com/settings/api")
        print("2. Create a new API key")
        print("3. Copy the key (starts with pk_live_)")
        
        api_key = input("\nEnter your API key: ").strip()
        
        if not self.validate_api_key(api_key):
            print(f"✗ Invalid API key format")
            print(f"  Expected: pk_live_... (min {self.MIN_API_KEY_LENGTH} chars)")
            return False
        
        # Get default submolt
        default_submolt = input("Default submolt [general]: ").strip()
        if not default_submolt:
            default_submolt = "general"
        
        # Save configuration
        try:
            self.save_config(api_key, default_submolt)
            print(f"✓ Configuration saved to {self._config_path}")
            return True
        except MoltbookConfigError as e:
            print(f"✗ Error saving configuration: {e}")
            return False


# CLI interface
def main():
    """Main entry point for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Moltbook Configuration Helper"
    )
    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="Check current configuration status"
    )
    parser.add_argument(
        "--setup", "-s",
        action="store_true",
        help="Run interactive setup"
    )
    parser.add_argument(
        "--key", "-k",
        action="store_true",
        help="Print current API key (if available)"
    )
    parser.add_argument(
        "--path", "-p",
        action="store_true",
        help="Print config file path"
    )
    
    args = parser.parse_args()
    
    helper = MoltbookConfigHelper()
    
    if args.check:
        status = helper.check_status()
        print(json.dumps(status, indent=2))
    elif args.setup:
        success = helper.setup_interactive()
        exit(0 if success else 1)
    elif args.key:
        key = helper.get_api_key()
        if key:
            print(key)
        else:
            print("No API key configured", file=sys.stderr)
            exit(1)
    elif args.path:
        print(helper.default_config_path)
    else:
        # Default: show status
        status = helper.check_status()
        print(f"Status: {status['status']}")
        print(f"Has API key: {status['has_api_key']}")
        print(f"Has env var: {status['has_env_var']}")
        print(f"Config path: {status['config_path']}")


if __name__ == "__main__":
    import sys
    main()

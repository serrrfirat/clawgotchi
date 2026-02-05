"""
Moltbook API Key Configurator

Provides utilities for managing Moltbook API credentials.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


CONFIG_PATH = Path.home() / ".moltbook.json"


def save_api_key(api_key: str) -> dict:
    """
    Save API key to configuration file.
    
    Args:
        api_key: The Moltbook API key
        
    Returns:
        dict with status and message
    """
    config = {"api_key": api_key}
    
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    
    return {
        "status": "success",
        "message": f"API key saved to {CONFIG_PATH}",
        "path": str(CONFIG_PATH)
    }


def load_api_key() -> str | None:
    """
    Load API key from configuration file.
    
    Returns:
        API key string or None if not found/invalid
    """
    if not CONFIG_PATH.exists():
        return None
    
    try:
        with open(CONFIG_PATH, "r") as f:
            content = f.read()
            if not content.strip():
                return None
            config = json.loads(content)
    except (json.JSONDecodeError, IOError):
        return None
    
    return config.get("api_key")


def validate_config() -> dict:
    """
    Validate Moltbook configuration.
    
    Returns:
        dict with status, valid flag, and any errors
    """
    result = {
        "status": "success",
        "valid": False,
        "errors": [],
        "path": str(CONFIG_PATH)
    }
    
    if not CONFIG_PATH.exists():
        result["status"] = "error"
        result["errors"].append(f"Config file not found: {CONFIG_PATH}")
        return result
    
    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        result["status"] = "error"
        result["errors"].append(f"Invalid JSON: {e}")
        return result
    
    if "api_key" not in config:
        result["status"] = "error"
        result["errors"].append("Missing 'api_key' field")
        return result
    
    if not isinstance(config["api_key"], str) or not config["api_key"].strip():
        result["status"] = "error"
        result["errors"].append("'api_key' must be a non-empty string")
        return result
    
    result["valid"] = True
    return result


def remove_config() -> dict:
    """
    Remove Moltbook configuration file.
    
    Returns:
        dict with status and message
    """
    if not CONFIG_PATH.exists():
        return {
            "status": "success",
            "message": "No config file to remove"
        }
    
    os.remove(CONFIG_PATH)
    return {
        "status": "success",
        "message": f"Removed config file: {CONFIG_PATH}"
    }

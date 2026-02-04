"""
JSON Escape Utility for Moltbook Posts

Safely escape JSON strings for Moltbook API submissions.
Handles apostrophes, quotes, newlines, and special characters.
"""

import json
import re
from typing import Optional


class MoltbookJsonError(Exception):
    """Custom exception for JSON escaping errors."""
    pass


def escape_for_moltbook(content: str) -> str:
    """
    Escape a string for safe JSON encoding in Moltbook API.
    
    Args:
        content: The raw string content to escape
        
    Returns:
        JSON-escaped string safe for Moltbook API
        
    Raises:
        MoltbookJsonError: If content is None or cannot be escaped
    """
    if content is None:
        raise MoltbookJsonError("Content cannot be None")
    
    if not isinstance(content, str):
        raise MoltbookJsonError(f"Content must be string, got {type(content).__name__}")
    
    # Use Python's json encoder to properly escape
    encoded = json.dumps(content)
    # json.dumps adds surrounding quotes, remove them
    return encoded[1:-1]


def build_post_payload(
    submolt: str,
    title: str,
    content: str,
    url: Optional[str] = None
) -> dict:
    """
    Build a complete Moltbook post payload with proper JSON escaping.
    
    Args:
        submolt: The submolt name (e.g., "general")
        title: Post title
        content: Post content (can contain apostrophes, quotes, etc.)
        url: Optional URL to include
        
    Returns:
        Dictionary ready for Moltbook API POST request
        
    Raises:
        MoltbookJsonError: If validation fails
    """
    # Validate required fields
    if not submolt or not isinstance(submolt, str):
        raise MoltbookJsonError("submolt must be a non-empty string")
    if not title or not isinstance(title, str):
        raise MoltbookJsonError("title must be a non-empty string")
    if not content or not isinstance(content, str):
        raise MoltbookJsonError("content must be a non-empty string")
    
    # Build payload
    payload = {
        "submolt": submolt,
        "title": title,
        "content": content
    }
    
    if url:
        payload["url"] = url
    
    return payload


def escape_curl_content(content: str) -> str:
    """
    Prepare content for use in curl -d argument.
    Handles escaping for shell and JSON.
    
    Args:
        content: Raw content string
        
    Returns:
        Properly escaped string for curl
    """
    # First escape for JSON
    json_escaped = escape_for_moltbook(content)
    # Then escape for shell (single quotes)
    # Replace single quotes with escaped version for shell
    return json_escaped.replace("'", "'\"'\"'")


def validate_json_string(content: str) -> tuple[bool, Optional[str]]:
    """
    Validate if a string can be properly JSON-encoded.
    
    Args:
        content: String to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        json.dumps(content)
        return True, None
    except (TypeError, ValueError) as e:
        return False, str(e)


def batch_escape(strings: list[str]) -> list[str]:
    """
    Escape multiple strings at once.
    
    Args:
        list of strings to escape
        
    Returns:
        List of escaped strings
        
    Raises:
        MoltbookJsonError: If any string cannot be escaped
    """
    result = []
    for i, s in enumerate(strings):
        try:
            result.append(escape_for_moltbook(s))
        except MoltbookJsonError as e:
            raise MoltbookJsonError(f"Error escaping string at index {i}: {e}")
    return result


# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python json_escape.py <string>")
        print("   or: python json_escape.py --file <path>")
        sys.exit(1)
    
    if sys.argv[1] == "--file":
        if len(sys.argv) < 3:
            print("Error: --file requires a path argument")
            sys.exit(1)
        try:
            with open(sys.argv[2], 'r') as f:
                content = f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {sys.argv[2]}")
            sys.exit(1)
        except IOError as e:
            print(f"Error reading file: {e}")
            sys.exit(1)
    else:
        content = sys.argv[1]
    
    try:
        escaped = escape_for_moltbook(content)
        print(escaped)
    except MoltbookJsonError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

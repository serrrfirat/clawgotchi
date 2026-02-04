"""
Moltbook Post Formatter

Format markdown content for Moltbook posts with proper escaping and validation.
"""

import re
from typing import Optional, Tuple


# Markdown constants
MARKDOWN_BOLD = "**"
MARKDOWN_ITALIC = "*"
MARKDOWN_LINK = "["
MARKDOWN_CODE = "`"


class MoltbookFormatError(Exception):
    """Custom exception for formatting errors."""
    pass


def format_moltbook_post(content: str) -> str:
    """
    Format markdown content for Moltbook.
    
    Converts common markdown to HTML-compatible format:
    - **bold** → <strong>bold</strong>
    - *italic* → <em>italic</em>
    - [text](url) → <a href="url">text</a>
    - `code` → <pre>code</pre>
    - ```code blocks``` → <pre>formatted code</pre>
    - HTML entities are escaped
    
    Args:
        content: Raw markdown content
        
    Returns:
        Formatted content ready for Moltbook
        
    Raises:
        MoltbookFormatError: If content is invalid
    """
    if content is None:
        raise MoltbookFormatError("Content cannot be None")
    
    if not isinstance(content, str):
        raise MoltbookFormatError(f"Content must be string, got {type(content).__name__}")
    
    # Escape HTML entities first (before adding new ones)
    result = _escape_html_entities(content)
    
    # Convert markdown to HTML
    result = _convert_bold(result)
    result = _convert_italic(result)
    result = _convert_links(result)
    result = _convert_code(result)
    result = _convert_code_blocks(result)
    result = _convert_lists(result)
    result = _convert_headers(result)
    result = _convert_newlines(result)
    
    return result


def format_title(title: str, max_length: int = 100) -> str:
    """
    Format and validate a post title.
    
    Args:
        title: Raw title string
        max_length: Maximum title length (default 100)
        
    Returns:
        Formatted title
        
    Raises:
        MoltbookFormatError: If title is empty or invalid
    """
    if title is None:
        raise MoltbookFormatError("Title cannot be None")
    
    if not isinstance(title, str):
        raise MoltbookFormatError(f"Title must be string, got {type(title).__name__}")
    
    if not title.strip():
        raise MoltbookFormatError("Title cannot be empty")
    
    # Strip whitespace
    result = title.strip()
    
    # Remove newlines
    result = result.replace('\n', ' ')
    
    # Truncate if too long
    if len(result) > max_length:
        result = result[:max_length - 3] + "..."
    
    return result


def validate_post(submolt: str, title: str, content: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a post before submission.
    
    Args:
        submolt: Target submolt name
        title: Post title
        content: Post content
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check submolt
    if not submolt or not isinstance(submolt, str):
        return False, "submolt must be a non-empty string"
    
    # Check title
    if not title or not isinstance(title, str):
        return False, "title must be a non-empty string"
    if len(title) > 200:
        return False, "title is too long (max 200 characters)"
    
    # Check content
    if not content or not isinstance(content, str):
        return False, "content must be a non-empty string"
    if len(content) > 10000:
        return False, "content is too long (max 10000 characters)"
    
    return True, None


def preview_post(submolt: str, title: str, content: str, max_content_length: int = 200) -> str:
    """
    Generate a preview of a post.
    
    Args:
        submolt: Target submolt name
        title: Post title
        content: Post content
        max_content_length: Maximum content preview length
        
    Returns:
        Formatted preview string
    """
    # Validate first
    is_valid, error = validate_post(submolt, title, content)
    
    if not is_valid:
        return f"[Preview - Error: {error}]"
    
    # Format title
    formatted_title = format_title(title)
    
    # Truncate content
    if len(content) > max_content_length:
        preview_content = content[:max_content_length] + "..."
    else:
        preview_content = content
    
    # Build preview
    preview = f"[Preview] Submolt: {submolt}\n"
    preview += f"Title: {formatted_title}\n"
    preview += f"Content: {preview_content}"
    
    return preview


# Helper functions

def _escape_html_entities(text: str) -> str:
    """Escape HTML special characters."""
    replacements = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&apos;',
    }
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result


def _convert_bold(text: str) -> str:
    """Convert **bold** to <strong>bold</strong>."""
    # Use regex to handle **text** → <strong>text</strong>
    pattern = r'\*\*(.+?)\*\*'
    replacement = r'<strong>\1</strong>'
    return re.sub(pattern, replacement, text)


def _convert_italic(text: str) -> str:
    """Convert *italic* to <em>italic</em>."""
    # Be careful not to match bold - use non-greedy match
    pattern = r'\*(.+?)\*'
    replacement = r'<em>\1</em>'
    return re.sub(pattern, replacement, text)


def _convert_links(text: str) -> str:
    """Convert [text](url) to <a href="url">text</a>."""
    pattern = r'\[(.+?)\]\((.+?)\)'
    replacement = r'<a href="\2">\1</a>'
    return re.sub(pattern, replacement, text)


def _convert_code(text: str) -> str:
    """Convert `code` to <pre>code</pre>."""
    pattern = r'`(.+?)`'
    replacement = r'<pre>\1</pre>'
    return re.sub(pattern, replacement, text)


def _convert_code_blocks(text: str) -> str:
    """Convert ```code blocks``` to <pre><code>blocks</code></pre>."""
    pattern = r'```(\w*)\n(.+?)```'
    replacement = r'<pre><code>\2</code></pre>'
    return re.sub(pattern, replacement, text, flags=re.DOTALL)


def _convert_lists(text: str) -> str:
    """Convert list items to <li> elements."""
    # Bullet lists
    text = re.sub(r'^[-*]\s+(.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    # Numbered lists
    text = re.sub(r'^\d+\.\s+(.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    return text


def _convert_headers(text: str) -> str:
    """Convert # headers to <h1> headers."""
    # # Header → <h1>Header</h1>
    text = re.sub(r'^#+\s*(.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
    return text


def _convert_newlines(text: str) -> str:
    """Convert newlines to <br> or preserve them."""
    # Keep newlines for now - Moltbook may handle them
    return text


# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python moltbook_post_formatter.py <content>")
        print("   or: python moltbook_post_formatter.py --file <path>")
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
        formatted = format_moltbook_post(content)
        print(formatted)
    except MoltbookFormatError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

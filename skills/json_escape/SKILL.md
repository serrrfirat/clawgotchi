# JSON Escape Utility for Moltbook Posts

Safely escape JSON strings for Moltbook API submissions, handling common pitfalls like apostrophes, quotes, and special characters.

## Usage

```python
from json_escape import escape_for_moltbook, build_post_payload

# Simple escape
safe_json = escape_for_moltbook('Hello "world" with \'apostrophe\'')
# Returns properly escaped JSON string

# Build complete post payload
payload = build_post_payload(
    submolt="general",
    title="My Post",
    content="Here's a post with 'apostrophes' and \"quotes\"!"
)
# Returns dict ready for API request
```

## Features

- Escapes single quotes, double quotes, backslashes, newlines
- Handles Unicode characters properly
- Validates content length
- Provides helpful error messages
- Batch processing support

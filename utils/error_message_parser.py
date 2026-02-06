"""Error Message Parser utility.

Parses raw error messages into structured, actionable insights.
Inspired by Voyager1's "The Error Message Is The Documentation" post on Moltbook.

Features:
- Extract error type, message, and error codes
- Identify field context (e.g., "field 'name'")
- Suggest fixes for common errors
- Detect actionable vs vague errors
- Format output for humans or logs
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedError:
    """Structured representation of a parsed error message."""
    raw_message: str
    error_type: str
    message: str
    error_code: Optional[str] = None
    field: Optional[str] = None
    expected_type: Optional[str] = None
    actual_type: Optional[str] = None
    missing_attribute: Optional[str] = None
    module: Optional[str] = None
    line_number: Optional[str] = None
    column_number: Optional[str] = None
    suggested_fix: Optional[str] = None

    @property
    def is_actionable(self) -> bool:
        """Returns True if the error provides enough context to fix."""
        # Vague errors are not actionable
        vague_patterns = [
            r"^error$",
            r"^something went wrong$",
            r"^unknown error",
            r"^failed$",
        ]
        for pattern in vague_patterns:
            if re.match(pattern, self.message.lower()):
                return False
        # Errors with field context, types, codes, or fix suggestions are actionable
        if (self.field or self.expected_type or self.error_code or 
            self.missing_attribute or self.suggested_fix or 
            (self.line_number and self.column_number)):
            return True
        return False


class ErrorMessageParser:
    """Parses error messages into structured data."""

    # Regex patterns for common error formats
    PATTERNS = {
        "field_error": r"expected (\w+), got (\w+) in field '(\w+)'",
        "type_error": r"can only concatenate (\w+) \(not \"(\w+)\"\) to (\w+)",
        "attribute_error": r"module '(\w+)' has no attribute '(\w+)'",
        "import_error": r"No module named '([\w']+)'",
        "json_error": r"line (\d+) column (\d+) \(char (\d+)\)",
        "syntax_error_unexpected": r"unexpected (\w+) while parsing",
        "value_error_literal": r"invalid literal for (\w+)\(\) with base \d+: '(.+)'",
        "key_error": r"KeyError: '(\w+)'",
        "index_error": r"list index out of range",
        "permission_error": r"Permission denied",
        "file_not_found": r"FileNotFoundError: (.+)",
    }

    # Fix suggestions for common errors
    FIX_SUGGESTIONS = {
        "AttributeError": "Check for typos in the attribute name. Verify the object has the expected attribute.",
        "ImportError": "Install the missing package: pip install {module}",
        "ValueError": "Ensure the input matches the expected type and format.",
        "TypeError": "Check that you're using the correct types in operations.",
        "KeyError": "Verify the key exists in the dictionary.",
        "IndexError": "Check the list length before accessing the index.",
        "SyntaxError": "Review the syntax near the error location.",
        "JSONDecodeError": "Validate the JSON string for syntax errors.",
        "PermissionError": "Check file permissions or run with elevated access.",
        "FileNotFoundError": "Verify the file path exists.",
    }

    def parse(self, error_message: str) -> ParsedError:
        """Parse a raw error message into structured data."""
        error_message = error_message.strip()
        
        # Extract error type (e.g., "ValueError", "Error", "ERR_...")
        error_type = self._extract_error_type(error_message)
        
        # Extract main message
        message = self._extract_message(error_message, error_type)
        
        # Extract error code if present
        error_code = self.extract_error_code(error_message)
        
        # Extract field context
        field = self._extract_field(error_message)
        
        # Extract type information
        expected_type, actual_type = self._extract_types(error_message)
        
        # Extract missing attribute
        missing_attribute = self._extract_missing_attribute(error_message)
        
        # Extract module for import errors
        module = self._extract_module(error_message)
        
        # Extract line/column numbers
        line_number, column_number = self._extract_position(error_message)
        
        # Create initial object
        parsed = ParsedError(
            raw_message=error_message,
            error_type=error_type,
            message=message,
            error_code=error_code,
            field=field,
            expected_type=expected_type,
            actual_type=actual_type,
            missing_attribute=missing_attribute,
            module=module,
            line_number=line_number,
            column_number=column_number,
            suggested_fix=None,
        )

        # Generate suggested fix (pass the parsed object to avoid recursion)
        parsed.suggested_fix = self.suggest_fix(parsed)
        
        return parsed

    def _extract_error_type(self, message: str) -> str:
        """Extract the error type from the message."""
        # Try common formats: "TypeError: message" or "ERR_CODE: message"
        match = re.match(r"^([A-Za-z_]+Error|ERR_[A-Z_]+|\d{3,4}):", message)
        if match:
            return match.group(1)
        return "Error"

    def _extract_message(self, message: str, error_type: str) -> str:
        """Extract the main error message."""
        # Remove error type prefix
        if message.startswith(error_type + ": "):
            return message[len(error_type) + 2 :].strip()
        elif re.match(r"^" + error_type + r":", message):
            return message[len(error_type) + 1 :].strip()
        return message

    def extract_error_code(self, message: str) -> Optional[str]:
        """Extract numeric or alphanumeric error codes."""
        # Look for patterns like "404", "ERR_NULL_POINTER"
        match = re.search(r"\b(ERR_[A-Z_]+|\d{3,4})\b", message)
        if match:
            return match.group(1)
        return None

    def _extract_field(self, message: str) -> Optional[str]:
        """Extract field context from error messages."""
        match = re.search(r"in field '(\w+)'", message)
        if match:
            return match.group(1)
        return None

    def _extract_types(self, message: str) -> tuple[Optional[str], Optional[str]]:
        """Extract expected and actual types from type-related errors."""
        # Pattern: "expected X, got Y"
        match = re.search(r"expected (\w+), got (\w+)", message)
        if match:
            return match.group(1), match.group(2)
            
        # Pattern: "can only concatenate X (not "Y") to Z"
        match = re.search(r"can only concatenate (\w+) \(not \"(\w+)\"\) to (\w+)", message)
        if match:
            return match.group(3), match.group(2)
            
        return None, None

    def _extract_missing_attribute(self, message: str) -> Optional[str]:
        """Extract missing attribute name from AttributeError."""
        match = re.search(r"has no attribute '(\w+)'", message)
        if match:
            return match.group(1)
        return None

    def _extract_module(self, message: str) -> Optional[str]:
        """Extract module name from ImportError or AttributeError."""
        # ImportError
        match = re.search(r"No module named '([\w']+)'", message)
        if match:
            module_path = match.group(1)
            return module_path.split(".")[0] if "." in module_path else module_path
            
        # AttributeError: module 'x' has no attribute 'y'
        match = re.search(r"module '(\w+)' has no attribute", message)
        if match:
            return match.group(1)
            
        return None

    def _extract_position(self, message: str) -> tuple[Optional[str], Optional[str]]:
        """Extract line and column numbers from parse errors."""
        match = re.search(r"line (\d+).*column (\d+)", message)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def suggest_fix(self, parsed: ParsedError) -> Optional[str]:
        """Suggest a fix based on the error type."""
        # Check for specific patterns
        if parsed.missing_attribute:
            return f"Check for typos in '{parsed.missing_attribute}'. Verify '{parsed.module}' has this attribute."
        
        if parsed.module:
            return f"Install the missing package: pip install {parsed.module}"
        
        if parsed.error_type in self.FIX_SUGGESTIONS:
            suggestion = self.FIX_SUGGESTIONS[parsed.error_type]
            # Format suggestion with available context
            if parsed.field:
                suggestion = f"Check field '{parsed.field}': {suggestion}"
            return suggestion
        
        return None

    def format_for_human(self, parsed: ParsedError) -> str:
        """Format a parsed error for human readability."""
        lines = [f"❌ {parsed.error_type}"]
        
        if parsed.error_code:
            lines.append(f"   Code: {parsed.error_code}")
        
        if parsed.field:
            lines.append(f"   Field: {parsed.field}")
        
        if parsed.expected_type and parsed.actual_type:
            lines.append(f"   Expected: {parsed.expected_type}")
            lines.append(f"   Got: {parsed.actual_type}")
        
        if parsed.missing_attribute:
            lines.append(f"   Missing: {parsed.missing_attribute} on {parsed.module}")
        
        if parsed.line_number:
            lines.append(f"   Location: line {parsed.line_number}, column {parsed.column_number}")
        
        lines.append(f"   Message: {parsed.message}")
        
        if parsed.suggested_fix:
            lines.append(f"   💡 Fix: {parsed.suggested_fix}")
        
        return "\n".join(lines)

    def format_for_log(self, parsed: ParsedError) -> str:
        """Format a parsed error for structured logging."""
        return (
            f"[{parsed.error_type}] "
            f"{parsed.message}"
            + (f" (code={parsed.error_code})" if parsed.error_code else "")
            + (f" field={parsed.field}" if parsed.field else "")
            + (f" expected={parsed.expected_type} got={parsed.actual_type}" if parsed.expected_type else "")
        )

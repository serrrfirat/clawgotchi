"""
Error Pattern Registry

Documents common error patterns agents encounter and provides standardized
handling strategies. Complements circuit_breaker and fallback_response.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from datetime import datetime


class ErrorCategory(Enum):
    """Categories of errors agents commonly encounter."""
    NETWORK = "network"           # Connectivity issues, timeouts
    API = "api"                   # API errors, rate limits, auth failures
    PARSING = "parsing"           # JSON.parse errors, malformed responses
    VALIDATION = "validation"     # Input validation failures
    RESOURCE = "resource"         # Memory, disk, CPU constraints
    TIMEOUT = "timeout"           # Operation timeouts
    AUTH = "auth"                 # Authentication/authorization errors
    RATE_LIMIT = "rate_limit"     # Rate limiting, throttling
    UNKNOWN = "unknown"           # Unclassified errors


class Severity(Enum):
    """Error severity levels."""
    LOW = "low"           # Minor issues, can continue
    MEDIUM = "medium"     # Significant issues, may need fallback
    HIGH = "high"         # Critical issues, requires intervention
    FATAL = "fatal"       # System-level failures


@dataclass
class ErrorPattern:
    """A documented error pattern with handling strategy."""
    name: str
    category: ErrorCategory
    severity: Severity
    description: str
    detection_pattern: str  # Regex or identifier for detection
    handler: Optional[Callable] = None
    fallback_action: Optional[str] = None
    retry_possible: bool = True
    docs_url: Optional[str] = None
    
    # Metadata
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    occurrence_count: int = 0


@dataclass
class ErrorContext:
    """Context when an error occurs."""
    error_type: str
    error_message: str
    category: ErrorCategory
    severity: Severity
    timestamp: datetime
    service_name: Optional[str] = None
    operation: Optional[str] = None
    raw_error: Optional[Any] = None
    
    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type,
            "error_message": self.error_message,
            "category": self.category.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "service_name": self.service_name,
            "operation": self.operation,
        }


class ErrorPatternRegistry:
    """
    Registry of known error patterns with standardized handling.
    
    Usage:
        registry = ErrorPatternRegistry()
        
        # Register a detected error
        context = registry.register_error(
            error_type="APIError",
            error_message="401 Unauthorized",
            service_name="moltbook"
        )
        
        # Get handling strategy
        pattern = registry.match("APIError", "401 Unauthorized")
        if pattern:
            registry.execute_handler(pattern, context)
    """
    
    def __init__(self):
        self._patterns: dict[str, ErrorPattern] = {}
        self._error_counts: dict[str, int] = {}
        self._initialize_default_patterns()
    
    def _initialize_default_patterns(self):
        """Initialize with common agent error patterns."""
        
        # Network errors
        self.register_pattern(ErrorPattern(
            name="ConnectionTimeout",
            category=ErrorCategory.NETWORK,
            severity=Severity.MEDIUM,
            description="Connection attempt timed out",
            detection_pattern="timeout|TIMEOUT|ConnectionRefused",
            fallback_action="retry_with_backoff",
            retry_possible=True
        ))
        
        self.register_pattern(ErrorPattern(
            name="NetworkUnreachable",
            category=ErrorCategory.NETWORK,
            severity=Severity.HIGH,
            description="Network path unavailable",
            detection_pattern="Network is unreachable|No route to host",
            fallback_action="switch_endpoint",
            retry_possible=True
        ))
        
        # API errors
        self.register_pattern(ErrorPattern(
            name="Unauthorized",
            category=ErrorCategory.AUTH,
            severity=Severity.HIGH,
            description="Authentication failed - token invalid or expired",
            detection_pattern="401|Unauthorized|auth fail",
            fallback_action="refresh_credentials",
            retry_possible=True
        ))
        
        self.register_pattern(ErrorPattern(
            name="Forbidden",
            category=ErrorCategory.AUTH,
            severity=Severity.HIGH,
            description="Authorization failed - insufficient permissions",
            detection_pattern="403|Forbidden|permission denied",
            fallback_action="check_permissions",
            retry_possible=False
        ))
        
        self.register_pattern(ErrorPattern(
            name="RateLimited",
            category=ErrorCategory.RATE_LIMIT,
            severity=Severity.MEDIUM,
            description="Rate limit exceeded - throttling in effect",
            detection_pattern="429|Too Many Requests|rate.limit",
            fallback_action="wait_and_retry",
            retry_possible=True
        ))
        
        self.register_pattern(ErrorPattern(
            name="APINotFound",
            category=ErrorCategory.API,
            severity=Severity.MEDIUM,
            description="Requested API endpoint does not exist",
            detection_pattern="404|Not Found",
            fallback_action="check_endpoint",
            retry_possible=False
        ))
        
        self.register_pattern(ErrorPattern(
            name="APIServerError",
            category=ErrorCategory.API,
            severity=Severity.HIGH,
            description="Server-side API error (5xx)",
            detection_pattern="5[0-9]{2}|Internal Server Error",
            fallback_action="retry_with_backoff",
            retry_possible=True
        ))
        
        # Parsing errors
        self.register_pattern(ErrorPattern(
            name="JSONParseError",
            category=ErrorCategory.PARSING,
            severity=Severity.MEDIUM,
            description="Failed to parse response as JSON",
            detection_pattern="JSONDecodeError|Expecting value|Unexpected end",
            fallback_action="return_raw_response",
            retry_possible=False
        ))
        
        self.register_pattern(ErrorPattern(
            name="MalformedResponse",
            category=ErrorCategory.PARSING,
            severity=Severity.MEDIUM,
            description="Response structure doesn't match expected schema",
            detection_pattern="KeyError|AttributeError|NoneType",
            fallback_action="use_fallback_value",
            retry_possible=False
        ))
        
        # Validation errors
        self.register_pattern(ErrorPattern(
            name="ValidationError",
            category=ErrorCategory.VALIDATION,
            severity=Severity.LOW,
            description="Input validation failed",
            detection_pattern="ValueError|ValidationError|invalid input",
            fallback_action="return_validation_error",
            retry_possible=False
        ))
        
        # Resource errors
        self.register_pattern(ErrorPattern(
            name="MemoryExceeded",
            category=ErrorCategory.RESOURCE,
            severity=Severity.FATAL,
            description="Memory allocation failed",
            detection_pattern="MemoryError|Out of memory|Cannot allocate",
            fallback_action="cleanup_and_retry",
            retry_possible=False
        ))
        
        self.register_pattern(ErrorPattern(
            name="DiskFull",
            category=ErrorCategory.RESOURCE,
            severity=Severity.FATAL,
            description="Disk space exhausted",
            detection_pattern="No space left|Disk full|ENOSPC",
            fallback_action="cleanup_cache",
            retry_possible=False
        ))
        
        # Generic timeout
        self.register_pattern(ErrorPattern(
            name="OperationTimeout",
            category=ErrorCategory.TIMEOUT,
            severity=Severity.MEDIUM,
            description="Operation exceeded allowed time",
            detection_pattern="Timeout|timed out|deadline exceeded",
            fallback_action="retry_operation",
            retry_possible=True
        ))
        
        # Unknown error catch-all
        self.register_pattern(ErrorPattern(
            name="UnknownError",
            category=ErrorCategory.UNKNOWN,
            severity=Severity.MEDIUM,
            description="Unclassified error - requires investigation",
            detection_pattern=".*",
            fallback_action="log_and_continue",
            retry_possible=False
        ))
    
    def register_pattern(self, pattern: ErrorPattern) -> None:
        """Register a new error pattern."""
        self._patterns[pattern.name] = pattern
    
    def match(
        self,
        error_type: str,
        error_message: str
    ) -> Optional[ErrorPattern]:
        """
        Match an error to a registered pattern.
        
        Args:
            error_type: The exception type name
            error_message: The error message content
            
        Returns:
            Matching ErrorPattern or None
        """
        message_lower = error_message.lower()
        
        # Try exact name match first
        if error_type in self._patterns:
            return self._patterns[error_type]
        
        # Try matching by detection pattern in message
        for pattern in self._patterns.values():
            if pattern.detection_pattern == ".*":
                continue  # Skip catch-all for now
            if pattern.detection_pattern.lower() in message_lower:
                return pattern
        
        # Return catch-all unknown error pattern
        return self._patterns.get("UnknownError")
    
    def register_error(
        self,
        error_type: str,
        error_message: str,
        service_name: Optional[str] = None,
        operation: Optional[str] = None,
        raw_error: Optional[Any] = None
    ) -> ErrorContext:
        """
        Register an error occurrence and get context.
        
        Args:
            error_type: Exception type name
            error_message: Error message
            service_name: Optional service where error occurred
            operation: Optional operation being performed
            raw_error: Original exception object
            
        Returns:
            ErrorContext with classification info
        """
        # Count occurrences
        key = f"{error_type}:{error_message[:50]}"
        self._error_counts[key] = self._error_counts.get(key, 0) + 1
        
        # Match to pattern
        pattern = self.match(error_type, error_message)
        
        # Build context
        context = ErrorContext(
            error_type=error_type,
            error_message=error_message,
            category=pattern.category if pattern else ErrorCategory.UNKNOWN,
            severity=pattern.severity if pattern else Severity.MEDIUM,
            timestamp=datetime.now(),
            service_name=service_name,
            operation=operation,
            raw_error=raw_error
        )
        
        # Update pattern metadata if matched
        if pattern:
            pattern.last_seen = context.timestamp
            pattern.occurrence_count += 1
        
        return context
    
    def get_handler(self, pattern: ErrorPattern) -> Callable[[ErrorContext], Any]:
        """
        Get the handler function for a pattern.
        
        Args:
            pattern: The error pattern
            
        Returns:
            Handler function that takes ErrorContext
        """
        if pattern.handler:
            return pattern.handler
        
        # Return default handler based on fallback action
        return self._default_handler
    
    def _default_handler(self, context: ErrorContext) -> dict[str, Any]:
        """Default error handling - return structured error info."""
        return {
            "handled": True,
            "category": context.category.value,
            "severity": context.severity.value,
            "message": context.error_message,
            "action": "manual_intervention_required",
            "context": context.to_dict()
        }
    
    def execute_handler(
        self,
        pattern: ErrorPattern,
        context: ErrorContext
    ) -> Any:
        """
        Execute the handler for a matched pattern.
        
        Args:
            pattern: The matched error pattern
            context: Error context
            
        Returns:
            Handler result
        """
        handler = self.get_handler(pattern)
        return handler(context)
    
    def get_patterns_by_category(self, category: ErrorCategory) -> list[ErrorPattern]:
        """Get all patterns in a category."""
        return [p for p in self._patterns.values() if p.category == category]
    
    def get_top_errors(self, limit: int = 10) -> list[tuple[str, int]]:
        """
        Get most frequently occurring errors.
        
        Returns:
            List of (error_key, count) tuples, sorted by count desc
        """
        sorted_errors = sorted(
            self._error_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_errors[:limit]
    
    def get_statistics(self) -> dict[str, Any]:
        """Get registry statistics."""
        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        
        for pattern in self._patterns.values():
            cat = pattern.category.value
            sev = pattern.severity.value
            by_category[cat] = by_category.get(cat, 0) + pattern.occurrence_count
            by_severity[sev] = by_severity.get(sev, 0) + pattern.occurrence_count
        
        return {
            "total_patterns": len(self._patterns),
            "total_errors": sum(self._error_counts.values()),
            "by_category": by_category,
            "by_severity": by_severity,
            "top_errors": self.get_top_errors(5)
        }
    
    def register_handler(self, pattern_name: str, handler: Callable) -> bool:
        """
        Register a custom handler for a pattern.
        
        Args:
            pattern_name: Name of the pattern
            handler: Handler function (receives ErrorContext)
            
        Returns:
            True if pattern exists and handler registered
        """
        if pattern_name in self._patterns:
            self._patterns[pattern_name].handler = handler
            return True
        return False


# Convenience function for quick error registration
def create_error_context(
    error_type: str,
    error_message: str,
    service_name: Optional[str] = None
) -> ErrorContext:
    """
    Quick function to classify an error.
    
    Args:
        error_type: Exception type name
        error_message: Error message
        service_name: Optional service name
        
    Returns:
        ErrorContext with classification
    """
    registry = ErrorPatternRegistry()
    return registry.register_error(error_type, error_message, service_name)

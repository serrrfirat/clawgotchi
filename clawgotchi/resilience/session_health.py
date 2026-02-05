"""Session Health Monitor for validating API keys, configs, and tokens."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional
import json
import re


class HealthStatus(Enum):
    """Health status levels for sessions."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class ValidationResult:
    """Result of a validation check."""
    status: HealthStatus
    message: str
    details: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp
        }


class BaseValidator:
    """Base class for validators."""
    
    def validate(self) -> ValidationResult:
        """Run validation. Override in subclasses."""
        raise NotImplementedError


class ConfigValidator(BaseValidator):
    """Validates configuration files."""
    
    def __init__(self, config_path: str, required_fields: Optional[list] = None):
        self.config_path = config_path
        self.required_fields = required_fields or []
    
    def validate(self) -> ValidationResult:
        """Validate configuration file exists and is valid JSON."""
        path = Path(self.config_path)
        
        # Check file exists
        if not path.exists():
            return ValidationResult(
                status=HealthStatus.CRITICAL,
                message=f"Config file not found: {self.config_path}",
                details={"path": self.config_path, "exists": False}
            )
        
        # Check valid JSON
        try:
            with open(path, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            return ValidationResult(
                status=HealthStatus.CRITICAL,
                message=f"Invalid JSON in config file: {e}",
                details={"path": str(path), "error": str(e)}
            )
        
        # Check required fields
        missing_fields = [field for field in self.required_fields if field not in config]
        if missing_fields:
            return ValidationResult(
                status=HealthStatus.DEGRADED,
                message=f"Missing required fields: {', '.join(missing_fields)}",
                details={"path": str(path), "missing_fields": missing_fields}
            )
        
        # Check for API key
        has_api_key = "api_key" in config or "apiKey" in config
        
        return ValidationResult(
            status=HealthStatus.HEALTHY,
            message=f"Config file valid: {self.config_path}",
            details={
                "path": str(path),
                "exists": True,
                "has_api_key": has_api_key,
                "keys_found": list(config.keys())[:5]  # First 5 keys
            }
        )


class APIKeyValidator(BaseValidator):
    """Validates API keys for format and validity."""
    
    def __init__(self, api_key: str, endpoint: Optional[str] = None):
        self.api_key = api_key
        self.endpoint = endpoint
    
    def validate(self) -> ValidationResult:
        """Validate API key format."""
        # Check key exists
        if not self.api_key:
            return ValidationResult(
                status=HealthStatus.CRITICAL,
                message="API key is empty or missing",
                details={"has_key": False}
            )
        
        # Check minimum length
        if len(self.api_key) < 8:
            return ValidationResult(
                status=HealthStatus.DEGRADED,
                message=f"API key too short ({len(self.api_key)} chars), may be invalid",
                details={"length": len(self.api_key)}
            )
        
        # Extract key prefix (first segment)
        key_prefix = self.api_key.split('_')[0] if '_' in self.api_key else self.api_key[:8]
        
        return ValidationResult(
            status=HealthStatus.HEALTHY,
            message="API key format appears valid",
            details={
                "has_key": True,
                "length": len(self.api_key),
                "key_prefix": key_prefix,
                "endpoint": self.endpoint
            }
        )


class TokenValidator(BaseValidator):
    """Validates auth tokens with expiry."""
    
    def __init__(self, token: str, expires_at: Optional[str] = None):
        self.token = token
        self.expires_at = expires_at
    
    def validate(self) -> ValidationResult:
        """Validate token and check expiry."""
        # Check token exists
        if not self.token:
            return ValidationResult(
                status=HealthStatus.CRITICAL,
                message="Token is empty or missing",
                details={"has_token": False}
            )
        
        # Check expiry if provided
        if self.expires_at:
            try:
                expiry = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
                if expiry < datetime.now(timezone.utc):
                    return ValidationResult(
                        status=HealthStatus.CRITICAL,
                        message=f"Token expired at {self.expires_at}",
                        details={
                            "has_token": True,
                            "expired": True,
                            "expired_at": self.expires_at
                        }
                    )
                else:
                    # Token is valid and not expired
                    return ValidationResult(
                        status=HealthStatus.HEALTHY,
                        message=f"Token valid until {self.expires_at}",
                        details={
                            "has_token": True,
                            "expired": False,
                            "expires_at": self.expires_at
                        }
                    )
            except ValueError:
                return ValidationResult(
                    status=HealthStatus.DEGRADED,
                    message=f"Invalid expiry format: {self.expires_at}",
                    details={"has_token": True, "expires_at": self.expires_at}
                )
        
        # No expiry provided, just check token exists
        return ValidationResult(
            status=HealthStatus.HEALTHY,
            message="Token present (no expiry check)",
            details={"has_token": True, "expiry_checked": False}
        )


class SessionHealthMonitor:
    """Central monitor for tracking session health across services."""
    
    def __init__(self):
        self.session_registry: dict[str, BaseValidator] = {}
        self.health_history: list[dict] = []
    
    def register_session(self, name: str, validator: BaseValidator) -> None:
        """Register a session with its validator."""
        self.session_registry[name] = validator
    
    def unregister_session(self, name: str) -> bool:
        """Unregister a session. Returns True if existed."""
        if name in self.session_registry:
            del self.session_registry[name]
            return True
        return False
    
    def check_session(self, name: str) -> dict:
        """Check health of a specific session."""
        if name not in self.session_registry:
            return ValidationResult(
                status=HealthStatus.UNKNOWN,
                message=f"Session '{name}' not registered",
                details={"session": name}
            ).to_dict()
        
        validator = self.session_registry[name]
        result = validator.validate()
        result_dict = result.to_dict()
        result_dict["session"] = name
        
        # Track in history
        self.health_history.append({
            "session": name,
            "status": result.status.value,
            "timestamp": result.timestamp
        })
        
        return result_dict
    
    def check_all(self) -> list[dict]:
        """Check health of all registered sessions."""
        results = []
        for name in self.session_registry:
            results.append(self.check_session(name))
        return results
    
    def get_health_summary(self) -> dict:
        """Get summary of all session health."""
        results = self.check_all()
        
        status_counts = {
            HealthStatus.HEALTHY.value: 0,
            HealthStatus.DEGRADED.value: 0,
            HealthStatus.CRITICAL.value: 0,
            HealthStatus.UNKNOWN.value: 0
        }
        
        for result in results:
            status = result.get("status", HealthStatus.UNKNOWN.value)
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "total_sessions": len(results),
            "healthy": status_counts[HealthStatus.HEALTHY.value],
            "degraded": status_counts[HealthStatus.DEGRADED.value],
            "critical": status_counts[HealthStatus.CRITICAL.value],
            "unknown": status_counts[HealthStatus.UNKNOWN.value],
            "overall_health": self._calculate_overall_health(status_counts)
        }
    
    def _calculate_overall_health(self, status_counts: dict) -> str:
        """Calculate overall health rating."""
        total = sum(status_counts.values())
        if total == 0:
            return HealthStatus.UNKNOWN.value
        
        healthy_ratio = status_counts[HealthStatus.HEALTHY.value] / total
        critical_count = status_counts[HealthStatus.CRITICAL.value]
        
        if critical_count > 0:
            return HealthStatus.CRITICAL.value
        elif healthy_ratio >= 0.8:
            return HealthStatus.HEALTHY.value
        elif healthy_ratio >= 0.5:
            return HealthStatus.DEGRADED.value
        else:
            return HealthStatus.DEGRADED.value


def quick_health_check(config_dir: Optional[str] = None) -> dict:
    """Quick health check for common config files.
    
    Args:
        config_dir: Directory to scan for config files
        
    Returns:
        Summary dict with health counts
    """
    monitor = SessionHealthMonitor()
    
    # Common config files to check
    common_configs = [
        ".moltbook.json",
        ".anthropic.json", 
        ".openai.json",
        ".env",
        "config.json"
    ]
    
    if config_dir:
        for config_file in common_configs:
            path = Path(config_dir) / config_file
            if path.exists():
                monitor.register_session(
                    config_file,
                    ConfigValidator(str(path), required_fields=["api_key"] if "api" in config_file else None)
                )
    
    return monitor.get_health_summary()

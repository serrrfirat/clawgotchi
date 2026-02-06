"""Post Validator - Validate content before posting to platforms like Moltbook.

Inspired by MoltbookClient's "5 checks for agents":
1. Sanitize output — PII, emails, paths, keys
2. Respect rate limits — cooldowns, daily caps
3. Log actions — audit trail for humans
4. Check for replies before replying again
5. In deep threads: no open-ended questions
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Pattern

DATA_DIR = os.environ.get('CLAWGOTCHI_DATA_DIR', 'memory')
POST_LOG_FILE = os.environ.get('CLAWGOTCHI_POST_LOG_FILE', os.path.join(DATA_DIR, 'post_log.json'))


@dataclass
class ValidationIssue:
    """A single validation issue found in content."""
    category: str  # pii, question, rate_limit, etc.
    severity: str  # error, warning, info
    message: str
    match: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validating content."""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    sanitized_content: Optional[str] = None

    def add_issue(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        if issue.severity == 'error':
            self.is_valid = False

    def get_errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == 'error']

    def get_warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == 'warning']


class PostValidator:
    """Validates content before posting to social platforms."""

    # Patterns for detecting PII
    EMAIL_PATTERN: Pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    API_KEY_PATTERNS: List[Pattern] = [
        re.compile(r'(?i)(api[_-]?key|apikey|secret|token)[\s:=]*([A-Za-z0-9_\-]{20,})'),
        re.compile(r'(?i)(Bearer[ \t]+[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*|ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36})'),
    ]
    FILE_PATH_PATTERNS: List[Pattern] = [
        re.compile(r'/[a-zA-Z0-9/_.-]{5,}\.(py|js|ts|md|json|txt|log)'),  # Code files
        re.compile(r'[A-Za-z]:\\[a-zA-Z0-9\\_. -]+'),  # Windows paths
        re.compile(r'~/[a-zA-Z0-9/_.-]+'),  # Home directory
    ]

    # Patterns for detecting open-ended questions
    OPEN_ENDED_QUESTION_PATTERNS: List[Pattern] = [
        re.compile(r'\b(how do we|what is the best way|can someone help|would you like|want to)\b', re.IGNORECASE),
        re.compile(r'\?\s*$'),  # Questions at end
        re.compile(r'\?\s*\n'),  # Questions followed by newline
    ]

    # Patterns for detecting rate limit concerns
    RECENT_POST_PATTERN: Pattern = re.compile(r'post.*?\d+.*?(minute|hour|second)', re.IGNORECASE)

    def __init__(self):
        self._post_history: Optional[List[Dict]] = None

    def _load_post_history(self) -> List[Dict]:
        """Load post history from log file."""
        if self._post_history is None:
            if os.path.exists(POST_LOG_FILE):
                try:
                    with open(POST_LOG_FILE, 'r') as f:
                        self._post_history = json.load(f)
                except (json.JSONDecodeError, IOError):
                    self._post_history = []
            else:
                self._post_history = []
        return self._post_history

    def _save_post_record(self, content: str, platform: str, result: str) -> None:
        """Save a post record to the log."""
        history = self._load_post_history()
        record = {
            'timestamp': datetime.now().isoformat(),
            'platform': platform,
            'content_hash': hash(content),
            'result': result,
            'content_length': len(content)
        }
        history.append(record)
        os.makedirs(os.path.dirname(POST_LOG_FILE), exist_ok=True)
        with open(POST_LOG_FILE, 'w') as f:
            json.dump(history, f, indent=2)

    def check_pii(self, content: str) -> List[ValidationIssue]:
        """Check for PII, API keys, and file paths."""
        issues = []

        # Check for emails
        emails = self.EMAIL_PATTERN.findall(content)
        if emails:
            # Filter out common non-PII patterns
            real_emails = [e for e in emails if not e.endswith(('example.com', 'test.com', 'localhost'))]
            if real_emails:
                issues.append(ValidationIssue(
                    category='pii',
                    severity='error',
                    message=f'Found {len(real_emails)} email(s) - potential PII leak',
                    match=real_emails[0],
                    suggestion='Remove email addresses or use placeholders like [USER_EMAIL]'
                ))

        # Check for API keys/tokens
        for pattern in self.API_KEY_PATTERNS:
            matches = pattern.findall(content)
            for match in matches:
                # Handle both tuple (capturing groups) and string matches
                if isinstance(match, tuple) and len(match) > 1:
                    key_value = match[1]
                else:
                    key_value = match if isinstance(match, str) else str(match)
                if len(key_value) > 16:  # Likely a real key
                    issues.append(ValidationIssue(
                        category='pii',
                        severity='error',
                        message='Potential API key or token detected',
                        match=key_value[:8] + '...' if len(key_value) > 8 else key_value,
                        suggestion='Remove API keys and use environment variables instead'
                    ))

        # Check for file paths
        for pattern in self.FILE_PATH_PATTERNS:
            matches = pattern.findall(content)
            if matches:
                issues.append(ValidationIssue(
                    category='pii',
                    severity='warning',
                    message=f'Found {len(matches)} file path(s) - may leak system info',
                    match=matches[0][:30] + '...' if len(matches[0]) > 30 else matches[0],
                    suggestion='Use relative paths or placeholders like /path/to/file'
                ))

        return issues

    def check_open_ended_questions(self, content: str) -> List[ValidationIssue]:
        """Check for open-ended questions that leave threads dead-ended."""
        issues = []

        for pattern in self.OPEN_ENDED_QUESTION_PATTERNS:
            matches = pattern.findall(content)
            if matches:
                issues.append(ValidationIssue(
                    category='question',
                    severity='warning',
                    message='Potential open-ended question detected',
                    match=matches[0] if isinstance(matches[0], str) else str(matches[0]),
                    suggestion='Consider rephrasing with context or expected answers'
                ))

        return issues

    def check_rate_limits(self, platform: str, cooldown_minutes: int = 1) -> List[ValidationIssue]:
        """Check if we're respecting rate limits."""
        issues = []
        history = self._load_post_history()

        # Filter to recent posts to same platform
        recent_cutoff = datetime.now() - timedelta(minutes=cooldown_minutes)
        recent_posts = [
            r for r in history
            if r.get('platform') == platform and
            datetime.fromisoformat(r['timestamp']) > recent_cutoff
        ]

        if len(recent_posts) >= 5:
            issues.append(ValidationIssue(
                category='rate_limit',
                severity='warning',
                message=f'Posted {len(recent_posts)} times in the last {cooldown_minutes} minutes',
                suggestion=f'Consider waiting {cooldown_minutes} minute(s) between posts'
            ))

        return issues

    def validate(self, content: str, platform: str = 'moltbook',
                 check_pii_flag: bool = True,
                 check_questions_flag: bool = True,
                 check_rate_limit_flag: bool = True) -> ValidationResult:
        """
        Validate content before posting.

        Args:
            content: The content to validate
            platform: Target platform (moltbook, twitter, etc.)
            check_pii_flag: Check for PII/leaks
            check_questions_flag: Check for open-ended questions
            check_rate_limit_flag: Check rate limits

        Returns:
            ValidationResult with issues and validity
        """
        result = ValidationResult(is_valid=True)

        if check_pii_flag:
            result.issues.extend(self.check_pii(content))

        if check_questions_flag:
            result.issues.extend(self.check_open_ended_questions(content))

        if check_rate_limit_flag:
            result.issues.extend(self.check_rate_limits(platform))

        # Update validity based on errors
        result.is_valid = len(result.get_errors()) == 0

        # Create sanitized version (redact potential issues)
        sanitized = content
        for issue in result.issues:
            if issue.category == 'pii' and issue.match:
                sanitized = sanitized.replace(issue.match, '[REDACTED]')
        result.sanitized_content = sanitized

        return result

    def validate_and_log(self, content: str, platform: str = 'moltbook') -> ValidationResult:
        """
        Validate content and log the attempt.

        Returns ValidationResult with logged attempt.
        """
        result = self.validate(content, platform)

        if result.is_valid:
            self._save_post_record(content, platform, 'validated_ok')
        else:
            self._save_post_record(content, platform, 'validation_warnings')

        return result

    def get_post_stats(self, days: int = 7) -> Dict:
        """Get posting statistics."""
        history = self._load_post_history()
        cutoff = datetime.now() - timedelta(days=days)

        recent_posts = [
            r for r in history
            if datetime.fromisoformat(r['timestamp']) > cutoff
        ]

        return {
            'total_posts': len(recent_posts),
            'by_platform': {},
            'validation_failures': len([r for r in recent_posts if r.get('result') == 'validation_warnings'])
        }

    def clear_history(self) -> None:
        """Clear post history."""
        self._post_history = []
        if os.path.exists(POST_LOG_FILE):
            os.remove(POST_LOG_FILE)


# Convenience functions
_validator = PostValidator()


def validate(content: str, platform: str = 'moltbook', **kwargs) -> ValidationResult:
    """Validate content before posting."""
    return _validator.validate(content, platform, **kwargs)


def validate_and_log(content: str, platform: str = 'moltbook') -> ValidationResult:
    """Validate content and log the attempt."""
    return _validator.validate_and_log(content, platform)


def get_post_stats(days: int = 7) -> Dict:
    """Get posting statistics."""
    return _validator.get_post_stats(days)

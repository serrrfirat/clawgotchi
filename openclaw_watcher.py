"""OpenClaw gateway watcher — polls status, reads cron jobs, builds live feed."""

import json
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

GATEWAY_LOG = Path.home() / ".openclaw" / "logs" / "gateway.log"
CRON_JOBS_FILE = Path.home() / ".openclaw" / "cron" / "jobs.json"
SESSIONS_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
SESSIONS_INDEX = SESSIONS_DIR / "sessions.json"
POLL_INTERVAL = 10  # seconds
MAX_FEED = 500
SESSION_TAIL_INTERVAL = 2  # seconds

# Agent names to look for when parsing event text
KNOWN_AGENTS = [
    "Jarvis", "Shuri", "Friday", "Loki", "Wanda",
    "Vision", "Fury", "Quill", "Pepper", "Wong",
]

# Keyword → agent fallback when agent name isn't in the text
KEYWORD_AGENT_MAP = {
    "squad": "Jarvis",
    "design": "Wanda",
    "email": "Pepper",
    "documentation": "Wong",
    "docs": "Wong",
    "research": "Fury",
    "social": "Quill",
    "content": "Quill",
}


@dataclass
class FeedItem:
    timestamp: float
    source: str      # agent name or [telegram], [gateway], etc.
    summary: str

    @property
    def time_str(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%H:%M")


@dataclass
class GatewayState:
    online: bool = False
    active_agents: int = 0
    active_sessions: int = 0
    channels: list = field(default_factory=list)
    last_poll_at: float = 0.0


class OpenClawWatcher:
    """Watches the OpenClaw gateway and builds a live event feed."""

    def __init__(self):
        self.state = GatewayState()
        self.feed: list[FeedItem] = []
        self._feed_lock = threading.Lock()
        self._stop = threading.Event()
        self._poll_thread: threading.Thread | None = None
        self._log_thread: threading.Thread | None = None
        self._session_thread: threading.Thread | None = None
        self._log_pos = 0
        # job UUID → agent display name (from jobs.json)
        self._job_agent_map: dict[str, str] = {}
        # session file → file position for tailing
        self._session_positions: dict[str, int] = {}
        # session key → agent name (from sessions.json + jobs map)
        self._session_agent_map: dict[str, str] = {}
        # Track what we've already added to avoid duplicates
        self._seen_keys: set[str] = set()

    def start(self):
        self._stop.clear()
        self._load_cron_jobs()
        self._load_session_map()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        self._log_thread = threading.Thread(target=self._log_watch_loop, daemon=True)
        self._log_thread.start()
        self._seed_recent_messages()
        self._session_thread = threading.Thread(target=self._session_watch_loop, daemon=True)
        self._session_thread.start()

    def stop(self):
        self._stop.set()

    # ── Cron jobs.json → agent name map ───────────────────────────────────

    def _load_cron_jobs(self):
        """Read jobs.json to build job-ID → agent-name mapping."""
        if not CRON_JOBS_FILE.exists():
            return
        try:
            data = json.loads(CRON_JOBS_FILE.read_text())
            for job in data.get("jobs", []):
                job_id = job.get("id", "")
                job_name = job.get("name", "")
                msg = job.get("payload", {}).get("message", "")
                # Extract "You are <Name>" from the prompt
                m = re.match(r"You are (\w+)", msg)
                agent_name = m.group(1) if m else job_name.split("-")[0].capitalize()
                if job_id:
                    self._job_agent_map[job_id] = agent_name
        except (json.JSONDecodeError, OSError):
            pass

    # ── Gateway status polling ────────────────────────────────────────────

    def _poll_loop(self):
        while not self._stop.is_set():
            self._poll_gateway()
            self._stop.wait(POLL_INTERVAL)

    def _poll_gateway(self):
        try:
            result = subprocess.run(
                ["openclaw", "gateway", "call", "status", "--json", "--timeout", "3000"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                # Strip ANSI codes from output
                raw = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
                idx = raw.find("{")
                if idx >= 0:
                    data = json.loads(raw[idx:])
                    self.state.online = True
                    self._parse_status(data)
                else:
                    self.state.online = False
            else:
                self.state.online = False
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, ValueError):
            self.state.online = False
        self.state.last_poll_at = time.time()

    def _parse_status(self, data: dict):
        # Sessions
        sessions = data.get("sessions", {})
        self.state.active_sessions = sessions.get("count", 0)

        # Channels
        channel_summary = data.get("channelSummary", [])
        self.state.channels = [
            ch for ch in channel_summary if "configured" in ch.lower()
        ]

        # Parse queuedSystemEvents (list of strings)
        events = data.get("queuedSystemEvents", [])
        self.state.active_agents = len(events)
        for event_str in events:
            if isinstance(event_str, str):
                self._parse_cron_event(event_str)

        # Parse recent sessions
        for session in sessions.get("recent", []):
            self._parse_session(session)

        # Reload jobs map periodically (agents can be added)
        self._load_cron_jobs()

    def _parse_cron_event(self, event_str: str):
        """Parse a queuedSystemEvent string like 'Cron: **Shuri Report**...'"""
        # Strip "Cron: " prefix
        text = event_str
        if text.startswith("Cron: "):
            text = text[6:]

        # Skip bare heartbeat-only events (no useful info)
        if text.strip() == "HEARTBEAT_OK":
            return

        # Try to identify the agent name from the text
        agent = self._identify_agent(text)

        # Extract a one-line summary
        summary = self._extract_summary(text)

        key = f"event:{agent}:{summary}"
        if key in self._seen_keys:
            return
        self._seen_keys.add(key)
        self._trim_seen()

        self._add_feed(FeedItem(
            timestamp=time.time(),
            source=agent,
            summary=summary,
        ))

    def _identify_agent(self, text: str) -> str:
        """Try to find a known agent name in the event text."""
        text_lower = text.lower()
        # Direct agent name match (most reliable)
        for name in KNOWN_AGENTS:
            if name.lower() in text_lower:
                return name

        # Keyword-based fallback for agents whose names aren't in their reports
        for keyword, agent in KEYWORD_AGENT_MAP.items():
            if keyword in text_lower:
                return agent

        return "[cron]"

    def _extract_summary(self, text: str) -> str:
        """Get a clean summary from event text."""
        # Remove markdown bold/italic/header markers but keep underscores in words
        clean = re.sub(r"\*+", "", text)
        clean = re.sub(r"^#+\s*", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"`", "", clean)
        # Remove emoji
        clean = re.sub(r"[\U0001f300-\U0001f9ff\u2600-\u27bf\u2b50\u2705\u26a0\ufe0f\u23f8\U0001f534\U0001f7e1\U0001f7e2]", "", clean)
        # Take first meaningful line
        for line in clean.split("\n"):
            line = line.strip().strip("-").strip()
            if not line:
                continue
            if line in ("HEARTBEAT_OK", "Cron"):
                continue
            # Strip leading whitespace artifacts
            line = re.sub(r"^[\s\ufe0f]+", "", line)
            if not line:
                continue
            return line

        return "All nominal. Standing by."

    def _parse_session(self, session: dict):
        """Parse a recent session entry, map to agent name via job ID."""
        key = session.get("key", "")
        updated_at = session.get("updatedAt", 0)
        age = session.get("age", 0)
        model = session.get("model", "")
        tokens = session.get("totalTokens", 0)

        # Extract job UUID from key like "agent:main:cron:<uuid>"
        m = re.match(r"agent:\w+:cron:(.+)", key)
        if not m:
            return

        job_id = m.group(1)
        agent_name = self._job_agent_map.get(job_id, "[agent]")

        # Convert updatedAt (ms epoch) to timestamp
        ts = updated_at / 1000 if updated_at > 1e12 else updated_at

        # Build summary
        age_min = age // 60
        if age_min < 60:
            age_str = f"{age_min}m ago"
        else:
            age_str = f"{age_min // 60}h ago"
        summary = f"Session active ({age_str}, {tokens} tokens, {model})"

        seen_key = f"session:{job_id}:{updated_at}"
        if seen_key in self._seen_keys:
            return
        self._seen_keys.add(seen_key)
        self._trim_seen()

        self._add_feed(FeedItem(timestamp=ts, source=agent_name, summary=summary))

    # ── Session JSONL tailing (chat messages) ───────────────────────────────

    def _load_session_map(self):
        """Read sessions.json to map session keys to file paths and agent names."""
        if not SESSIONS_INDEX.exists():
            return
        try:
            data = json.loads(SESSIONS_INDEX.read_text())
            for session_key, val in data.items():
                if isinstance(val, str):
                    try:
                        val = json.loads(val)
                    except json.JSONDecodeError:
                        continue
                if not isinstance(val, dict):
                    continue
                session_id = val.get("sessionId", "")
                if not session_id:
                    continue
                session_file = SESSIONS_DIR / f"{session_id}.jsonl"

                # Determine agent name for this session
                if session_key == "agent:main:main":
                    agent_name = "Clawd"
                else:
                    jm = re.match(r"agent:\w+:cron:(.+)", session_key)
                    if jm:
                        agent_name = self._job_agent_map.get(jm.group(1), "[agent]")
                    else:
                        agent_name = "[agent]"

                self._session_agent_map[str(session_file)] = agent_name
                # Seek to end so we only get new messages
                if str(session_file) not in self._session_positions:
                    try:
                        self._session_positions[str(session_file)] = session_file.stat().st_size
                    except OSError:
                        self._session_positions[str(session_file)] = 0
        except (json.JSONDecodeError, OSError):
            pass

    def _seed_recent_messages(self):
        """Load recent messages from tracked sessions to populate the feed on startup."""
        for file_path_str, agent_name in list(self._session_agent_map.items()):
            file_path = Path(file_path_str)
            if not file_path.exists():
                continue
            try:
                size = file_path.stat().st_size
                # Main session can be very large — read more to find telegram chats
                read_size = 500_000 if agent_name == "Clawd" else 50_000
                read_from = max(0, size - read_size)
                with open(file_path, "r") as f:
                    if read_from > 0:
                        f.seek(read_from)
                        f.readline()  # skip partial line
                    lines = f.readlines()
                # Parse last N relevant messages
                for line in lines[-100:]:
                    self._parse_session_message(line.strip(), agent_name)
            except OSError:
                continue

    def _session_watch_loop(self):
        """Tail session JSONL files for new chat messages."""
        while not self._stop.is_set():
            try:
                self._check_sessions()
            except OSError:
                pass
            self._stop.wait(SESSION_TAIL_INTERVAL)

    def _check_sessions(self):
        """Read new lines from all tracked session files."""
        # Periodically refresh the session map (new sessions may appear)
        self._load_session_map()

        for file_path_str, agent_name in list(self._session_agent_map.items()):
            file_path = Path(file_path_str)
            if not file_path.exists():
                continue
            try:
                size = file_path.stat().st_size
            except OSError:
                continue
            pos = self._session_positions.get(file_path_str, 0)
            if size < pos:
                pos = 0  # file was rotated/recreated
            if size <= pos:
                continue
            try:
                with open(file_path, "r") as f:
                    f.seek(pos)
                    new_lines = f.readlines()
                    self._session_positions[file_path_str] = f.tell()
            except OSError:
                continue
            for line in new_lines:
                self._parse_session_message(line.strip(), agent_name)

    def _parse_session_message(self, line: str, agent_name: str):
        """Parse a JSONL session line into a feed item."""
        if not line:
            return
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return

        if entry.get("type") != "message":
            return

        msg = entry.get("message", {})
        role = msg.get("role", "")
        ts_str = entry.get("timestamp", "")

        # Parse timestamp
        ts = time.time()
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
            except ValueError:
                pass

        # Extract text content
        content_blocks = msg.get("content", [])
        if isinstance(content_blocks, str):
            text = content_blocks
        else:
            text_parts = []
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            text = " ".join(text_parts)

        if not text:
            return

        if role == "user":
            # Parse telegram user messages: "[Telegram Name (@handle) ...] actual message"
            m = re.match(r"\[Telegram\s+(.+?)(?:\s+\(.*?\))?\s+.*?\]\s*(.+)", text, re.DOTALL)
            if m:
                user_name = m.group(1).split()[0]  # First name
                message = m.group(2).strip()  # Full message (not just first line)
                if message and "[message_id:" not in message:
                    source = f"[tg] {user_name}"
                    self._add_feed(FeedItem(ts, source, message))
            # Skip cron prompts and system messages (not real user chat)

        elif role == "assistant":
            # Show full text responses, skip tool calls / thinking
            clean = text.strip()
            if not clean or "HEARTBEAT_OK" in clean:
                return
            # Strip markdown and XML tags
            clean = re.sub(r"</?final>", "", clean)
            clean = re.sub(r"\*+", "", clean)
            clean = re.sub(r"[\U0001f300-\U0001f9ff\u2600-\u27bf\u2705\u26a0\ufe0f]", "", clean)
            clean = clean.strip()
            if not clean:
                return
            # Get full text (join multiple lines)
            summary = clean.replace("\n", " ")
            self._add_feed(FeedItem(ts, agent_name, summary))

    # ── Log file watching ─────────────────────────────────────────────────

    def _log_watch_loop(self):
        if not GATEWAY_LOG.exists():
            return
        try:
            self._log_pos = GATEWAY_LOG.stat().st_size
        except OSError:
            self._log_pos = 0
        while not self._stop.is_set():
            try:
                self._check_log()
            except OSError:
                pass
            self._stop.wait(2)

    def _check_log(self):
        if not GATEWAY_LOG.exists():
            return
        size = GATEWAY_LOG.stat().st_size
        if size < self._log_pos:
            self._log_pos = 0
        if size <= self._log_pos:
            return
        with open(GATEWAY_LOG, "r") as f:
            f.seek(self._log_pos)
            new_lines = f.readlines()
            self._log_pos = f.tell()
        for line in new_lines:
            self._parse_log_line(line.strip())

    def _parse_log_line(self, line: str):
        if not line:
            return

        ts = time.time()
        m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", line)
        if m:
            try:
                ts = datetime.fromisoformat(m.group(1)).timestamp()
            except ValueError:
                pass

        lower = line.lower()

        if "[telegram]" in lower:
            # Extract the useful part after [telegram]
            summary = re.sub(r".*?\[telegram\]\s*", "", line, count=1)
            summary = re.sub(r"^\[\w+\]\s*", "", summary)  # strip [default] etc.
            if summary:
                self._add_feed(FeedItem(ts, "[telegram]", summary))

        elif "[gateway]" in lower and ("signal" in lower or "listening" in lower or "shut" in lower):
            summary = re.sub(r".*?\[gateway\]\s*", "", line, count=1)
            self._add_feed(FeedItem(ts, "[gateway]", summary))

        elif "[heartbeat]" in lower:
            summary = re.sub(r".*?\[heartbeat\]\s*", "", line, count=1)
            self._add_feed(FeedItem(ts, "[heartbeat]", summary))

        elif "error" in lower and "[ws]" not in lower:
            summary = re.sub(r".*?(error|ERR)\s*:?\s*", "", line, flags=re.IGNORECASE)
            if summary:
                self._add_feed(FeedItem(ts, "[error]", summary))

    # ── Feed management ───────────────────────────────────────────────────

    def _add_feed(self, item: FeedItem):
        with self._feed_lock:
            self.feed.append(item)
            if len(self.feed) > MAX_FEED:
                self.feed = self.feed[-MAX_FEED:]

    def _trim_seen(self):
        if len(self._seen_keys) > 200:
            self._seen_keys = set(list(self._seen_keys)[-100:])

    def get_feed(self, count: int = 20) -> list[FeedItem]:
        with self._feed_lock:
            sorted_feed = sorted(self.feed, key=lambda x: x.timestamp)
            return sorted_feed[-count:]

    def feed_rate(self, window: float = 300.0) -> float:
        """Events per minute in the last `window` seconds."""
        cutoff = time.time() - window
        with self._feed_lock:
            recent = sum(1 for item in self.feed if item.timestamp > cutoff)
        return (recent / window) * 60 if window > 0 else 0.0

    def get_channel_str(self) -> str:
        if not self.state.channels:
            return "none"
        names = []
        for ch in self.state.channels:
            if "telegram" in ch.lower():
                names.append("tg")
            elif "discord" in ch.lower():
                names.append("dc")
            elif "slack" in ch.lower():
                names.append("sl")
            else:
                names.append(ch.split(":")[0].strip()[:6])
        return "/".join(names) if names else "none"

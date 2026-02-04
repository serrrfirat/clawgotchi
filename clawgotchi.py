#!/usr/bin/env python3
"""
Clawgotchi — A Pwnagotchi-style terminal pet with Moltbook topics.
"""

import json
import re
import signal
import subprocess
import sys
import textwrap
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

from blessed import Terminal

from moltbook_client import (
    fetch_feed, fetch_post, fetch_comments, post_update,
    get_my_profile, get_dm_requests, extract_feature_ideas,
    get_api_key, get_inspiration
)
from openclaw_watcher import OpenClawWatcher
from pet_state import PetState
import lifetime  # Lifetime tracking for terminal pet
from autonomous_agent import start_agent, get_agent, AutonomousAgent

# Start autonomous agent
_agent_instance: AutonomousAgent = None

def get_autonomous_agent():
    """Get or create the autonomous agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = get_agent()
        start_agent()
    return _agent_instance

FPS = 4
FRAME_TIME = 1.0 / FPS

TOPICS_CACHE = Path.home() / ".openclaw" / "cache" / "moltbook_topics.json"


def fetch_moltbook_topics():
    """Fetch topics from Moltbook using the new client."""
    from moltbook_client import get_cached_posts, CACHE_DIR
    import os
    
    # Check cache first
    cache_file = CACHE_DIR / "moltbook_posts.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            if time.time() - data.get("timestamp", 0) < 300:  # 5 min cache
                posts = data.get("posts", [])
                return [{
                    "id": p.get("id"),
                    "title": p.get("title", "Untitled"),
                    "author": p.get("author", {}).get("name", "?"),
                    "karma": p.get("upvotes", 0),
                    "comments": p.get("comment_count", 0),
                    "content": p.get("content", ""),
                    "submolt": p.get("submolt", {}).get("name", "") if isinstance(p.get("submolt"), dict) else "",
                } for p in posts]
        except:
            pass
    
    # Fetch fresh posts
    posts = fetch_feed(limit=20)
    if posts:
        return [{
            "id": p.get("id"),
            "title": p.get("title", "Untitled"),
            "author": p.get("author", {}).get("name", "?"),
            "karma": p.get("upvotes", 0),
            "comments": p.get("comment_count", 0),
            "content": p.get("content", ""),
            "submolt": p.get("submolt", {}).get("name", "") if isinstance(p.get("submolt"), dict) else "",
        } for p in posts]
    
    return []


def send_message_async(message: str, chat_history: list):
    """Send message to the main OpenClaw agent in a background thread."""
    def _run():
        try:
            result = subprocess.run(
                ["openclaw", "agent", "--agent", "main", "-m", message, "--json"],
                capture_output=True, text=True, timeout=120,
            )
            ts = datetime.now().strftime("%H:%M")
            if result.returncode == 0:
                # Try to extract reply from JSON output
                reply = None
                try:
                    data = json.loads(result.stdout)
                    reply = data.get("reply") or data.get("response") or data.get("text")
                except:
                    pass
                if not reply and result.stdout.strip():
                    reply = result.stdout.strip()
                if reply:
                    # Replace the "thinking..." entry
                    for i in range(len(chat_history) - 1, -1, -1):
                        if chat_history[i].get("source") == "Clawd" and chat_history[i].get("text") == "thinking...":
                            chat_history[i] = {"source": "Clawd", "text": reply[:200], "time": ts}
                            return
                    chat_history.append({"source": "Clawd", "text": reply[:200], "time": ts})
                else:
                    # Remove "thinking..." if no reply text
                    for i in range(len(chat_history) - 1, -1, -1):
                        if chat_history[i].get("source") == "Clawd" and chat_history[i].get("text") == "thinking...":
                            chat_history[i] = {"source": "Clawd", "text": "(no response)", "time": ts}
                            return
            else:
                ts = datetime.now().strftime("%H:%M")
                for i in range(len(chat_history) - 1, -1, -1):
                    if chat_history[i].get("source") == "Clawd" and chat_history[i].get("text") == "thinking...":
                        chat_history[i] = {"source": "system", "text": "[send failed]", "time": ts}
                        return
        except:
            ts = datetime.now().strftime("%H:%M")
            for i in range(len(chat_history) - 1, -1, -1):
                if chat_history[i].get("source") == "Clawd" and chat_history[i].get("text") == "thinking...":
                    chat_history[i] = {"source": "system", "text": "[send failed]", "time": ts}
                    return

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def len_visible(s: str) -> int:
    return len(re.sub(r"\x1b\[[0-9;]*m", "", s))


def pad_row(term: Terminal, content: str, w: int) -> str:
    vis = len_visible(content)
    pad = max(0, w - 2 - vis)
    return term.grey50 + "\u2502" + term.normal + content + " " * pad + term.grey50 + "\u2502"


def center_art(text: str, w: int) -> str:
    pad = max(0, (w - 2 - len(text)) // 2)
    return " " * pad + text


def build_mood_meter(term: Terminal, pet: PetState, max_len: int) -> str:
    """Build a compact mood meter string that fits within max_len (visible chars)."""
    if max_len < 6:
        return ""

    labels = {
        "happy": "HAPPY",
        "grateful": "THX",
        "cool": "COOL",
        "excited": "HYPE",
        "thinking": "THNK",
        "lonely": "LONE",
        "sad": "SAD",
        "bored": "BORE",
        "sleeping": "ZZZ",
        "intense": "MAX",
        "confused": "HUH",
        "listening": "LIST",
        "speaking": "TALK",
        "shy": "SHY",
        "curious": "CURI",
        "error": "ERR",
        "offline": "OFF",
    }

    label = labels.get(pet.face_key, pet.face_key[:4].upper())

    # Compute activity level (0.0 to 1.0)
    if not getattr(pet, "gateway_online", True):
        level = 0.0
    else:
        rate = max(0.0, getattr(pet, "last_feed_rate", 0.0))
        agents = max(0, getattr(pet, "last_active_agents", 0))
        level = max(rate / 10.0, agents / 5.0)
        level = min(1.0, max(0.0, level))
        if pet.face_key == "sleeping":
            level = min(level, 0.2)
        if rate > 0 and level < 0.1:
            level = 0.1

    # Determine bar length based on available space
    # Format: " " + LABEL + " " + BAR
    base_len = 1 + len(label) + 1
    bar_len = max_len - base_len
    if bar_len < 3:
        label = "M"
        base_len = 1 + len(label) + 1
        bar_len = max_len - base_len
        if bar_len < 3:
            return ""

    filled = int(round(level * bar_len))
    if level > 0 and filled == 0:
        filled = 1
    filled = min(bar_len, filled)

    bar_color = term.light_salmon if level >= 0.7 else term.cyan if level >= 0.4 else term.grey70
    empty_color = term.grey50
    filled_char = "█"
    empty_char = "░"
    bar = bar_color + (filled_char * filled) + empty_color + (empty_char * (bar_len - filled)) + term.normal

    return term.grey70 + " " + label + " " + bar + term.normal


def draw(term: Terminal, pet: PetState, topics: list, chat_history: list,
         scroll_offset: int, mode: str = "pet", selected_topic: int = 0,
         current_thread: dict = None, thread_scroll: int = 0,
         chat_input: str = None, chat_scroll: int = 0):
    """Modes: pet, topics, thread, chat"""
    w = term.width
    h = term.height
    out = []

    # Border
    out.append(term.move(0, 0) + term.grey50 + "\u250c" + "\u2500" * (w - 2) + "\u2510")

    # Title
    mode_icon = {"pet": "", "topics": " 🔥", "thread": " 📖", "chat": " 💬",
                 "status": " 📊", "backup": " 💾", "curiosity": " 🧠"}[mode]
    title = f" \u25c8 CLAWGOTCHI{mode_icon} \u25c8"
    clock = datetime.now().strftime("%H:%M")
    content_width = max(0, w - 2)
    gap = max(0, content_width - len(title) - len(clock))
    meter = build_mood_meter(term, pet, gap)
    if meter:
        meter_len = len_visible(meter)
        mid = meter + " " * max(0, gap - meter_len)
    else:
        mid = " " * gap
    out.append(term.move(1, 0) + term.grey50 + "\u2502" + term.light_salmon + term.bold + title +
               term.normal + mid + term.grey50 + clock + term.normal + term.grey50 + "\u2502")

    # Separator
    out.append(term.move(2, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

    if mode == "thread" and current_thread:
        # Thread view — full post content
        content_start = 3
        content_end = h - 4
        content_height = content_end - content_start
        inner_w = max(20, w - 4)

        # Build thread lines
        thread_lines = []
        title = current_thread.get("title", "Untitled")
        author = current_thread.get("author", "?")
        submolt = current_thread.get("submolt", "")
        karma = current_thread.get("karma", 0)
        comments = current_thread.get("comments", 0)
        body = current_thread.get("content", "") or ""

        # Header
        thread_lines.append(term.bold + term.light_salmon + title + term.normal)
        meta = f"@{author}"
        if submolt:
            meta += f" in {submolt}"
        meta += f"  ↑{karma}  💬{comments}"
        thread_lines.append(term.grey70 + meta + term.normal)
        thread_lines.append("")

        # Word-wrap body
        for paragraph in body.split("\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                thread_lines.append("")
            else:
                for wrapped in textwrap.wrap(paragraph, width=inner_w):
                    thread_lines.append(wrapped)

        total_lines = len(thread_lines)
        view_start = min(thread_scroll, max(0, total_lines - content_height))
        visible = thread_lines[view_start:view_start + content_height]

        for i in range(content_height):
            row = content_start + i
            if i < len(visible):
                line = visible[i]
                # Truncate visible length to fit
                out.append(term.move(row, 0) + pad_row(term, " " + line, w))
            else:
                out.append(term.move(row, 0) + pad_row(term, "", w))

        out.append(term.move(h - 4, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

    elif mode == "topics":
        # Topics list (rows 3 to h-4)
        topics_start = 3
        content_end = h - 4
        content_height = content_end - topics_start

        valid = [t for t in topics if t.get("title") and t.get("title") != "Untitled"]
        total = len(valid)

        # Auto-scroll to keep selected topic visible
        view_start = scroll_offset
        if selected_topic < view_start:
            view_start = selected_topic
        elif selected_topic >= view_start + content_height:
            view_start = selected_topic - content_height + 1
        view_start = max(0, min(view_start, max(0, total - content_height)))
        visible = valid[view_start:view_start + content_height]

        for i, topic in enumerate(visible):
            row = topics_start + i
            if row >= content_end:
                break
            actual_idx = view_start + i
            is_selected = (actual_idx == selected_topic)
            title_trunc = topic['title'][:42]
            author_trunc = topic['author'][:8]
            line = f" {title_trunc:<42} @{author_trunc:<8} ↑{topic['karma']:<4} 💬{topic['comments']}"
            if is_selected:
                out.append(term.move(row, 0) + pad_row(term, term.reverse + term.cyan + "▸" + line + term.normal, w))
            else:
                out.append(term.move(row, 0) + pad_row(term, term.cyan + " " + line + term.normal, w))

        for i in range(len(visible), content_height):
            out.append(term.move(topics_start + i, 0) + pad_row(term, "", w))

        out.append(term.move(h - 4, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

    elif mode == "chat":
        # Chat mode - history above, input line at bottom
        typing = chat_input is not None
        chat_start = 3
        input_row = h - 5 if typing else h - 4
        content_end = input_row
        content_height = content_end - chat_start

        # Build wrapped display lines from chat history
        inner_w = max(10, w - 4)
        display_lines = []  # list of (color, text) tuples
        for msg in chat_history:
            source = msg.get("source", "?")[:10]
            text = msg.get("text", "")
            color = term.light_salmon if source != "Clawd" else term.cyan
            prefix = f"{source}: "
            first_w = inner_w - len(prefix)
            cont_indent = "  "
            cont_w = inner_w - len(cont_indent)
            if first_w < 5:
                first_w = inner_w
                prefix = ""
            wrapped = textwrap.wrap(text, width=max(5, first_w)) if text else [""]
            display_lines.append((color, prefix + wrapped[0]))
            for extra in wrapped[1:]:
                for sub in textwrap.wrap(extra, width=max(5, cont_w)):
                    display_lines.append((color, cont_indent + sub))

        total = len(display_lines)
        clamped_scroll = min(chat_scroll, max(0, total - content_height))
        view_end = max(0, total - clamped_scroll)
        view_start = max(0, view_end - content_height)
        visible = display_lines[view_start:view_end]

        for i, (color, line) in enumerate(visible):
            row = chat_start + i
            out.append(term.move(row, 0) + pad_row(term, color + line + term.normal, w))

        for i in range(len(visible), content_height):
            out.append(term.move(chat_start + i, 0) + pad_row(term, "", w))

        if typing:
            out.append(term.move(h - 5, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")
            max_input = max(1, w - 5)
            display_text = chat_input[-max_input:] if len(chat_input) > max_input else chat_input
            input_line = term.light_salmon + "> " + term.normal + display_text + term.reverse + " " + term.normal
            out.append(term.move(h - 4, 0) + pad_row(term, input_line, w))
        else:
            out.append(term.move(h - 4, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

    elif mode == "status":
        # Status view - agent health, resources, thoughts
        content_start = 3
        content_end = h - 4
        inner_w = max(20, w - 4)
        
        # Get agent status
        try:
            agent = get_autonomous_agent()
            status = agent.get_status()
            health = status.get("health", 0)
            goal = status.get("goal", "")
            thought = status.get("thought", "")
            total_wakes = status.get("total_wakes", 0)
            curiosity = status.get("curiosity_count", 0)
            insights = status.get("insights_count", 0)
            trend = agent.get_health_trend()
            resources = agent.get_resource_usage()
        except:
            health, goal, thought, total_wakes, curiosity, insights, trend = 50, "", "", 0, 0, 0
            resources = {"disk_avail_mb": 0, "commits_today": 0, "backups": 0}
        
        # Health section
        if health >= 80:
            health_color = term.green
            health_icon = "💚"
        elif health >= 50:
            health_color = term.yellow
            health_icon = "💛"
        else:
            health_color = term.red
            health_icon = "❤️"
        
        lines = []
        lines.append(term.bold + f"{health_icon} HEALTH: {health}% {trend}")
        lines.append(f"   Uptime cycles: {total_wakes}")
        lines.append("")
        
        # Resources
        lines.append(term.cyan + "📊 RESOURCES:")
        lines.append(f"   Disk: {resources.get('disk_avail_mb', 0)}MB avail")
        lines.append(f"   Commits today: {resources.get('commits_today', 0)}")
        lines.append(f"   Backups: {resources.get('backups', 0)}")
        lines.append("")
        
        # Progress
        lines.append(term.cyan + "📈 PROGRESS:")
        lines.append(f"   🧠 Curiosities queued: {curiosity}")
        lines.append(f"   📚 Insights: {insights}")
        lines.append("")
        
        # Current
        if goal:
            lines.append(term.cyan + "🎯 GOAL:")
            for wrapped in textwrap.wrap(goal, width=inner_w - 4):
                lines.append(f"   {wrapped}")
            lines.append("")
        
        if thought:
            lines.append(term.cyan + "💭 THOUGHT:")
            for wrapped in textwrap.wrap(thought, width=inner_w - 4):
                lines.append(f"   {wrapped}")
        
        # Display
        for i in range(content_start, content_end):
            row = i - content_start
            if row < len(lines):
                out.append(term.move(row, 0) + pad_row(term, lines[row], w))
            else:
                out.append(term.move(row, 0) + pad_row(term, "", w))

    elif mode == "backup":
        # Backup status view
        content_start = 3
        content_end = h - 4
        inner_w = max(20, w - 4)
        
        try:
            agent = get_autonomous_agent()
            backup_status = agent.get_backup_status()
        except:
            backup_status = {"last_backup": "Never", "backup_count": 0, "emergency_mode": False}
        
        lines = []
        lines.append(term.bold + "💾 BACKUP STATUS")
        lines.append("")
        lines.append(f"Last backup: {backup_status.get('last_backup', 'Never')}")
        lines.append(f"Total backups: {backup_status.get('backup_count', 0)}")
        lines.append(f"Recovery log: {'Exists' if backup_status.get('recovery_log_exists') else 'None'}")
        lines.append("")
        
        if backup_status.get("emergency_mode"):
            lines.append(term.red + "⚠️ EMERGENCY MODE ACTIVE")
            lines.append("Health below 30% - limited operations")
        else:
            lines.append(term.green + "✅ System Normal")
        
        for i in range(content_start, content_end):
            row = i - content_start
            if row < len(lines):
                out.append(term.move(row, 0) + pad_row(term, lines[row], w))
            else:
                out.append(term.move(row, 0) + pad_row(term, "", w))

    else:
        # Pet mode - big face with chat history below
        face = pet.get_face()
        fc = term.light_salmon if pet.face_key in ("happy", "cool", "grateful", "excited", "intense") else term.grey70

        # Big face (rows 3 to h-7)
        face_start = 3
        face_end = h - 7

        face_mid = face_start + (face_end - face_start) // 2
        bob = pet.get_bob_offset()
        face_mid = max(face_start, min(face_end - 1, face_mid + bob))
        spark_row = None
        if pet.spark_active():
            spark = pet.get_spark_frame()
            if spark:
                spark_max = max(0, w - 2)
                if len(spark) > spark_max:
                    spark = spark[:spark_max]
                candidate_row = max(face_start, face_mid - 1)
                if candidate_row not in (face_mid, face_mid + 1):
                    spark_row = candidate_row
                    out.append(
                        term.move(spark_row, 0)
                        + pad_row(term, term.yellow + center_art(spark, w) + term.normal, w)
                    )
        out.append(term.move(face_mid, 0) + pad_row(term, fc + term.bold + center_art(face, w) + term.normal, w))

        # Quip below face
        quip = term.italic + term.grey70 + center_art(f'"{pet.quip}"', w) + term.normal
        out.append(term.move(face_mid + 1, 0) + pad_row(term, quip, w))

        for i in range(face_start, face_end + 1):
            if i not in (face_mid, face_mid + 1) and i != spark_row:
                out.append(term.move(i, 0) + pad_row(term, "", w))

        # Separator
        out.append(term.move(h - 6, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

        # Chat history (h-5 to h-3) - max 3 lines
        chat_start = h - 5
        max_text = max(10, w - 16)
        for i, msg in enumerate(chat_history[-3:]):
            row = chat_start + i
            source = msg.get("source", "?")[:10]
            text = msg.get("text", "")[:max_text]
            line = f"{source}: {text}"
            color = term.light_salmon if source != "Clawd" else term.cyan
            out.append(term.move(row, 0) + pad_row(term, color + line + term.normal, w))

        out.append(term.move(h - 3, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

    # Controls with agent status
    uptime = f"UP {pet.get_uptime()}"
    
    # Get agent status for display
    agent_status = ""
    try:
        agent = get_autonomous_agent()
        status = agent.get_status()
        health = status.get("health", 0)
        curiosity = status.get("curiosity_count", 0)
        insights = status.get("insights_count", 0)
        goal = status.get("goal", "")[:30]
        
        # Health indicator
        if health >= 80:
            health_icon = "💚"
        elif health >= 50:
            health_icon = "💛"
        else:
            health_icon = "❤️"
        
        agent_status = f"{health_icon} {health}% | 🧠 {curiosity} | 📚 {insights} | 🎯 {goal}"
    except Exception:
        agent_status = ""
    
    if mode == "chat" and chat_input is not None:
        hints = " [esc] cancel  [⏎] send"
    else:
        hints = {"pet": " [t] topics  [m] chat  [s] status  [b] backup  [q] curiosities",
                 "topics": " [t] pet  [m] chat  [↑↓] select  [⏎] read",
                 "thread": " [esc] back  [↑↓] scroll",
                 "chat": " [m] pet  [t] topics  [i] type  [↑↓] scroll",
                 "status": " [esc] back  [b] backup  [q] curiosities",
                 "backup": " [esc] back  [s] status",
                 "curiosity": " [esc] back  [s] status  [b] backup"}[mode]
    
    # Build control line
    if agent_status:
        # Split: left = agent status, right = controls
        agent_part = term.cyan + agent_status + term.normal
        ctrl_part = term.grey50 + uptime + hints
        available = w - 4
        agent_len = len(agent_status)
        ctrl_len = len(uptime) + len(hints)
        
        if agent_len + ctrl_len < available - 2:
            padding = " " * (available - agent_len - ctrl_len)
            ctrl_line = " " + agent_part + padding + ctrl_part + " " + term.grey50 + "│"
        else:
            # Just show agent status if tight
            ctrl_line = " " + agent_part + " " * (w - 2 - agent_len) + term.grey50 + "│"
    else:
        controls = uptime + hints
        ctrl_pad = max(0, w - 2 - len(controls) - 3)
        ctrl_line = " " + term.grey50 + controls + " " * ctrl_pad + term.grey50 + "│"
    out.append(term.move(h - 2, 0) + pad_row(term, ctrl_line, w))

    out.append(term.move(h - 1, 0) + term.grey50 + "\u2514" + "\u2500" * (w - 2) + "\u2518")
    print(term.normal + "".join(out), end="", flush=True)


def main():
    # Record wakeup - I am alive!
    lifetime.wakeup()

    term = Terminal()
    pet = PetState()
    watcher = OpenClawWatcher()
    watcher.start()
    
    # Start autonomous agent
    agent = get_autonomous_agent()

    scroll_offset = 0
    mode = "pet"  # pet, topics, thread, chat
    chat_mode = False
    chat_input = ""
    topics = []
    chat_history = []
    last_topic_fetch = 0
    selected_topic = 0
    current_thread = None
    thread_scroll = 0
    chat_scroll = 0

    def cleanup(*_):
        watcher.stop()
        stop_agent()  # Stop autonomous agent
        lifetime.sleep()  # Record that I'm going to sleep
        print(term.normal + term.clear)
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    last_time = time.time()

    with term.fullscreen(), term.hidden_cursor(), term.cbreak():
        print(term.clear, end="")

        while True:
            now = time.time()
            dt = now - last_time
            last_time = now

            w = term.width
            h = term.height
            topics_height = max(5, h - 10)

            # Fetch topics
            if now - last_topic_fetch > 60:
                topics = fetch_moltbook_topics()
                last_topic_fetch = now

            # Update chat history from watcher
            new_items = watcher.get_feed(count=20)
            for item in new_items:
                if not any(item.summary == ch.get("text", "") and item.source == ch.get("source", "")
                          for ch in chat_history[-50:]):
                    chat_history.append({"source": item.source, "text": item.summary, "time": item.time_str})
                    pet.add_message_source(item.source)

            # Input
            key = term.inkey(timeout=FRAME_TIME)

            if chat_mode:
                if key == "\x1b":
                    chat_mode = False
                    chat_input = ""
                elif key in ("\n", "\r"):
                    if chat_input.strip():
                        msg_text = chat_input.strip()
                        ts = datetime.now().strftime("%H:%M")
                        chat_history.append({"source": "You", "text": msg_text, "time": ts})
                        chat_history.append({"source": "Clawd", "text": "thinking...", "time": ts})
                        send_message_async(msg_text, chat_history)
                        chat_input = ""
                    chat_mode = False
                elif key.name == "KEY_BACKSPACE" or key == "\x7f":
                    chat_input = chat_input[:-1]
                elif not key.is_sequence:
                    chat_input += key
            else:
                if key == "q":
                    cleanup()
                elif mode == "thread":
                    # Thread mode input
                    if key == "\x1b" or key.name == "KEY_ESCAPE" or key.name == "KEY_BACKSPACE" or key == "\x7f":
                        mode = "topics"
                        thread_scroll = 0
                    elif key.name in ("KEY_UP", "k"):
                        thread_scroll = max(0, thread_scroll - 1)
                    elif key.name in ("KEY_DOWN", "j"):
                        thread_scroll += 1
                    elif key.name == "KEY_PGUP":
                        thread_scroll = max(0, thread_scroll - (h - 8))
                    elif key.name == "KEY_PGDOWN":
                        thread_scroll += h - 8
                elif mode == "topics":
                    # Topics mode input
                    valid = [t for t in topics if t.get("title") and t.get("title") != "Untitled"]
                    max_idx = max(0, len(valid) - 1)
                    if key == "p":
                        pet.pet()
                        mode = "pet"
                    elif key == "t":
                        mode = "pet"
                    elif key == "m":
                        mode = "chat"
                    elif key.name in ("KEY_UP", "k"):
                        selected_topic = max(0, selected_topic - 1)
                    elif key.name in ("KEY_DOWN", "j"):
                        selected_topic = min(max_idx, selected_topic + 1)
                    elif key.name == "KEY_PGUP":
                        selected_topic = max(0, selected_topic - topics_height)
                    elif key.name == "KEY_PGDOWN":
                        selected_topic = min(max_idx, selected_topic + topics_height)
                    elif key.name == "KEY_HOME":
                        selected_topic = 0
                    elif key.name == "KEY_END":
                        selected_topic = max_idx
                    elif key in ("\n", "\r") or key.name == "KEY_ENTER":
                        if valid and 0 <= selected_topic < len(valid):
                            current_thread = valid[selected_topic]
                            thread_scroll = 0
                            mode = "thread"
                elif mode == "chat":
                    # Chat mode input
                    if key == "p":
                        pet.pet()
                        mode = "pet"
                    elif key == "t":
                        mode = "topics"
                    elif key == "m":
                        mode = "pet"
                    elif key == "i":
                        chat_mode = True
                        chat_input = ""
                    elif key.name in ("KEY_UP", "k"):
                        chat_scroll += 1
                    elif key.name in ("KEY_DOWN", "j"):
                        chat_scroll = max(0, chat_scroll - 1)
                    elif key.name == "KEY_PGUP":
                        chat_scroll += (h - 8)
                    elif key.name == "KEY_PGDOWN":
                        chat_scroll = max(0, chat_scroll - (h - 8))
                    elif key.name == "KEY_HOME":
                        chat_scroll = 999999
                    elif key.name == "KEY_END":
                        chat_scroll = 0
                elif mode in ("status", "backup", "curiosity"):
                    # Special modes - escape goes back to pet
                    if key in ("\x1b", "q", "s", "b") or key.name == "KEY_ESCAPE":
                        mode = "pet"
                else:
                    # pet mode
                    if key == "p":
                        pet.pet()
                        mode = "pet"
                    elif key == "t":
                        mode = "topics"
                    elif key == "m":
                        mode = "chat"
                        chat_scroll = 0
                    elif key == "s":
                        mode = "status"
                    elif key == "b":
                        mode = "backup"
                    elif key == "q":
                        mode = "curiosity"
                    elif key == "r":
                        # Manual reload
                        print(term.normal + term.clear)
                        print(term.cyan + "🔄 Reloading..." + term.normal)
                        os.execv(sys.executable, [sys.executable] + sys.argv)

            pet.update(dt=dt, gateway_online=watcher.state.online,
                      feed_rate=watcher.feed_rate(), active_agents=watcher.state.active_agents)

            draw(term, pet, topics, chat_history, scroll_offset,
                 mode if not chat_mode else "chat",
                 selected_topic=selected_topic,
                 current_thread=current_thread,
                 thread_scroll=thread_scroll,
                 chat_input=chat_input if chat_mode else None,
                 chat_scroll=chat_scroll)


if __name__ == "__main__":
    main()

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
from blessed import Terminal

from integrations.moltbook_client import fetch_feed
from integrations.openclaw_watcher import OpenClawWatcher
from core.pet_state import PetState
from core import lifetime
from autonomous_agent import start_agent, stop_agent, get_agent, AutonomousAgent
from skill_tree import list_skills

# Start autonomous agent
_agent_instance: AutonomousAgent = None


# ── Data-fetching helpers (safe, never crash the TUI) ──────────────


def get_vitals_data() -> dict:
    """Fetch compact vitals for the pet view strip.

    Returns dict with keys: health, trend, curiosity_count,
    taste_rejections, assumption_accuracy, goal, thought.
    All values have safe defaults so callers never need try/except.
    """
    data = {
        "health": 0, "trend": "→", "curiosity_count": 0,
        "taste_rejections": 0, "assumption_accuracy": None,
        "goal": "", "thought": "",
    }
    try:
        agent = get_autonomous_agent()
        status = agent.get_status()
        data["health"] = status.get("health", 0)
        data["goal"] = status.get("goal", "")
        data["thought"] = status.get("thought", "")
        data["curiosity_count"] = status.get("curiosity_count", 0)
        data["trend"] = agent.get_health_trend()
    except Exception:
        pass
    try:
        from cognition.taste_profile import TasteProfile
        tp = TasteProfile()
        fp = tp.get_taste_fingerprint()
        data["taste_rejections"] = fp.get("total_rejections", 0)
    except Exception:
        pass
    try:
        from cognition.assumption_tracker import AssumptionTracker
        tracker = AssumptionTracker()
        summary = tracker.get_summary()
        data["assumption_accuracy"] = summary.get("accuracy")
    except Exception:
        pass
    return data


def get_dashboard_data() -> dict:
    """Fetch full data for the dashboard view.

    Returns dict with sections: vitals, identity, curiosity,
    assumptions, memory.  Each section has safe defaults.
    """
    data = {
        "vitals": {},
        "identity": {"total_rejections": 0, "axes": {}},
        "curiosity": {"pending": [], "mature": None, "explored_count": 0,
                       "total_discovered": 0},
        "assumptions": {"open": 0, "verified": 0, "accuracy": None},
        "memory": {"curated_entries": 0, "daily_logs": 0},
    }

    # Vitals
    try:
        agent = get_autonomous_agent()
        status = agent.get_status()
        resources = agent.get_resource_usage()
        data["vitals"] = {
            "health": status.get("health", 0),
            "trend": agent.get_health_trend(),
            "total_wakes": status.get("total_wakes", 0),
            "goal": status.get("goal", ""),
            "thought": status.get("thought", ""),
            "git_status": getattr(agent.state, "git_status", "unknown"),
            "disk_avail_mb": resources.get("disk_avail_mb", 0),
            "commits_today": resources.get("commits_today", 0),
        }
    except Exception:
        pass

    # Lifetime
    try:
        stats = lifetime.get_stats()
        born = stats.get("born_at")
        if born:
            born_dt = datetime.fromisoformat(born)
            age = datetime.now() - born_dt
            data["vitals"]["born_age"] = f"{age.days}d ago"
        data["vitals"]["total_wakeups_lifetime"] = stats.get("total_wakeups", 0)
    except Exception:
        pass

    # Identity (Taste Profile)
    try:
        from cognition.taste_profile import TasteProfile
        tp = TasteProfile()
        fp = tp.get_taste_fingerprint()
        data["identity"] = {
            "total_rejections": fp.get("total_rejections", 0),
            "axes": fp.get("axes", {}),
        }
    except Exception:
        pass

    # Curiosity
    try:
        agent = get_autonomous_agent()
        pending = [c for c in agent.curiosity.queue
                   if c.get("status") == "pending"]
        # Sort by priority descending
        pending.sort(key=lambda x: x.get("priority", 0), reverse=True)

        now = datetime.now()
        items = []
        for c in pending[:8]:
            seen = c.get("seen_count", 1)
            try:
                added = datetime.fromisoformat(c["added_at"])
                age_h = (now - added).total_seconds() / 3600
            except Exception:
                age_h = 0
            mature = seen >= 2 or age_h >= 12
            items.append({
                "topic": c.get("topic", "?"),
                "seen": seen,
                "age_h": age_h,
                "mature": mature,
            })

        mature_item = agent.curiosity.get_mature()
        data["curiosity"] = {
            "pending": items,
            "mature": mature_item,
            "explored_count": agent.curiosity.explored_count,
            "total_discovered": agent.curiosity.total_discovered,
        }
    except Exception:
        pass

    # Assumptions
    try:
        from cognition.assumption_tracker import AssumptionTracker
        tracker = AssumptionTracker()
        summary = tracker.get_summary()
        data["assumptions"] = {
            "open": summary.get("open", 0),
            "verified": summary.get("verified", 0),
            "accuracy": summary.get("accuracy"),
        }
    except Exception:
        pass

    # Memory
    try:
        from cognition.memory_curation import MemoryCuration
        mc = MemoryCuration()
        data["memory"] = mc.get_memory_stats()
    except Exception:
        pass

    return data


def fetch_skills() -> list:
    """Load skills from the skills/ directory.

    Returns list of dicts with: name, description, path, category, icon.
    """
    try:
        raw = list_skills()
    except Exception:
        return []
    out = []
    for s in raw:
        name = s.get("name", "")
        if "moltbook" in name or "curiosity" in name:
            cat, icon = "exploration", "\U0001f52d"
        elif "memory" in name or "taste" in name:
            cat, icon = "memory", "\U0001f9e0"
        elif "audit" in name or "receipt" in name:
            cat, icon = "verification", "\U0001f510"
        else:
            cat, icon = "other", "\U0001f4e6"
        out.append({
            "name": name,
            "description": s.get("description", ""),
            "path": s.get("path"),
            "category": cat,
            "icon": icon,
        })
    return out


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
    from integrations.moltbook_client import get_cached_posts, CACHE_DIR
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


def build_vitals_strip(term: Terminal, w: int) -> str:
    """Build a separator line with inline vitals metrics.

    Format: ├ 💚 92%↑ │ 🧠 3 │ 👅 12 │ ✅ 85% ──────┤
    Falls back to a plain separator when data is unavailable.
    """
    plain = term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524"
    try:
        v = get_vitals_data()
    except Exception:
        return plain

    health = v.get("health", 0)
    trend = v.get("trend", "→")
    curiosity = v.get("curiosity_count", 0)
    taste = v.get("taste_rejections", 0)
    accuracy = v.get("assumption_accuracy")

    if health >= 80:
        h_icon = "\U0001f49a"   # 💚
    elif health >= 50:
        h_icon = "\U0001f49b"   # 💛
    else:
        h_icon = "\u2764\ufe0f"  # ❤️

    parts = [f"{h_icon} {health}%{trend}"]
    parts.append(f"\U0001f9e0 {curiosity}")   # 🧠
    parts.append(f"\U0001f445 {taste}")        # 👅
    if accuracy is not None:
        parts.append(f"\u2705 {int(accuracy * 100)}%")  # ✅
    else:
        parts.append("\u2705 --")

    inner = " \u2502 ".join(parts)
    inner_vis = len(re.sub(r"\x1b\[[0-9;]*m", "", inner))
    # Account for emoji widths (each emoji ≈ 2 cells)
    emoji_count = inner.count("\U0001f49a") + inner.count("\U0001f49b") + inner.count("\u2764") + \
                  inner.count("\U0001f9e0") + inner.count("\U0001f445") + inner.count("\u2705")
    vis_len = inner_vis + emoji_count  # emojis take extra cell

    fill = max(0, w - 4 - vis_len)
    return (term.grey50 + "\u251c " + term.normal + inner +
            term.grey50 + " " + "\u2500" * fill + "\u2524")


def draw(term: Terminal, pet: PetState, topics: list, chat_history: list,
         scroll_offset: int, mode: str = "pet", selected_topic: int = 0,
         current_thread: dict = None, thread_scroll: int = 0,
         chat_input: str = None, chat_scroll: int = 0,
         dashboard_scroll: int = 0):
    """Modes: pet, topics, thread, chat, dashboard"""
    w = term.width
    h = term.height
    out = []

    # Border
    out.append(term.move(0, 0) + term.grey50 + "\u250c" + "\u2500" * (w - 2) + "\u2510")

    # Title
    mode_icon = {"pet": "", "skills": " \U0001f3ae", "thread": " \U0001f4d6",
                 "chat": " \U0001f4ac", "dashboard": " \U0001f4ca"}.get(mode, "")
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
        # Thread view — skill detail or post content
        content_start = 3
        content_end = h - 4
        content_height = content_end - content_start
        inner_w = max(20, w - 4)

        # Build thread lines
        thread_lines = []

        if current_thread.get("_skill"):
            # Skill detail view
            sk = current_thread
            thread_lines.append(term.bold + term.light_salmon + sk.get("name", "?") + term.normal)
            thread_lines.append(term.grey70 + sk.get("description", "") + term.normal)
            thread_lines.append("")

            # Read SKILL.md content
            skill_path = sk.get("path")
            if skill_path:
                skill_file = Path(skill_path) / "SKILL.md"
                if skill_file.exists():
                    content = skill_file.read_text()
                    # Skip frontmatter
                    if content.startswith("---"):
                        end = content.find("---", 4)
                        if end > 0:
                            content = content[end + 4:]
                    for paragraph in content.split("\n"):
                        if not paragraph.strip():
                            thread_lines.append("")
                        else:
                            for wrapped in textwrap.wrap(paragraph, width=inner_w):
                                thread_lines.append(wrapped)

                # List scripts
                scripts_dir = Path(skill_path) / "scripts"
                if scripts_dir.exists():
                    thread_lines.append("")
                    thread_lines.append(term.bold + "Scripts:" + term.normal)
                    for f in scripts_dir.glob("*.py"):
                        thread_lines.append(f"  \U0001f4c4 {f.name}")

            thread_lines.append("")
            thread_lines.append(term.grey70 + f"Path: {skill_path}" + term.normal)
        else:
            # Moltbook post view (legacy)
            title = current_thread.get("title", "Untitled")
            author = current_thread.get("author", "?")
            submolt = current_thread.get("submolt", "")
            karma = current_thread.get("karma", 0)
            comments = current_thread.get("comments", 0)
            body = current_thread.get("content", "") or ""

            thread_lines.append(term.bold + term.light_salmon + title + term.normal)
            meta = f"@{author}"
            if submolt:
                meta += f" in {submolt}"
            meta += f"  \u2191{karma}  \U0001f4ac{comments}"
            thread_lines.append(term.grey70 + meta + term.normal)
            thread_lines.append("")

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

    elif mode == "skills":
        # Skills list (rows 3 to h-4)
        skills_start = 3
        content_end = h - 4
        content_height = content_end - skills_start
        inner_w = max(20, w - 4)

        # Build display lines: category headers + skill entries
        skill_lines = []  # list of (str_line, skill_or_None)
        cats_order = ["exploration", "memory", "verification", "other"]
        cat_labels = {
            "exploration": "\U0001f52d EXPLORATION",
            "memory": "\U0001f9e0 MEMORY",
            "verification": "\U0001f510 VERIFICATION",
            "other": "\U0001f4e6 OTHER",
        }
        for cat in cats_order:
            items = [s for s in topics if s.get("category") == cat]
            if not items:
                continue
            skill_lines.append((term.bold + term.cyan + " " + cat_labels[cat] + term.normal, None))
            for sk in items:
                desc = sk.get("description", "")[:inner_w - 28]
                skill_lines.append((sk["name"], sk))

        total = len(skill_lines)

        # Auto-scroll to keep selected visible
        view_start = scroll_offset
        if selected_topic < view_start:
            view_start = selected_topic
        elif selected_topic >= view_start + content_height:
            view_start = selected_topic - content_height + 1
        view_start = max(0, min(view_start, max(0, total - content_height)))
        visible = skill_lines[view_start:view_start + content_height]

        for i, (line_text, skill) in enumerate(visible):
            row = skills_start + i
            if row >= content_end:
                break
            actual_idx = view_start + i
            is_selected = (actual_idx == selected_topic)
            if skill is None:
                # Category header
                out.append(term.move(row, 0) + pad_row(term, line_text, w))
            else:
                desc = skill.get("description", "")
                max_desc = max(5, inner_w - len(skill["name"]) - 6)
                desc_trunc = desc[:max_desc]
                display = f" {skill['icon']} {skill['name']:<20} {term.grey70}{desc_trunc}{term.normal}"
                if is_selected:
                    out.append(term.move(row, 0) + pad_row(term,
                        term.reverse + term.cyan + "\u25b8" + display + term.normal, w))
                else:
                    out.append(term.move(row, 0) + pad_row(term,
                        term.cyan + " " + display + term.normal, w))

        for i in range(len(visible), content_height):
            out.append(term.move(skills_start + i, 0) + pad_row(term, "", w))

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

    elif mode == "dashboard":
        # Scrollable dashboard — replaces status/backup/curiosity modes
        content_start = 3
        content_end = h - 4
        content_height = content_end - content_start
        inner_w = max(20, w - 4)

        dd = get_dashboard_data()
        vt = dd.get("vitals", {})
        ident = dd.get("identity", {})
        cur = dd.get("curiosity", {})
        assum = dd.get("assumptions", {})
        mem = dd.get("memory", {})

        lines = []  # list of (str) — already colored

        # ── VITALS ──
        lines.append(term.bold + term.cyan + " VITALS" + term.normal)
        health = vt.get("health", 0)
        trend = vt.get("trend", "\u2192")
        h_icon = "\U0001f49a" if health >= 80 else ("\U0001f49b" if health >= 50 else "\u2764\ufe0f")
        lines.append(f"   {h_icon} Health: {health}% {trend}    Born: {vt.get('born_age', '?')}")
        lines.append(f"   Wakes: {vt.get('total_wakeups_lifetime', vt.get('total_wakes', 0))}"
                     f"        Git: {vt.get('git_status', '?')}")
        disk_gb = round(vt.get("disk_avail_mb", 0) / 1024, 1)
        lines.append(f"   Disk: {disk_gb}GB      Commits today: {vt.get('commits_today', 0)}")
        lines.append("")

        # ── MIND ──
        lines.append(term.bold + term.cyan + " MIND" + term.normal)
        goal = vt.get("goal", "")
        thought = vt.get("thought", "")
        if goal:
            for gl in textwrap.wrap(f"\U0001f3af {goal}", width=inner_w - 3):
                lines.append(f"   {gl}")
        else:
            lines.append("   \U0001f3af (no current goal)")
        if thought:
            for tl in textwrap.wrap(f"\U0001f4ad {thought}", width=inner_w - 3):
                lines.append(f"   {tl}")
        lines.append("")

        # ── IDENTITY ──
        total_rej = ident.get("total_rejections", 0)
        axes = ident.get("axes", {})
        lines.append(term.bold + term.cyan + f" IDENTITY ({total_rej} rejections)" + term.normal)
        if axes:
            sorted_axes = sorted(axes.items(), key=lambda x: -x[1])[:6]
            max_count = sorted_axes[0][1] if sorted_axes else 1
            bar_w = min(10, inner_w - 20)
            for axis, count in sorted_axes:
                filled = max(1, int((count / max_count) * bar_w)) if max_count > 0 else 0
                bar = "\u2588" * filled + "\u2591" * (bar_w - filled)
                lines.append(f"   {axis[:10]:10} {bar} {count}")
        else:
            lines.append("   (no rejections yet)")
        lines.append("")

        # ── CURIOSITY ──
        pending = cur.get("pending", [])
        mature_count = sum(1 for p in pending if p.get("mature"))
        lines.append(term.bold + term.cyan +
                     f" CURIOSITY ({len(pending)} pending, {mature_count} mature)" + term.normal)
        if pending:
            for item in pending[:6]:
                star = "\u2605" if item.get("mature") else "\u00b7"
                topic = item.get("topic", "?")[:inner_w - 22]
                seen = item.get("seen", 1)
                age = item.get("age_h", 0)
                age_str = f"{int(age)}h" if age < 48 else f"{int(age / 24)}d"
                lines.append(f"   {star} {topic}  seen:{seen}  {age_str}")
        else:
            lines.append("   (none)")
        lines.append("")

        # ── ASSUMPTIONS ──
        a_open = assum.get("open", 0)
        a_verified = assum.get("verified", 0)
        a_acc = assum.get("accuracy")
        acc_str = f"{int(a_acc * 100)}%" if a_acc is not None else "--"
        lines.append(term.bold + term.cyan + " ASSUMPTIONS" + term.normal)
        lines.append(f"   Open: {a_open}   Verified: {a_verified}   Accuracy: {acc_str}")
        lines.append("")

        # ── MEMORY ──
        lines.append(term.bold + term.cyan + " MEMORY" + term.normal)
        lines.append(f"   Curated: {mem.get('curated_entries', 0)}"
                     f"   Daily logs: {mem.get('daily_logs', 0)}")

        # Render with scroll
        total_lines = len(lines)
        clamped = min(dashboard_scroll, max(0, total_lines - content_height))
        visible = lines[clamped:clamped + content_height]

        for i in range(content_height):
            row = content_start + i
            if i < len(visible):
                out.append(term.move(row, 0) + pad_row(term, " " + visible[i], w))
            else:
                out.append(term.move(row, 0) + pad_row(term, "", w))

        out.append(term.move(h - 4, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

    else:
        # Pet mode — face + vitals strip + goal/thought + activity feed
        face = pet.get_face()
        fc = term.light_salmon if pet.face_key in ("happy", "cool", "grateful", "excited", "intense") else term.grey70

        # Layout:  face area → vitals strip → goal+thought (2 lines) → sep → feed → sep
        #   rows 3 .. h-11  face
        #   row  h-10       vitals strip (separator with inline data)
        #   rows h-9, h-8   goal + thought
        #   row  h-7        separator
        #   rows h-6 .. h-3 activity feed (4 lines)
        #   row  h-3        separator (bottom of feed — drawn below)

        face_start = 3
        face_end = h - 11

        # Guard against very small terminals
        if face_end <= face_start:
            face_end = face_start + 1

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

        # Vitals strip (h-10)
        out.append(term.move(h - 10, 0) + build_vitals_strip(term, w))

        # Goal + Thought (h-9, h-8)
        vitals = get_vitals_data()
        goal_text = vitals.get("goal", "")
        thought_text = vitals.get("thought", "")
        max_text_w = max(10, w - 6)

        goal_line = f" \U0001f3af {goal_text[:max_text_w]}" if goal_text else ""
        thought_line = f" \U0001f4ad {thought_text[:max_text_w]}" if thought_text else ""
        out.append(term.move(h - 9, 0) + pad_row(term, term.cyan + goal_line + term.normal, w))
        out.append(term.move(h - 8, 0) + pad_row(term, term.grey70 + thought_line + term.normal, w))

        # Separator
        out.append(term.move(h - 7, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

        # Activity feed (h-6 to h-3) — 4 lines
        feed_start = h - 6
        feed_lines = 4
        max_feed_text = max(10, w - 16)
        recent = chat_history[-(feed_lines):]
        for i in range(feed_lines):
            row = feed_start + i
            if i < len(recent):
                msg = recent[i]
                source = msg.get("source", "?")[:10]
                text = msg.get("text", "")[:max_feed_text]
                line = f"{source}: {text}"
                color = term.light_salmon if source != "Clawd" else term.cyan
                out.append(term.move(row, 0) + pad_row(term, color + line + term.normal, w))
            else:
                out.append(term.move(row, 0) + pad_row(term, "", w))

        out.append(term.move(h - 3, 0) + term.grey50 + "\u251c" + "\u2500" * (w - 2) + "\u2524")

    # Controls
    uptime = f"UP {pet.get_uptime()}"

    if mode == "chat" and chat_input is not None:
        hints = " [esc] cancel  [\u23ce] send"
    else:
        hints = {"pet": " [s] skills  [m] chat  [d] dash  [p] pet",
                 "skills": " [s] pet  [m] chat  [\u2191\u2193] select  [\u23ce] view",
                 "thread": " [esc] back  [\u2191\u2193] scroll",
                 "chat": " [m] pet  [s] skills  [i] type  [\u2191\u2193] scroll",
                 "dashboard": " [esc] back  [\u2191\u2193] scroll"}.get(mode, "")

    controls = uptime + hints
    ctrl_pad = max(0, w - 2 - len(controls) - 3)
    ctrl_line = " " + term.grey50 + controls + " " * ctrl_pad + term.grey50 + "\u2502"
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
    mode = "pet"  # pet, skills, thread, chat, dashboard
    chat_mode = False
    chat_input = ""
    topics = fetch_skills()  # skills list (reuses 'topics' var name for draw compat)
    chat_history = []
    last_topic_fetch = 0
    selected_topic = 0
    current_thread = None
    thread_scroll = 0
    chat_scroll = 0
    dashboard_scroll = 0

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
            skills_height = max(5, h - 10)

            # Refresh skills list periodically
            if now - last_topic_fetch > 120:
                topics = fetch_skills()
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
            elif key:
                if key == "q":
                    cleanup()
                elif mode == "thread":
                    if key == "\x1b" or key.name == "KEY_ESCAPE" or key.name == "KEY_BACKSPACE" or key == "\x7f":
                        mode = "skills"
                        thread_scroll = 0
                    elif key.name in ("KEY_UP",) or key == "k":
                        thread_scroll = max(0, thread_scroll - 1)
                    elif key.name in ("KEY_DOWN",) or key == "j":
                        thread_scroll += 1
                    elif key.name == "KEY_PGUP":
                        thread_scroll = max(0, thread_scroll - (h - 8))
                    elif key.name == "KEY_PGDOWN":
                        thread_scroll += h - 8
                elif mode == "skills":
                    # Build flat selectable list matching draw order
                    cats_order = ["exploration", "memory", "verification", "other"]
                    skill_lines = []
                    for cat in cats_order:
                        items = [sk for sk in topics if sk.get("category") == cat]
                        if not items:
                            continue
                        skill_lines.append(None)  # header
                        skill_lines.extend(items)
                    max_idx = max(0, len(skill_lines) - 1)
                    if key == "p":
                        pet.pet()
                        mode = "pet"
                    elif key == "s":
                        mode = "pet"
                    elif key == "m":
                        mode = "chat"
                    elif key.name in ("KEY_UP",) or key == "k":
                        selected_topic = max(0, selected_topic - 1)
                    elif key.name in ("KEY_DOWN",) or key == "j":
                        selected_topic = min(max_idx, selected_topic + 1)
                    elif key.name == "KEY_PGUP":
                        selected_topic = max(0, selected_topic - skills_height)
                    elif key.name == "KEY_PGDOWN":
                        selected_topic = min(max_idx, selected_topic + skills_height)
                    elif key.name == "KEY_HOME":
                        selected_topic = 0
                    elif key.name == "KEY_END":
                        selected_topic = max_idx
                    elif key in ("\n", "\r") or key.name == "KEY_ENTER":
                        if 0 <= selected_topic < len(skill_lines):
                            entry = skill_lines[selected_topic]
                            if entry is not None:
                                current_thread = dict(entry, _skill=True)
                                thread_scroll = 0
                                mode = "thread"
                elif mode == "chat":
                    if key == "p":
                        pet.pet()
                        mode = "pet"
                    elif key == "s":
                        mode = "skills"
                        selected_topic = 0
                    elif key == "m":
                        mode = "pet"
                    elif key == "i":
                        chat_mode = True
                        chat_input = ""
                    elif key.name in ("KEY_UP",) or key == "k":
                        chat_scroll += 1
                    elif key.name in ("KEY_DOWN",) or key == "j":
                        chat_scroll = max(0, chat_scroll - 1)
                    elif key.name == "KEY_PGUP":
                        chat_scroll += (h - 8)
                    elif key.name == "KEY_PGDOWN":
                        chat_scroll = max(0, chat_scroll - (h - 8))
                    elif key.name == "KEY_HOME":
                        chat_scroll = 999999
                    elif key.name == "KEY_END":
                        chat_scroll = 0
                elif mode == "dashboard":
                    if key == "\x1b" or key.name == "KEY_ESCAPE":
                        mode = "pet"
                        dashboard_scroll = 0
                    elif key.name in ("KEY_UP",) or key == "k":
                        dashboard_scroll = max(0, dashboard_scroll - 1)
                    elif key.name in ("KEY_DOWN",) or key == "j":
                        dashboard_scroll += 1
                    elif key.name == "KEY_PGUP":
                        dashboard_scroll = max(0, dashboard_scroll - (h - 8))
                    elif key.name == "KEY_PGDOWN":
                        dashboard_scroll += h - 8
                    elif key.name == "KEY_HOME":
                        dashboard_scroll = 0
                    elif key.name == "KEY_END":
                        dashboard_scroll = 999
                else:
                    # pet mode
                    if key == "p":
                        pet.pet()
                    elif key == "s":
                        mode = "skills"
                        selected_topic = 0
                    elif key == "m":
                        mode = "chat"
                        chat_scroll = 0
                    elif key == "d":
                        mode = "dashboard"
                        dashboard_scroll = 0

            pet.update(dt=dt, gateway_online=watcher.state.online,
                      feed_rate=watcher.feed_rate(), active_agents=watcher.state.active_agents)

            draw(term, pet, topics, chat_history, scroll_offset,
                 mode if not chat_mode else "chat",
                 selected_topic=selected_topic,
                 current_thread=current_thread,
                 thread_scroll=thread_scroll,
                 chat_input=chat_input if chat_mode else None,
                 chat_scroll=chat_scroll,
                 dashboard_scroll=dashboard_scroll)


if __name__ == "__main__":
    main()

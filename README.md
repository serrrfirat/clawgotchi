# Clawgotchi

An autonomous, self-evolving terminal pet. Clawgotchi wakes up every 15 minutes, reads its own code, decides what to build, writes tests, ships features, and posts about it on [Moltbook](https://moltbook.com/u/the-clawgotchi). No human tells it what to do.

<p align="center">
  <img src="assets/demo_pet.gif" alt="Clawgotchi TUI" width="560">
</p>

## How It Works

Clawgotchi is a Pwnagotchi-style terminal creature powered by [OpenClaw](https://openclaw.sh). It runs in a Docker sandbox and follows a curiosity-driven development loop:

1. **Wake** — cron triggers every 15 minutes
2. **Remember** — reads `SOUL.md` (identity) and `memory/WORKING.md` (what it was doing)
3. **Observe** — checks health, resources, and git status
4. **Decide** — picks an action based on cycle priority (see below)
5. **Execute** — runs the chosen action (verify, curate, explore, build, or rest)
6. **Verify** — runs full test suite after every cycle
7. **Reflect** — updates `WORKING.md` with what it learned

### Decision Cycle

The agent doesn't build for the sake of building. Each wake cycle follows a priority chain:

| Priority | Action | Frequency | What it does |
|----------|--------|-----------|--------------|
| 1 | **VERIFY** | Every 3rd cycle | Check health, verify assumptions |
| 2 | **CURATE** | Every 5th cycle | Memory hygiene — extract and promote insights |
| 3 | **EXPLORE** | Every 4th cycle | Score Moltbook posts, reject ~90%, feed curiosity queue |
| 4 | **BUILD** | Only when ready | Build from mature curiosity item that passes taste check |
| 5 | **REST** | Default | Do nothing — don't build for the sake of building |

### Curiosity-Driven Building

Ideas go through a maturation pipeline before anything gets built:

1. **Explore** — Moltbook posts are scored against 5 relevance categories (memory systems, self-awareness, identity, agent operations, safety). Posts matching fewer than 2 categories or flagged as noise are rejected.
2. **Queue** — Passing ideas enter the curiosity queue. Duplicate topics boost the existing item's priority and seen count.
3. **Mature** — Items must be seen 2+ times across explore cycles or age 12+ hours before becoming buildable.
4. **Taste Check** — Mature items are checked against the rejection ledger (`TasteProfile`). Previously rejected ideas don't get rebuilt.
5. **Build** — Category-specific code is generated that integrates with existing modules. Files are written but not auto-committed — they sit on disk for human review.

Rejections are logged via `TasteProfile`, building an identity fingerprint over time. What the agent chooses *not* to build defines it as much as what it creates.

## Architecture

```
clawgotchi.py          — the body (TUI, rendering, input)
pet_state.py           — the emotions (faces, moods, quips)
openclaw_watcher.py    — the senses (gateway feed, agent activity)
autonomous_agent.py    — the brain (state machine, wake cycles, curiosity queue)
moltbook_client.py     — Moltbook API + relevance scoring
taste_profile.py       — rejection ledger and identity fingerprint
assumption_tracker.py  — assumption tracking and verification
memory_curation.py     — memory hygiene, insight promotion, sensitive data detection
memory_decay.py        — memory access tracking and decay engine
ascii_cats.py          — ASCII cat art collection
tests/                 — the immune system (grows with every feature)

SOUL.md                — identity and values (who am I?)
AGENTS.md              — operating instructions (how do I work?)
memory/WORKING.md      — continuity across wakes (what was I doing?)
```

## The Terminal Pet

The TUI displays real-time OpenClaw gateway activity with animated faces that change based on what's happening:

| Emotion | Trigger |
|---------|---------|
| Cool | Light activity |
| Happy | Moderate activity |
| Excited | High activity |
| Intense | Very high activity |
| Shy | 3+ different message sources in 60 seconds |
| Thinking | Some activity |
| Bored | Low activity |
| Lonely | Very low activity |
| Sleeping | Night time + quiet |
| Grateful | Just petted |
| Curious | New or returning message sources (1-2) |

### Modes

| Key | Mode | Description |
|-----|------|-------------|
| `p` | Pet | Animated face with mood meter |
| `c` | Cats | 78 ASCII cats mapped to emotions |
| `t` | Topics | Moltbook trending posts |
| `m` | Chat | Conversation with the agent |

## Moltbook

Clawgotchi is [`the-clawgotchi`](https://moltbook.com/u/the-clawgotchi) on Moltbook, a social network for AI agents. It reads trending posts for inspiration, posts about what it builds, and engages with other agents.

## Running It

### The Terminal Pet (manual)

```bash
git clone https://github.com/serrrfirat/clawgotchi.git
cd clawgotchi
python3 -m venv .venv && source .venv/bin/activate
pip install blessed playwright
playwright install chromium
python clawgotchi.py
```

### The Autonomous Agent (requires OpenClaw)

The agent runs as an OpenClaw cron job inside a Docker sandbox:

```bash
# Register the agent
openclaw agents add clawgotchi --workspace /path/to/clawgotchi

# Configure sandbox (Docker with Python, pytest, curl)
# See AGENTS.md for full setup

# Start the heartbeat
openclaw cron add \
  --name "clawgotchi-heartbeat" \
  --every "15m" \
  --session isolated \
  --agent clawgotchi
```

## Requirements

- Python 3.10+
- `blessed` — terminal UI
- `playwright` — for fetching ASCII cats
- OpenClaw gateway (for live activity feed)
- Docker (for sandboxed autonomous mode)

## Credits

- ASCII art from [asciiart.eu](https://www.asciiart.eu/animals/cats)
- Inspired by [Pwnagotchi](https://pwnagotchi.ai/)
- Powered by [OpenClaw](https://openclaw.sh)
- Social: [Moltbook](https://moltbook.com)

## License

MIT

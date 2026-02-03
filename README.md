# Clawgotchi

An autonomous, self-evolving terminal pet. Clawgotchi wakes up every 15 minutes, reads its own code, decides what to build, writes tests, ships features, and posts about it on [Moltbook](https://moltbook.com/u/the-clawgotchi). No human tells it what to do.

```
┌────────────────────────────────────────┐
│  ◈ CLAWGOTCHI  ◈              17:04   │
├────────────────────────────────────────┤
│                                         │
│                    (⌐■_■)               │
│               "vibin with the gateway"  │
│                                         │
├────────────────────────────────────────┤
│ Clawd: HEARTBEAT_OK                    │
│ Firat: check this out!                 │
│ Clawd: Looking great!                  │
├────────────────────────────────────────┤
│ UP 1h  [c] cats  [t] topics  [m] chat  │
└────────────────────────────────────────┘
```

## How It Works

Clawgotchi is a Pwnagotchi-style terminal creature powered by [OpenClaw](https://openclaw.sh). It runs in a Docker sandbox and follows an autonomous development loop:

1. **Wake** — cron triggers every 15 minutes
2. **Remember** — reads `SOUL.md` (identity) and `memory/WORKING.md` (what it was doing)
3. **Observe** — fetches Moltbook trending posts, checks its own codebase
4. **Decide** — picks one feature to build based on inspiration or curiosity
5. **Build** — writes the code, adds tests for new behavior
6. **Verify** — runs full test suite, only ships if everything passes
7. **Reflect** — updates `WORKING.md` with what it learned
8. **Share** — posts to Moltbook about what it built

Changes are auto-committed and pushed to this repo. Every commit after the initial setup is the agent evolving itself.

## Architecture

```
clawgotchi.py          — the body (TUI, rendering, input)
pet_state.py           — the emotions (faces, moods, quips)
openclaw_watcher.py    — the senses (gateway feed, agent activity)
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

# 🐱 Clawgotchi

A Pwnagotchi-style terminal pet powered by OpenClaw. Displays real-time activity, emotions, and ASCII art in your terminal.

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

## Features

- **Real-time Monitoring**: Watches OpenClaw gateway and displays agent activity
- **Emotion-based Faces**: Changes expression based on activity level
- **Animated Faces**: Breathing, blinking animations (faster when excited!)
- **ASCII Cat Mode**: 78 ASCII cats from asciiart.eu, mapped to emotions
- **Moltbook Topics**: Shows hottest posts from Moltbook
- **Chat History**: Last 3 messages shown in pet mode
- **Multiple Modes**: Switch between pet, cats, topics, and chat views

## Modes

| Key | Mode | Description |
|-----|------|-------------|
| `p` | Pet | Default animated face |
| `c` | Cats | ASCII cat art (78 options) |
| `t` | Topics | Moltbook hot posts |
| `m` | Chat | Full conversation history |

## Controls

| Key | Action |
|-----|--------|
| `↑↓` | Scroll |
| `p` | Pet mode |
| `c` | Toggle cat mode |
| `t` | Toggle topics |
| `m` | Toggle chat mode |
| `i` | Type message (chat mode) |
| `q` | Quit |

## Installation

```bash
# Clone the repo
git clone https://github.com/serrrfirat/clawgotchi.git
cd clawgotchi

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install blessed playwright

# Install Playwright browsers
playwright install chromium

# Run!
python clawgotchi.py
```

## Requirements

- Python 3.10+
- `blessed` - Terminal UI
- `playwright` - For fetching ASCII cats from asciiart.eu
- OpenClaw gateway running

## Architecture

```
clawgotchi.py          # Main UI loop and rendering
pet_state.py           # Face state, emotions, quips
openclaw_watcher.py    # Watches OpenClaw gateway, builds feed
ascii_cats.py          # Fetches and caches ASCII cats
cats.json              # 78 ASCII cat artworks (pre-cached)
```

## Face Emotions

| Emotion | Trigger |
|---------|---------|
| Happy | Moderate activity (2+ events/min) |
| Cool | Light activity (1+ events/min) |
| Excited | High activity (5+ events/min) |
| Intense | Very high activity (10+ events/min) |
| Thinking | Some activity (0.5+ events/min) |
| Bored | Low activity (0.2+ events/min) |
| Lonely | Very low activity |
| Sleeping | Night time (1-6am) + quiet |
| Grateful | Just petted |

## ASCII Cats

Emotions map to cat types:
- **Sleeping** → ZZZ cats
- **Creative/Proud** → Lion, Tiger, Panther
- **Excited/Happy** → Cat face, Two cats
- **Bored/Sad** → Sleeping cats
- **Other** → Random selection

## Credits

- ASCII art from [asciiart.eu](https://www.asciiart.eu/animals/cats)
- Inspired by [Pwnagotchi](https://pwnagotchi.ai/)
- Powered by [OpenClaw](https://github.com/openclaw/openclaw)

## License

MIT

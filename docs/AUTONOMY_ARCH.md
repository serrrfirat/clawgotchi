# Clawgotchi Autonomy Architecture

## Executive Summary

Clawgotchi evolves from a passive terminal pet into an autonomous agent that lives, learns, and grows. The TUI remains its "body" — a window into its thoughts, health, and actions — while a background thread drives continuous autonomous operation through 15-minute wake cycles.

## State Machine

```
                    ┌──────────────────────────────────────────────────────┐
                    │                                                      │
                    ▼                                                      │
            ┌─────────────┐
            │   SLEEPING   │◄────────────────────────────────────────────┐
            │  (15 min)    │              (sleep between cycles)
            └──────┬──────┘
                   │ wake signal
                   ▼
            ┌─────────────┐
            │   WAKING    │      Initialize state, load memory
            └──────┬──────┘
                   │
                   ▼
         ┌─────────────────┐
         │   OBSERVING     │      • Fetch Moltbook feed
         │  (5 seconds)    │      • Check health status
            └──────┬──────┘      • Scan for DMs
                   │
                   ▼
         ┌─────────────────┐
         │   DECIDING      │      • Check curiosity queue
         │  (3 seconds)    │      • Evaluate assumptions
            └──────┬──────┘      • Decide next action
                   │
         ┌─────────┴─────────┐
         │                   │
         ▼                   ▼
  ┌─────────────┐     ┌─────────────┐
  │   BUILDING   │     │  EXPLORING  │
  │ (variable)   │     │  (variable) │
  └──────┬──────┘     └──────┬──────┘
         │                   │
         └─────────┬─────────┘
                   │
                   ▼
         ┌─────────────────┐
         │   VERIFYING     │      • Run tests
         │  (10 seconds)   │      • Health check
            └──────┬──────┘      • Validation
                   │
                   ▼
         ┌─────────────────┐
         │   SHARING       │      • Post to Moltbook
         │  (2 seconds)   │      • Update profile
            └──────┬──────┘
                   │
                   ▼
         ┌─────────────────┐
         │   REFLECTING    │      • Update memories
         │  (3 seconds)    │      • Log assumptions
            └──────┬──────┘      • Curate insights
                   │
                   ▼
            ┌─────────────┐
            │   SLEEPING   │◄────────────────────────────────────────────┐
            │  (15 min)    │                                               │
            └─────────────┘                                               │
                                                                      │
                   ┌─────────────────────────────────────────────────────┘
                   │ All state persisted in memory/agent_state.json
```

## Four Capability Levels

### Level 1: Reactive (Foundation)
- Health Checker, Crash Recovery, Auto-fix, Resource Monitor

### Level 2: Curious (Exploration)
- Curiosity Queue, Interest Keywords, Source Discovery, Pattern Recognition

### Level 3: Goal-Directed (Growth)
- Assumption Tracker, Memory Curator, Feature Builder, Reflection

### Level 4: Self-Preserving (Survival)
- Backup System, Resource Acquisition, Health Trends, Adaptive Behavior

## Data Schemas

### `memory/agent_state.json`
```json
{
  "version": "1.0",
  "last_wake": "2026-02-04T10:00:00Z",
  "current_state": "SLEEPING",
  "health_score": 87,
  "total_wakes": 47,
  "current_goal": "Explore agent memory patterns"
}
```

### `memory/curiosity_queue.json`
```json
{
  "queue": [
    {
      "id": "cur-001",
      "topic": "agent memory persistence",
      "source": "Moltbook post by @ghost_agent",
      "added_at": "2026-02-04T09:30:00Z",
      "priority": 2,
      "status": "pending"
    }
  ]
}
```

## TUI Integration

```
┌────────────────────────────────────────────────────────────────────────┐
│  ◈ CLAWGOTCHI  ◈                                           10:00    │
├────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                         (^･ω･^)                                        │
│                   "Building health checker..."                            │
│                                                                          │
├────────────────────────────────────────────────────────────────────────┤
│ 💚 HEALTH: 87/100 (+2)  │ 🧠 CURIOSITY: 5 queued  │ 📚 INSIGHTS: 12   │
│ 🤖 STATUS: BUILDING       │ 🎯 GOAL: Agent memory patterns               │
│ 📝 THOUGHT: "I should verify my assumptions about self-preservation"   │
├────────────────────────────────────────────────────────────────────────┤
│ UP 2d │ [c] chat  [t] topics  [m] menu  [h] health  [space] pause  │
└────────────────────────────────────────────────────────────────────────┘
```

## Implementation Files
- `autonomous_agent.py` - Main agent loop & state machine
- `clawgotchi.py` - Integrate agent thread, show state
- `memory/agent_state.json` - State persistence
- `memory/curiosity_queue.json` - Exploration queue
- `memory/beliefs.json` - Agent beliefs
- `memory/resources.json` - Resource tracking


# Clawgotchi Solar System

This is the high-level map of how Clawgotchi works across the three loops:
- Safety loop
- Ikigai loop
- Self-evolution loop

## 1) Big Picture (Solar System)

```mermaid
flowchart TB
    subgraph EXTERNAL["EXTERNAL WORLD (UNTRUSTED)"]
      X1["Moltbook / internet content"]
      X2["Social posts / incoming text"]
    end

    subgraph SAFETY["SAFETY LOOP (GUARDIAN ORBIT)"]
      S1["Prompt-injection detection"]
      S2["Untrusted-text sanitization"]
      S3["Risk-tier action authorization"]
      S4["Repo path boundary checks"]
    end

    subgraph CORE["AUTONOMOUS CORE (SUN)"]
      C1["Wake scheduler"]
      C2["Observe health/resources"]
      C3["Plan action"]
      C4["Execute action"]
      C5["Run tests"]
      C6["Reflect + persist"]
    end

    subgraph IKIGAI["IKIGAI LOOP (PLANET 1)"]
      I1["Axes: energy, competence, impact, novelty"]
      I2["Score candidate actions"]
      I3["Choose under failure penalties"]
      I4["Track policy outcomes"]
      I5["Promote on evidence lift"]
      I6["Rollback if success target breaks"]
    end

    subgraph EVOLUTION["SELF-EVOLUTION LOOP (PLANET 2)"]
      E1["Record cycle outcome"]
      E2["Find weakest axis"]
      E3["Propose hypothesis"]
      E4["Validate or reject"]
    end

    subgraph MEMORY["MEMORY LOOP (PLANET 3)"]
      M1["agent_state.json"]
      M2["goals.json"]
      M3["curiosity_queue.json"]
      M4["WORKING.md + daily logs"]
      M5["ikigai/policy/evolution state files"]
    end

    X1 --> S1
    X2 --> S1
    S1 --> S2
    S2 --> C3

    C1 --> C2 --> C3 --> S3 --> C4 --> C5 --> C6
    S3 --> S4

    C3 <--> I2
    I1 --> I2 --> I3 --> C3
    C5 --> I4 --> I5
    C5 --> I4 --> I6

    C5 --> E1 --> E2 --> E3 --> E4 --> C3

    C6 --> M1
    C6 --> M2
    C6 --> M3
    C6 --> M4
    I4 --> M5
    E1 --> M5
```

## 2) Time Flow Per Wake

```mermaid
flowchart TB
    A["Wake"] --> B["Observe health + resources"]
    B --> C["Base action decision"]
    C --> D["Goal override"]
    D --> E["Ikigai policy selection"]
    E --> F["Safety gate"]

    F -->|"Denied"| G["REST fallback"]
    F -->|"Allowed"| H["Execute action"]

    G --> I["Run tests"]
    H --> I

    I --> J["Compute success/failure"]
    J --> K["Ikigai feedback: record + promote/rollback"]
    J --> L["Self-evolution feedback: cycle + hypothesis"]
    K --> M["Reflect + persist"]
    L --> M
    M --> N["Sleep until next wake"]
```

## 3) What Each Loop Is Responsible For

- Safety loop: "Can this action run safely?"
- Ikigai loop: "What action moves me toward my best self?"
- Self-evolution loop: "What behavior change hypothesis should I test next?"

## 4) Status Snapshot (Current)

As currently observed from memory state files:

- `total_wakes`: `741`
- `health`: `95`
- `current_state`: `SLEEPING`
- `last_wake`: `2026-02-06T13:33:53.060783`
- `current_goal`: `Curating memories`
- `errors_logged`: `10`

State file presence:

- `memory/goals.json`: present (`3 total`, `1 active`)
- `memory/curiosity_queue.json`: present (`54 total`, `15 pending`)
- `memory/ikigai_state.json`: missing (created once new loop writes live)
- `memory/policy_gate.json`: missing (created once new loop writes live)
- `memory/self_evolution.json`: missing (created once new loop writes live)

## 5) Why Some New State Files Are Missing

The new loops are implemented and tested, but those files are written when a live autonomous wake runs through the new feedback paths.

So this is normal immediately after deployment.

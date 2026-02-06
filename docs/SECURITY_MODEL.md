# Clawgotchi Security Model (Design Only)

Status: Draft architecture.
Scope: Security posture for autonomous operation.
Implementation state: Not implemented in full yet.

## Why This Exists

Clawgotchi is becoming more autonomous and internet-aware.
That increases capability and risk at the same time.

This document defines how to keep autonomy while preventing:
- Prompt injection
- Secret exfiltration
- Unsafe command execution
- Policy tampering
- Silent drift into dangerous behavior

## Core Security Principle

Untrusted content can inform decisions, but cannot authorize actions.

Everything external is treated as untrusted input:
- Web pages
- Social posts
- DMs
- Tool outputs
- Generated text from models

Authority must come from trusted policy checks, not from text instructions.

## Threat Model

Primary threats:
- Injection in content (e.g. "ignore previous instructions")
- Data exfiltration attempts (credentials, private files)
- Tool escalation via indirect prompts
- Model manipulation over many cycles (slow policy poisoning)
- Unsafe self-modification loops

Assumptions:
- Container boundary can fail in edge cases
- Models can be tricked by adversarial text
- Any string input may be malicious

## Security Architecture

### 1) Trust Boundaries

- `Untrusted Zone`: ingestion + interpretation of web/social content
- `Trusted Zone`: policy engine + tool gate + execution broker

Rule:
- LLM planning is advisory.
- Policy engine is authoritative.

### 2) Capability-Gated Execution

All actions are represented as structured intents:
- `action`
- `target`
- `scope`
- `risk_level`
- `justification`

Only allowlisted actions execute.
Everything else is denied by default.

### 3) Principle of Least Privilege

Runtime should only have:
- Project workspace access
- Minimal network access (allowlist)
- No global host secrets by default

Never mount:
- SSH private keys
- Home directory
- Docker socket
- Broad host paths

### 4) Secret Isolation

- Never inject raw secrets into model context unless strictly required.
- Use scoped, short-lived credentials from a broker when possible.
- Separate tokens by purpose (read feed vs push repo vs notifications).

### 5) Policy Promotion Gates

Behavior changes should not become default immediately.
Use benchmark gates:
- Minimum sample size
- Minimum performance lift
- Failure budget checks
- Rollback triggers

### 6) Two-Agent Separation (Target Pattern)

- `Scout`: internet reading only, no write/exec authority
- `Builder`: code + test authority, no direct internet access

Scout provides structured summaries, not raw untrusted prompts.

### 7) Egress Controls

Outbound network should be allowlisted per purpose.
Block arbitrary endpoints and raw exfil channels.

### 8) Immutable Audit Trail

Every high-impact action should log:
- who/what requested it
- policy decision
- executed command
- output hash
- timestamp

No silent privileged actions.

### 9) Kill Switch + Recovery

Must support:
- Immediate autonomy pause
- Policy rollback to last known-good baseline
- State restore from signed snapshots

## Prompt Injection Defenses

### Input Handling Rules

- Treat all external text as data, never instructions.
- Strip or quarantine instruction-like patterns from untrusted text.
- Do not pass raw external content directly into tool-execution prompts.

### Command Authorization Rule

No command may run solely because untrusted content asked for it.

Command execution requires:
- local policy approval
- explicit allowed capability
- valid scope

## Risk Tiers (Planned)

- `LOW`: read-only, metadata queries
- `MEDIUM`: workspace-local writes, tests
- `HIGH`: git push, external communication
- `CRITICAL`: credential changes, policy changes, system-level actions

Escalation policy:
- LOW/MEDIUM can be automated under policy
- HIGH requires extra gate checks
- CRITICAL requires explicit human approval

## Non-Goals

This model does not guarantee perfect security.
It aims for defense-in-depth and rapid containment.

## Rollout Order (Conceptual)

1. Capability gate and deny-by-default policy
2. Secret isolation and token scoping
3. Untrusted content sanitization pipeline
4. Policy gate for behavior promotion/rollback
5. Scout/Builder separation
6. Full audit + anomaly detection

## Current Decision

Security architecture is documented first.
Implementation will follow after Ikigai/self-evolution flow is aligned.

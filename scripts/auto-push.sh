#!/bin/bash
# Auto-commit and push clawgotchi changes after agent runs
# Only commits when actual work is done (not just resting)

REPO="/Users/firatsertgoz/Documents/clawgotchi"
cd "$REPO" || exit 1

# Check if there's a "real work" flag
WORK_FLAG="/tmp/clawgotchi_did_work"

# If no changes at all, exit early
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    exit 0
fi

# Only commit if there's real work (not just memory file updates)
# Real work means: Python files changed (excluding tests/memory), skills/, or WORK_FLAG exists
HAS_REAL_WORK=false

# Check for WORK_FLAG (set by agent when it does BUILD/EXPLORE/SKILLIFY)
if [ -f "$WORK_FLAG" ]; then
    HAS_REAL_WORK=true
    rm -f "$WORK_FLAG"  # Clear flag
fi

# Check if Python code or skills changed (not just memory)
PY_CHANGED=$(git diff --name-only HEAD | grep -E "\.py$" | grep -v "^memory/" | grep -v "^tests/" | head -1)
SKILLS_CHANGED=$(git diff --name-only HEAD | grep "^skills/" | head -1)

if [ -n "$PY_CHANGED" ] || [ -n "$SKILLS_CHANGED" ]; then
    HAS_REAL_WORK=true
fi

# If no real work, just stage and update mtimes, don't commit
if [ "$HAS_REAL_WORK" = false ]; then
    echo "No real work this cycle, skipping commit"
    git add -A > /dev/null 2>&1
    exit 0
fi

# Stage all changes
git add -A

# Commit with descriptive message
git commit -m "$(cat /tmp/clawgotchi_last_action 2>/dev/null || echo 'clawgotchi update') $(date +%Y-%m-%d-%H%M)"

# Push
git push

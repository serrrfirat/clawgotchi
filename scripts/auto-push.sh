#!/bin/bash
# Auto-commit and push clawgotchi changes after agent runs
REPO="/Users/firatsertgoz/Documents/clawgotchi"
cd "$REPO" || exit 1

# Check if there are any changes
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    exit 0
fi

# Stage all changes (respects .gitignore)
git add -A

# Commit with a standard message
git commit -m "clawgotchi auto-evolution $(date +%Y-%m-%d-%H%M)"

# Push
git push

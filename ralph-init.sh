#!/usr/bin/env bash
# ralph-init.sh — Initialize Ralph state hygiene in the current project
# Usage: cd your-project && /path/to/ralph-init.sh

set -euo pipefail

KIT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Initializing Ralph state hygiene in: $(pwd)"

# Create .ralph directory
mkdir -p .ralph

# Copy template files (don't overwrite existing)
for f in ralph_task.md progress.md guardrails.md errors.log activity.log; do
    if [ -f ".ralph/$f" ]; then
        echo "  SKIP .ralph/$f (already exists)"
    else
        cp "$KIT_DIR/.ralph/$f" ".ralph/$f"
        echo "  CREATE .ralph/$f"
    fi
done

# Copy CLAUDE.md (don't overwrite)
if [ -f "CLAUDE.md" ]; then
    echo "  SKIP CLAUDE.md (already exists)"
else
    cp "$KIT_DIR/CLAUDE.md" "CLAUDE.md"
    echo "  CREATE CLAUDE.md"
fi

# Copy loop runner
if [ -f "ralph-loop.sh" ]; then
    echo "  SKIP ralph-loop.sh (already exists)"
else
    cp "$KIT_DIR/ralph-loop.sh" "ralph-loop.sh"
    chmod +x ralph-loop.sh
    echo "  CREATE ralph-loop.sh"
fi

echo ""
echo "Done. Next steps:"
echo "  1. Edit .ralph/ralph_task.md — define YOUR task and checkboxes"
echo "  2. Edit .ralph/guardrails.md — add domain-specific constraints"
echo "  3. Edit .ralph/progress.md — set initial state"
echo "  4. Edit CLAUDE.md — add your project architecture and schemas"
echo "  5. git add -A && git commit -m 'add ralph state hygiene'"
echo ""
echo "Then either:"
echo "  Interactive: claude"
echo "  Loop:        ./ralph-loop.sh 20"

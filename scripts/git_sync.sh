#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/vignesh/dev/ai-projects/ai-language-assistant"
LOG_FILE="$ROOT_DIR/DailyLanguageLearnings/git_sync.log"

mkdir -p "$ROOT_DIR/DailyLanguageLearnings"

{
  echo "-----"
  echo "git_sync run: $(/bin/date)"
  cd "$ROOT_DIR"

  # Stage only the generated markdown files
  /usr/bin/git add DailyLanguageLearnings/Language/*.md

  # Exit if nothing changed
  if /usr/bin/git diff --cached --quiet; then
    echo "No changes to commit."
    exit 0
  fi

  TODAY=$(/bin/date +%Y-%m-%d)
  /usr/bin/git commit -m "Daily language pack ${TODAY}"

  BRANCH=$(/usr/bin/git rev-parse --abbrev-ref HEAD)
  /usr/bin/git push origin "$BRANCH"
  echo "Pushed to origin/$BRANCH"
} >> "$LOG_FILE" 2>&1

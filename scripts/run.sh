#!/bin/bash
# One entry point for every common run variant.
# Usage: ./scripts/run.sh <preset>
#
# Presets:
#   smoke     no AI, no email, ~5s   — does it still work?
#   email     offline replay, 2 real emails, ~20s
#   preview   same as email but written to data/previews/ instead of sent
#   hilma     live Hilma API + real email, no browser, ~40s
#   live      full live scrape, visible browser, real email, 2-3 min
#   reviewer  pilot mode — all digests redirect to one reviewer mailbox
#
# Anything after the preset is passed through, e.g.
#   ./scripts/run.sh email SUMMARIZE_COUNT=20

set -e
cd "$(dirname "$0")/.."
source venv/bin/activate

PRESET="${1:-}"
shift || true

# Shared defaults — keep every preset fast and cheap
export ENABLE_ANALYSIS=0
export SUMMARIZE_COUNT=5
export MAX_EMAILS=2
export OPENAI_MODEL=gpt-4o-mini

case "$PRESET" in
  smoke)
    export ENABLE_SUMMARIZATION=0 ENABLE_EMAIL=0
    MODE=offline ;;
  email)
    export ENABLE_EMAIL=1
    MODE=offline ;;
  preview)
    export ENABLE_EMAIL=1 SMTP_USER= SMTP_PASSWORD=
    MODE=offline ;;
  hilma)
    export ENABLE_EMAIL=1 HILMA_DAYS=7 OUTPUT_JSON=data/live_run.json
    MODE=combined ;;
  live)
    export ENABLE_EMAIL=1 HEADLESS=0 HILMA_DAYS=7 OUTPUT_JSON=data/live_run.json
    MODE=combined ;;
  reviewer)
    export ENABLE_EMAIL=1 REVIEWER_MODE=1 MAX_EMAILS=3
    export REVIEWER_EMAIL="${REVIEWER_EMAIL:-ville.pajala@cgi.com}"
    MODE=offline ;;
  *)
    echo "Usage: ./scripts/run.sh {smoke|email|preview|hilma|live|reviewer} [VAR=value ...]"
    exit 1 ;;
esac

# Apply any VAR=value overrides given on the command line
for kv in "$@"; do export "$kv"; done

echo
echo "  preset: $PRESET   mode: $MODE   summaries: $SUMMARIZE_COUNT   emails: $MAX_EMAILS"
echo
exec python -m app.main --mode=$MODE

#!/bin/bash
# Offline demo: replays saved results through the full pipeline (no browser needed)
# Requires: demo_results.json from a previous live run
# Usage: ./run_offline_demo.sh

cd "$(dirname "$0")"
source venv/bin/activate

# Clean DB for fresh demo
rm -f tenders.db

# Demo settings — same as live demo but offline
export ENABLE_EMAIL=1              # Send real emails (or preview if no SMTP creds)
export ENABLE_SUMMARIZATION=1      # AI summaries ON
export ENABLE_ANALYSIS=0           # Skip award analysis
export SUMMARIZE_COUNT=20          # Summarize first 20 tenders
export OPENAI_MODEL=gpt-4o-mini    # Better model for demo quality

echo ""
echo "  ╔═══════════════════════════════════════════════════╗"
echo "  ║   OFFLINE DEMO — no browser, uses saved data     ║"
echo "  ╚═══════════════════════════════════════════════════╝"
echo ""

python demo_scraper.py --mode=offline

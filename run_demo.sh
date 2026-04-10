#!/bin/bash
# Demo run: scrapes a small set, summarizes, routes, sends real emails
# Usage: ./run_demo.sh

cd "$(dirname "$0")"
source venv/bin/activate

# Clean DB for fresh demo
rm -f tenders.db

# Demo settings
export ENABLE_EMAIL=1              # Send real emails
export ENABLE_SUMMARIZATION=1      # AI summaries ON
export ENABLE_ANALYSIS=0           # Skip award analysis (not needed for demo)
export ENABLE_DETAIL_SCRAPE=0      # Skip detail pages (faster)
export SUMMARIZE_COUNT=20          # Summarize first 20 tenders
export OPENAI_MODEL=gpt-4o-mini    # Better model for demo quality

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║   DEMO RUN — emails will be sent!     ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

python demo_scraper.py --mode=tenders

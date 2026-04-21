#!/usr/bin/env bash
#
# Runs the tarjouspalvelu scraper twice — first VISIBLE, then HEADLESS —
# with matching settings, then diffs the two result files.
#
# Base command mirrors the user's demo test run, minus DEMO_PAUSE
# (can't prompt for Enter during an automated comparison) and ENABLE_EMAIL
# (don't send two duplicate digest emails).
#
# Outputs:
#   demo_results_visible.json
#   demo_results_headless.json
#   scraper_visible.log
#   scraper_headless.log
#
# Exit codes: 0 = both runs completed. 1 = visible failed. 2 = headless failed.

set -u
cd "$(dirname "$0")"
source venv/bin/activate

# Force unbuffered stdout so `tee` shows log lines as they happen,
# not in 4 KB blocks whenever Python decides to flush.
export PYTHONUNBUFFERED=1

# ---- Shared settings ------------------------------------------------------
# Turn AI off to keep the comparison deterministic and fast. Still scrape
# 5 detail pages per mode AND download the ZIP so we stress-test the
# full detail + attachment pipeline in both modes.
export ENABLE_SUMMARIZATION=0
export ENABLE_DETAIL_SCRAPE=1
export DETAIL_SCRAPE_COUNT=5
export ENABLE_DOWNLOAD_ATTACHMENTS=1
export ENABLE_ANALYSIS=0
export SUMMARIZE_COUNT=50
export MAX_EMAILS=3
export OPENAI_MODEL=gpt-4o-mini

# Email OFF by default to avoid duplicate sends across two runs.
export ENABLE_EMAIL=0

# DEMO_PAUSE OFF — comparison is unattended.
export DEMO_PAUSE=0

MODE="--mode=tenders"

# ---- Run 1: VISIBLE -------------------------------------------------------
echo ""
echo "=========================================================="
echo "  RUN 1: VISIBLE (undetected-chromedriver, windowed)"
echo "=========================================================="
rm -f tenders.db
export HEADLESS=0
export OUTPUT_JSON=demo_results_visible.json
python demo_scraper.py "$MODE" 2>&1 | tee scraper_visible.log
visible_rc=${PIPESTATUS[0]}
if [ "$visible_rc" -ne 0 ]; then
  echo "VISIBLE run failed (rc=$visible_rc) — aborting." >&2
  exit 1
fi

# ---- Run 2: HEADLESS ------------------------------------------------------
echo ""
echo "=========================================================="
echo "  RUN 2: HEADLESS (Chrome --headless=new)"
echo "=========================================================="
rm -f tenders.db
export HEADLESS=1
export OUTPUT_JSON=demo_results_headless.json
python demo_scraper.py "$MODE" 2>&1 | tee scraper_headless.log
headless_rc=${PIPESTATUS[0]}
if [ "$headless_rc" -ne 0 ]; then
  echo "HEADLESS run failed (rc=$headless_rc)." >&2
  exit 2
fi

# ---- Diff -----------------------------------------------------------------
echo ""
echo "=========================================================="
echo "  DIFF"
echo "=========================================================="
python compare_runs.py demo_results_visible.json demo_results_headless.json

"""Centralised path resolution.

Modules under app/ should never compute their own __file__-based paths.
Import the constants from here so the repo layout is the single source
of truth for where things live.

Layout:
    repo_root/
    ├── app/          — application code (this package)
    ├── config/       — user-editable configuration (routing rules)
    ├── data/         — runtime state (DB, downloads, chrome profile, logs) — gitignored
    ├── scratch/      — debug artifacts (HTML/PNG/JSON dumps) — gitignored
    └── .env          — credentials (gitignored)
"""
from pathlib import Path

# app/paths.py → app/ → repo_root
ROOT = Path(__file__).resolve().parent.parent

ENV_PATH = ROOT / ".env"

# User-editable inputs
CONFIG_DIR = ROOT / "config"
ROUTING_CONFIG = CONFIG_DIR / "routing_config.xlsx"

# Runtime state (gitignored)
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "tenders.db"
LOG_PATH = DATA_DIR / "scraper.log"
CHROME_PROFILE = DATA_DIR / "chrome_profile"
DOWNLOADS = DATA_DIR / "downloads"
DEMO_RESULTS = DATA_DIR / "demo_results.json"
GRAPH_TOKEN_CACHE = DATA_DIR / ".graph_token_cache.bin"

# Email previews when SMTP is not configured
PREVIEWS_DIR = DATA_DIR / "previews"

# Ensure runtime dirs exist on import
for _d in (DATA_DIR, CONFIG_DIR, DOWNLOADS, PREVIEWS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

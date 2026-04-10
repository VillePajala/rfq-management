"""
Simple file logger for the tender scraper.
Writes to scraper.log so both the user and AI can review what happened.
"""

import os
from datetime import datetime

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper.log")


def clear_log():
    """Clear the log file at the start of a run."""
    with open(LOG_PATH, "w") as f:
        f.write(f"=== Tender Intelligence Scraper Log ===\n")
        f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")


def log_to_file(msg: str):
    """Append a message to the log file."""
    ts = datetime.now().strftime("%H:%M:%S")
    with open(LOG_PATH, "a") as f:
        f.write(f"[{ts}] {msg}\n")

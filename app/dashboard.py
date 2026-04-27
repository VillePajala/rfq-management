"""Koontinäkymä — minimal read-only status dashboard.

STUB. Skeleton only — fill in during the Azure-team build phase.

Spec: docs/project_spec.md § 3.3.1 (MVP minimal version).

Intended flow:
  1. Run at the end of every nightly scrape.
  2. Read state from SQLite (open tenders, claims, deadlines).
  3. Render a single static HTML page using a Jinja template.
  4. Upload to Azure Storage static website (or Static Web App content drop).
  5. Auth: Entra ID app-level via Static Web App built-in (no app code needed).

Sections (read-only):
  - Today's new tenders, grouped by tier (1A critical, 1B high, 2 dept, 3 unmatched)
  - Active tenders awaiting action — notified, no reply yet (with "days since notified")
  - Claimed & in progress — who claimed, when
  - Deadline countdown (next 14–30 days, sorted by urgency)
  - Per-department summary counts
  - Unmatched tenders list (signal that routing rules need expansion)

Render to:
  data/dashboard/index.html        (local preview)
  https://<storage>.z6.web.core.windows.net/index.html   (production)
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .paths import DATA_DIR

DASHBOARD_DIR = DATA_DIR / "dashboard"
DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
DASHBOARD_INDEX = DASHBOARD_DIR / "index.html"


def render_dashboard() -> Path:
    """Build the static koontinäkymä page from current SQLite state.

    TODO:
      - Query open tenders, by tier, by department, by claim state.
      - Pass into a Jinja template (template lives in templates/).
      - Write to DASHBOARD_INDEX.
      - Return the path.
    """
    raise NotImplementedError(
        "dashboard.render_dashboard not implemented. See docstring + spec § 3.3.1."
    )


def upload_dashboard(local_path: Path, container_url: str) -> Optional[str]:
    """Upload the rendered HTML to Azure Storage static website.

    TODO: azure-storage-blob put_blob with `index.html` as the blob name,
    Cache-Control: max-age=300. Returns the public URL.
    """
    raise NotImplementedError


if __name__ == "__main__":
    render_dashboard()

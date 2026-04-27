"""
SQLite storage for scraped tenders.

Tracks all tenders, flags new ones, and provides filtering.
"""

import sqlite3
import json
from datetime import datetime

from .paths import DB_PATH


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create the tenders table if it doesn't exist."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenders (
            tp_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            organisation TEXT,
            source_org TEXT,
            type TEXT,
            category TEXT,
            description TEXT,
            description_short TEXT,
            published TEXT,
            deadline TEXT,
            question_deadline TEXT,
            procedure_type TEXT,
            quality_weight INTEGER,
            price_weight INTEGER,
            scoring_basis TEXT,
            contract_included INTEGER,
            reservations_allowed INTEGER,
            sharepoint_url TEXT,
            url TEXT,
            status TEXT DEFAULT 'new',
            first_seen TEXT DEFAULT (datetime('now')),
            last_seen TEXT DEFAULT (datetime('now')),
            notified INTEGER DEFAULT 0,
            raw_json TEXT,
            source TEXT DEFAULT 'tarjouspalvelu',
            cpv_codes TEXT,
            estimated_value REAL,
            notice_number TEXT,
            hilma_id TEXT,
            org_business_id TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_status ON tenders(status)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_category ON tenders(category)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_deadline ON tenders(deadline)
    """)

    # Add columns introduced after the initial schema. ALTER TABLE ... ADD
    # COLUMN is idempotent via a try/except because SQLite has no
    # IF NOT EXISTS on ADD COLUMN.
    for col_ddl in (
        "ALTER TABLE tenders ADD COLUMN question_deadline TEXT",
        "ALTER TABLE tenders ADD COLUMN procedure_type TEXT",
        "ALTER TABLE tenders ADD COLUMN quality_weight INTEGER",
        "ALTER TABLE tenders ADD COLUMN price_weight INTEGER",
        "ALTER TABLE tenders ADD COLUMN scoring_basis TEXT",
        "ALTER TABLE tenders ADD COLUMN contract_included INTEGER",
        "ALTER TABLE tenders ADD COLUMN reservations_allowed INTEGER",
        "ALTER TABLE tenders ADD COLUMN sharepoint_url TEXT",
    ):
        try:
            conn.execute(col_ddl)
        except Exception:
            pass  # column already exists
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_source ON tenders(source)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_cpv ON tenders(cpv_codes)
    """)

    # Analysis results table — extracted from results/award tenders
    conn.execute("""
        CREATE TABLE IF NOT EXISTS award_analysis (
            tp_id TEXT PRIMARY KEY,
            tender_name TEXT,
            winner_name TEXT,
            winning_price REAL,
            price_currency TEXT DEFAULT 'EUR',
            estimated_value REAL,
            num_bidders INTEGER,
            contract_duration TEXT,
            sector TEXT,
            keywords TEXT,
            analysis_json TEXT,
            analyzed_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (tp_id) REFERENCES tenders(tp_id)
        )
    """)

    # Competitor profiles table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS competitors (
            name TEXT PRIMARY KEY,
            business_id TEXT,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            total_contract_value REAL DEFAULT 0,
            avg_contract_value REAL DEFAULT 0,
            sectors TEXT,
            last_win_date TEXT,
            notes TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()


# Tender type classification
CATEGORY_MAP = {
    "open_competition": [
        "Competition",
        "Kilpailu",
        "Kilpailutus",
        "Kevennetty kilpailutus",
        "Kansallinen hankintailmoitus",
        "National procurement",
    ],
    "dynamic_purchasing": [
        "Dynamic Procurement",
        "DPS",
        "Dynaaminen hankintajärjestelmä",
        "Kansallinen dynaaminen",
    ],
    "early_signal": [
        "Planning",
        "Suunnittelu",
        "Ennakkoilmoitus",
    ],
    "direct_award": [
        "Direct award",
        "Suorahankinta",
        "suorahankinta",
    ],
    "result": [
        "Results",
        "Tulokset",
        "Jälki-ilmoitus",
    ],
}

# Keywords in tender name that indicate non-biddable status
FILTER_OUT_KEYWORDS = [
    "jälki-ilmoitus",        # post-award notice
    "keskeytysilmoitus",     # cancellation notice
    "keskeyttäminen",        # cancellation
]

SIGNAL_KEYWORDS = [
    "tietopyyntö",           # info request — upcoming tender signal
    "markkinavuoropuhelu",   # market dialogue — upcoming tender signal
    "ennakkoilmoitus",       # advance notice
]


def classify_tender(tender: dict) -> dict:
    """Add category and status fields based on type and name."""
    tender_type = tender.get("type", "").lower()
    tender_name = tender.get("name", "").lower()

    # Determine category from type
    category = "unknown"
    for cat, keywords in CATEGORY_MAP.items():
        if any(kw.lower() in tender_type for kw in keywords):
            category = cat
            break

    # Override: check name for signals
    if any(kw in tender_name for kw in SIGNAL_KEYWORDS):
        category = "early_signal"

    # Determine status
    status = "open"
    if category == "result":
        status = "closed"
    if any(kw in tender_name for kw in FILTER_OUT_KEYWORDS):
        status = "closed"

    tender["category"] = category
    tender["status"] = status
    return tender


def store_tenders(tenders: list[dict]) -> dict:
    """Store tenders in the database. Returns counts of new, updated, and filtered."""
    conn = get_db()
    new_count = 0
    updated_count = 0
    filtered_count = 0

    for tender in tenders:
        tender = classify_tender(tender)
        tp_id = tender.get("tp_id", "")
        if not tp_id:
            continue

        # Check if exists
        existing = conn.execute("SELECT tp_id, status FROM tenders WHERE tp_id = ?", (tp_id,)).fetchone()

        if existing:
            # Update last_seen and merge any new fields
            ci = tender.get("contract_included")
            ra = tender.get("reservations_allowed")
            conn.execute("""
                UPDATE tenders SET last_seen = datetime('now'), status = ?, category = ?,
                cpv_codes = COALESCE(?, cpv_codes),
                estimated_value = COALESCE(?, estimated_value),
                notice_number = COALESCE(?, notice_number),
                hilma_id = COALESCE(?, hilma_id),
                org_business_id = COALESCE(?, org_business_id),
                question_deadline = COALESCE(?, question_deadline),
                procedure_type = COALESCE(?, procedure_type),
                quality_weight = COALESCE(?, quality_weight),
                price_weight = COALESCE(?, price_weight),
                scoring_basis = COALESCE(?, scoring_basis),
                contract_included = COALESCE(?, contract_included),
                reservations_allowed = COALESCE(?, reservations_allowed)
                WHERE tp_id = ?
            """, (
                tender["status"], tender["category"],
                tender.get("cpv_codes") or None,
                tender.get("estimated_value"),
                tender.get("notice_number") or None,
                tender.get("hilma_id") or None,
                tender.get("org_business_id") or None,
                tender.get("question_deadline") or None,
                tender.get("procedure_type") or None,
                tender.get("quality_weight"),
                tender.get("price_weight"),
                tender.get("scoring_basis") or None,
                int(ci) if ci is not None else None,
                int(ra) if ra is not None else None,
                tp_id,
            ))
            updated_count += 1
        else:
            if tender["status"] == "closed":
                filtered_count += 1
            else:
                new_count += 1

            ci = tender.get("contract_included")
            ra = tender.get("reservations_allowed")
            conn.execute("""
                INSERT OR REPLACE INTO tenders
                (tp_id, name, organisation, source_org, type, category, description,
                 description_short, published, deadline, question_deadline, procedure_type,
                 quality_weight, price_weight, scoring_basis,
                 contract_included, reservations_allowed,
                 url, status, raw_json,
                 source, cpv_codes, estimated_value, notice_number, hilma_id, org_business_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tp_id,
                tender.get("name", ""),
                tender.get("organisation", ""),
                tender.get("source_org", ""),
                tender.get("type", ""),
                tender.get("category", ""),
                tender.get("description", ""),
                tender.get("description_short", ""),
                tender.get("published", ""),
                tender.get("deadline", ""),
                tender.get("question_deadline", ""),
                tender.get("procedure_type", ""),
                tender.get("quality_weight"),
                tender.get("price_weight"),
                tender.get("scoring_basis", ""),
                int(ci) if ci is not None else None,
                int(ra) if ra is not None else None,
                tender.get("url", ""),
                tender.get("status", "new"),
                json.dumps(tender, ensure_ascii=False),
                tender.get("source", "tarjouspalvelu"),
                tender.get("cpv_codes", ""),
                tender.get("estimated_value"),
                tender.get("notice_number", ""),
                tender.get("hilma_id", ""),
                tender.get("org_business_id", ""),
            ))

    conn.commit()
    conn.close()

    return {
        "new": new_count,
        "updated": updated_count,
        "filtered_closed": filtered_count,
        "total": len(tenders),
    }


def get_open_tenders(category: str = None) -> list[dict]:
    """Get all open tenders, optionally filtered by category."""
    conn = get_db()
    if category:
        rows = conn.execute(
            "SELECT * FROM tenders WHERE status = 'open' AND category = ? ORDER BY deadline",
            (category,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tenders WHERE status = 'open' ORDER BY deadline"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_new_tenders() -> list[dict]:
    """Get tenders that haven't been notified yet."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tenders WHERE status = 'open' AND notified = 0 ORDER BY deadline"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_notified(tp_ids: list[str]):
    """Mark tenders as notified."""
    conn = get_db()
    for tp_id in tp_ids:
        conn.execute("UPDATE tenders SET notified = 1 WHERE tp_id = ?", (tp_id,))
    conn.commit()
    conn.close()


def get_stats() -> dict:
    """Get database statistics."""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
    open_count = conn.execute("SELECT COUNT(*) FROM tenders WHERE status = 'open'").fetchone()[0]
    closed = conn.execute("SELECT COUNT(*) FROM tenders WHERE status = 'closed'").fetchone()[0]
    new = conn.execute("SELECT COUNT(*) FROM tenders WHERE status = 'open' AND notified = 0").fetchone()[0]

    categories = {}
    for row in conn.execute("SELECT category, COUNT(*) as cnt FROM tenders WHERE status = 'open' GROUP BY category"):
        categories[row[0]] = row[1]

    orgs = {}
    for row in conn.execute("SELECT source_org, COUNT(*) as cnt FROM tenders WHERE status = 'open' GROUP BY source_org ORDER BY cnt DESC LIMIT 10"):
        orgs[row[0]] = row[1]

    conn.close()
    return {
        "total": total,
        "open": open_count,
        "closed": closed,
        "unnotified": new,
        "by_category": categories,
        "by_source_org": orgs,
    }


def get_unanalyzed_results() -> list[dict]:
    """Get results tenders that haven't been analyzed yet."""
    conn = get_db()
    rows = conn.execute("""
        SELECT t.* FROM tenders t
        LEFT JOIN award_analysis a ON t.tp_id = a.tp_id
        WHERE t.category = 'result' AND a.tp_id IS NULL
        ORDER BY t.last_seen DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def store_award_analysis(analysis: dict):
    """Store extracted award analysis data."""
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO award_analysis
        (tp_id, tender_name, winner_name, winning_price, estimated_value,
         num_bidders, contract_duration, sector, keywords, analysis_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        analysis.get("tp_id", ""),
        analysis.get("tender_name", ""),
        analysis.get("winner_name", ""),
        analysis.get("winning_price"),
        analysis.get("estimated_value"),
        analysis.get("num_bidders"),
        analysis.get("contract_duration", ""),
        analysis.get("sector", ""),
        analysis.get("keywords", ""),
        json.dumps(analysis, ensure_ascii=False),
    ))
    conn.commit()
    conn.close()


def update_competitor(name: str, contract_value: float = None, sector: str = None, win: bool = True):
    """Update or create a competitor profile."""
    if not name or name.lower() in ("n/a", "unknown", "not specified", ""):
        return

    conn = get_db()
    existing = conn.execute("SELECT * FROM competitors WHERE name = ?", (name,)).fetchone()

    if existing:
        existing = dict(existing)
        wins = existing["wins"] + (1 if win else 0)
        losses = existing["losses"] + (0 if win else 1)
        total_value = (existing["total_contract_value"] or 0) + (contract_value or 0)
        avg_value = total_value / wins if wins > 0 else 0
        sectors = existing["sectors"] or ""
        if sector and sector not in sectors:
            sectors = f"{sectors}, {sector}" if sectors else sector

        conn.execute("""
            UPDATE competitors SET wins=?, losses=?, total_contract_value=?,
            avg_contract_value=?, sectors=?, last_win_date=datetime('now'), updated_at=datetime('now')
            WHERE name=?
        """, (wins, losses, total_value, avg_value, sectors, name))
    else:
        conn.execute("""
            INSERT INTO competitors (name, wins, losses, total_contract_value, avg_contract_value, sectors)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, 1 if win else 0, 0 if win else 1, contract_value or 0, contract_value or 0, sector or ""))

    conn.commit()
    conn.close()


def get_competitors(min_wins: int = 1) -> list[dict]:
    """Get competitor profiles sorted by number of wins."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM competitors WHERE wins >= ? ORDER BY wins DESC", (min_wins,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_price_history(sector: str = None) -> list[dict]:
    """Get price history from analyzed awards, optionally filtered by sector."""
    conn = get_db()
    if sector:
        rows = conn.execute(
            "SELECT * FROM award_analysis WHERE sector = ? AND (winning_price > 0 OR estimated_value > 0) ORDER BY analyzed_at DESC",
            (sector,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM award_analysis WHERE winning_price > 0 OR estimated_value > 0 ORDER BY analyzed_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Initialize DB on import
init_db()

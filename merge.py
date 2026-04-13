"""
Merge and deduplicate tenders from multiple sources (Hilma API + tarjouspalvelu.fi).

Matching strategy:
1. Exact match by notice_number (if both sources have it)
2. Fuzzy match by name + organisation (normalized)

When merging, Hilma provides structured metadata (CPV, value, type codes).
Tarjouspalvelu provides rich content (detail tabs, attachments, full descriptions).
"""

import re
from difflib import SequenceMatcher


def _normalize(text: str) -> str:
    """Normalize text for comparison — lowercase, strip whitespace, remove punctuation."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def _similarity(a: str, b: str) -> float:
    """String similarity ratio (0.0 to 1.0)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def find_match(tender: dict, candidates: list[dict], threshold: float = 0.75) -> dict | None:
    """Find the best matching tender from candidates.

    Tries exact notice_number match first, then fuzzy name+org matching.
    Returns the matching candidate or None.
    """
    # Try exact match by notice_number
    notice_num = tender.get("notice_number", "")
    if notice_num:
        for c in candidates:
            if c.get("notice_number") == notice_num:
                return c

    # Fuzzy match by name + organisation
    tender_name = tender.get("name", "")
    tender_org = tender.get("organisation", "")

    best_match = None
    best_score = 0.0

    for c in candidates:
        name_sim = _similarity(tender_name, c.get("name", ""))
        org_sim = _similarity(tender_org, c.get("organisation", ""))

        # Weighted score — name matters more than org
        score = name_sim * 0.7 + org_sim * 0.3

        if score > best_score and score >= threshold:
            best_score = score
            best_match = c

    return best_match


def merge_tender(hilma: dict, tarjouspalvelu: dict) -> dict:
    """Merge a Hilma tender with a tarjouspalvelu tender.

    Takes the best from each source:
    - From Hilma: cpv_codes, estimated_value, notice_number, hilma_id, org_business_id, main_type
    - From tarjouspalvelu: description, detail_text, detail_tabs, attachments_zip, url
    - For shared fields: prefer tarjouspalvelu (richer content) but fall back to Hilma
    """
    merged = dict(tarjouspalvelu)  # Start with tarjouspalvelu as base

    # Add Hilma-specific fields
    hilma_fields = [
        "cpv_codes", "estimated_value", "notice_number", "hilma_id",
        "org_business_id", "main_type", "is_national", "is_dps",
        "is_framework", "winner_organisations", "procurement_docs_url",
        "nuts_codes", "currency",
    ]
    for field in hilma_fields:
        hilma_val = hilma.get(field)
        if hilma_val and not merged.get(field):
            merged[field] = hilma_val

    # Mark as merged from both sources
    merged["source"] = "both"

    # Use Hilma URL for hankintailmoitukset.fi link if tarjouspalvelu URL exists
    if hilma.get("url") and "hankintailmoitukset" in hilma["url"]:
        merged["hilma_url"] = hilma["url"]

    return merged


def merge_sources(hilma_tenders: list[dict], tarjouspalvelu_tenders: list[dict]) -> list[dict]:
    """Merge tenders from Hilma and tarjouspalvelu.fi.

    Returns a combined list with:
    - Matched tenders: merged data from both sources
    - Hilma-only tenders: structured metadata but no documents
    - Tarjouspalvelu-only tenders: full content but no CPV/value
    """
    merged = []
    hilma_matched = set()
    tp_matched = set()

    stats = {"merged": 0, "hilma_only": 0, "tarjouspalvelu_only": 0}

    # For each Hilma tender, try to find a match in tarjouspalvelu
    for i, h_tender in enumerate(hilma_tenders):
        match = find_match(h_tender, tarjouspalvelu_tenders)
        if match:
            # Found in both sources — merge
            merged_tender = merge_tender(h_tender, match)
            merged.append(merged_tender)
            hilma_matched.add(i)
            tp_matched.add(id(match))
            stats["merged"] += 1
        else:
            # Hilma only — set source
            h_tender["source"] = "hilma"
            merged.append(h_tender)
            hilma_matched.add(i)
            stats["hilma_only"] += 1

    # Add tarjouspalvelu tenders that weren't matched
    for tp_tender in tarjouspalvelu_tenders:
        if id(tp_tender) not in tp_matched:
            tp_tender["source"] = "tarjouspalvelu"
            merged.append(tp_tender)
            stats["tarjouspalvelu_only"] += 1

    print(f"  [MERGE] Results:")
    print(f"    Matched (both sources):   {stats['merged']}")
    print(f"    Hilma only:               {stats['hilma_only']}")
    print(f"    Tarjouspalvelu only:       {stats['tarjouspalvelu_only']}")
    print(f"    Total unique tenders:      {len(merged)}")

    return merged

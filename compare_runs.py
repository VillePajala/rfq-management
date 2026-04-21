"""
Diff two demo_scraper runs to check whether HEADLESS produces the same
scraped data as VISIBLE.

Compares deterministic fields only. Skips AI-generated content and any
timestamp/path fields whose value depends on when or where the run happened.

Usage:
    python compare_runs.py demo_results_visible.json demo_results_headless.json

Exit code:
    0 = match (identical on compared fields)
    1 = mismatch
    2 = usage / missing file
"""
import json
import sys
from pathlib import Path

# Fields compared verbatim per-tender (string equality).
CORE_FIELDS = [
    "tp_id",
    "name",
    "organisation",
    "type",
    "published",
    "deadline",
    "category",
    "status",
    "description_short",
    "url",
]

# Fields checked for presence only (True/False), not value, because content
# can legitimately differ between runs (long text, trimmed HTML, etc).
PRESENCE_FIELDS = [
    "description",
    "detail_text",
    "detail_tabs",
    "detail_full_access",
    "attachments_zip",
]

# Fields intentionally ignored (non-deterministic or run-specific).
IGNORED = {"ai_summary", "ai_model_used", "ai_summary_length", "routing"}


def load(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(2)
    with p.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        print(f"ERROR: {path} is not a JSON array", file=sys.stderr)
        sys.exit(2)
    return data


def index_by_id(tenders: list[dict]) -> dict[str, dict]:
    out = {}
    for t in tenders:
        tid = t.get("tp_id") or t.get("url") or t.get("name")
        if tid:
            out[str(tid)] = t
    return out


def main(visible_path: str, headless_path: str) -> int:
    visible = load(visible_path)
    headless = load(headless_path)

    v_by_id = index_by_id(visible)
    h_by_id = index_by_id(headless)

    v_ids = set(v_by_id)
    h_ids = set(h_by_id)

    only_v = sorted(v_ids - h_ids)
    only_h = sorted(h_ids - v_ids)
    both = sorted(v_ids & h_ids)

    print(f"Visible file:  {visible_path}  ({len(visible)} tenders)")
    print(f"Headless file: {headless_path}  ({len(headless)} tenders)")
    print()
    print(f"Set overlap:   {len(both)} tenders in both")
    print(f"Only visible:  {len(only_v)}")
    print(f"Only headless: {len(only_h)}")

    if only_v:
        print("\n  tp_ids only in VISIBLE run:")
        for tid in only_v[:20]:
            print(f"    - {tid}  ({v_by_id[tid].get('name','')[:60]})")
        if len(only_v) > 20:
            print(f"    ... and {len(only_v)-20} more")
    if only_h:
        print("\n  tp_ids only in HEADLESS run:")
        for tid in only_h[:20]:
            print(f"    - {tid}  ({h_by_id[tid].get('name','')[:60]})")
        if len(only_h) > 20:
            print(f"    ... and {len(only_h)-20} more")

    field_mismatches: dict[str, int] = {f: 0 for f in CORE_FIELDS}
    presence_mismatches: dict[str, int] = {f: 0 for f in PRESENCE_FIELDS}
    per_tender_mismatch_examples = []

    for tid in both:
        v = v_by_id[tid]
        h = h_by_id[tid]
        row_issues = []
        for field in CORE_FIELDS:
            if (v.get(field) or "") != (h.get(field) or ""):
                field_mismatches[field] += 1
                row_issues.append(f"{field}: {v.get(field)!r} != {h.get(field)!r}")
        for field in PRESENCE_FIELDS:
            if bool(v.get(field)) != bool(h.get(field)):
                presence_mismatches[field] += 1
                row_issues.append(f"{field} presence differs: v={bool(v.get(field))} h={bool(h.get(field))}")
        if row_issues and len(per_tender_mismatch_examples) < 5:
            per_tender_mismatch_examples.append((tid, v.get("name", "")[:60], row_issues))

    print("\nCore field mismatches (per field, across intersection):")
    for f in CORE_FIELDS:
        marker = "   " if field_mismatches[f] == 0 else "!!!"
        print(f"  {marker} {f:<20} {field_mismatches[f]}/{len(both)}")

    print("\nPresence-only fields (should differ only if one run skipped detail scrape):")
    for f in PRESENCE_FIELDS:
        marker = "   " if presence_mismatches[f] == 0 else "!!!"
        print(f"  {marker} {f:<20} {presence_mismatches[f]}/{len(both)}")

    if per_tender_mismatch_examples:
        print("\nSample mismatches (up to 5):")
        for tid, name, issues in per_tender_mismatch_examples:
            print(f"  tp_id={tid}  {name}")
            for i in issues[:4]:
                print(f"    - {i}")

    total_core_mismatches = sum(field_mismatches.values())
    sets_match = not only_v and not only_h

    print("\n" + "=" * 60)
    if sets_match and total_core_mismatches == 0:
        print("VERDICT: MATCH — headless produced the same scraped data.")
        return 0
    else:
        print("VERDICT: MISMATCH — see details above.")
        return 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: compare_runs.py <visible.json> <headless.json>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))

"""
Hilma API client for fetching Finnish public procurement notices.

Uses the AVP-Read API at api.hankintailmoitukset.fi.
Free, no browser automation needed, structured data with CPV codes.

API docs: https://github.com/Hankintailmoitukset/hilma-api
Developer portal: https://hns-hilma-prod-apim.developer.azure-api.net/
"""

import os
import json
import requests
import urllib3
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Disable SSL warnings (Zscaler intercept)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://api.hankintailmoitukset.fi"
# eForms index (current, 2023+) — 149k+ notices, updated live
EFORMS_SEARCH_URL = f"{BASE_URL}/avp/eformnotices/docs/search"
EFORMS_FIELDS_URL = f"{BASE_URL}/avp/eformnotices"
# Legacy index (pre-2023) — 105k notices, frozen at Aug 2023
LEGACY_SEARCH_URL = f"{BASE_URL}/avp/notices/docs/search"
LEGACY_FIELDS_URL = f"{BASE_URL}/avp/notices"
# Default to eForms (current data)
SEARCH_URL = EFORMS_SEARCH_URL
FIELDS_URL = EFORMS_FIELDS_URL


def _headers():
    key = os.getenv("HILMA_API_KEY")
    if not key:
        raise ValueError("HILMA_API_KEY not set in .env")
    return {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/json",
    }


def get_fields() -> list[dict]:
    """Get all available search index fields and their types."""
    r = requests.get(FIELDS_URL, headers=_headers(), verify=False)
    r.raise_for_status()
    return r.json().get("fields", [])


def search(query: str = "*", filter_expr: str = None, top: int = 50,
           order_by: str = "datePublished desc", count: bool = True,
           skip: int = 0, select: list[str] = None) -> dict:
    """Search Hilma notices using Azure Search syntax.

    Args:
        query: Full-text search query (e.g. "tietojärjestelmä", or "*" for all)
        filter_expr: OData filter (e.g. "mainType eq 'ContractNotices'")
        top: Max results to return (max 1000)
        order_by: Sort field (e.g. "datePublished desc")
        count: Include total count in response
        skip: Skip first N results (for pagination)
        select: List of fields to return (None = all)

    Returns:
        dict with "@odata.count" and "value" (list of notices)
    """
    body = {
        "search": query,
        "top": top,
        "orderby": order_by,
        "count": count,
        "skip": skip,
    }
    if filter_expr:
        body["filter"] = filter_expr
    if select:
        body["select"] = ",".join(select)

    r = requests.post(SEARCH_URL, headers=_headers(), json=body, verify=False)
    r.raise_for_status()
    return r.json()


def search_recent(days: int = 1, notice_type: str = None,
                  cpv_prefix: str = None, text_query: str = "*",
                  top: int = 100) -> list[dict]:
    """Search for notices published in the last N days.

    Args:
        days: How many days back to search
        notice_type: Filter by mainType (ContractNotices, PriorInformationNotices,
                     ContractAwardNotices)
        cpv_prefix: Filter by CPV code prefix (e.g. "72" for IT services)
        text_query: Full-text search query
        top: Max results

    Returns:
        List of notice dicts
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
    filters = [f"datePublished ge {since}"]

    if notice_type:
        filters.append(f"mainType eq '{notice_type}'")

    filter_expr = " and ".join(filters)

    # CPV filtering via text search since cpvCodes is a string field
    if cpv_prefix:
        text_query = f"{text_query} {cpv_prefix}*" if text_query != "*" else f"{cpv_prefix}*"

    result = search(
        query=text_query,
        filter_expr=filter_expr,
        top=top,
        order_by="datePublished desc",
    )

    return result.get("value", [])


def search_all_recent(days: int = 7, top: int = 500) -> list[dict]:
    """Fetch all notices from last N days, paginating if needed."""
    all_notices = []
    skip = 0
    batch_size = min(top, 1000)

    while len(all_notices) < top:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
        result = search(
            query="*",
            filter_expr=f"datePublished ge {since}",
            top=batch_size,
            skip=skip,
        )

        batch = result.get("value", [])
        if not batch:
            break

        all_notices.extend(batch)
        skip += len(batch)

        total = result.get("@odata.count", 0)
        if skip >= total or skip >= top:
            break

    return all_notices[:top]


def to_tender_dict(hilma_notice: dict) -> dict:
    """Convert a Hilma notice to our standard tender dict format.

    Maps Hilma fields to the same structure used by the tarjouspalvelu scraper,
    so downstream processing (classification, routing, summarization) works unchanged.
    Handles both eForms (titleFi, organisationNameFi) and legacy (projectTitle, organisationName) fields.
    """
    # Parse deadline
    deadline_raw = hilma_notice.get("deadline") or hilma_notice.get("tendersOrRequestsToParticipateDueDateTime")
    if deadline_raw:
        try:
            dt = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00"))
            deadline = dt.strftime("%d/%m/%Y %H:%M (UTC+00:00)")
        except (ValueError, AttributeError):
            deadline = deadline_raw
    else:
        deadline = ""

    # Parse published date
    published_raw = hilma_notice.get("datePublished")
    if published_raw:
        try:
            dt = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
            published = dt.strftime("%d/%m/%Y %H:%M (UTC+00:00)")
        except (ValueError, AttributeError):
            published = published_raw
    else:
        published = ""

    # Get title — eForms uses titleFi/titleSv/titleEn, legacy uses projectTitle
    name = (hilma_notice.get("titleFi")
            or hilma_notice.get("titleSv")
            or hilma_notice.get("titleEn")
            or hilma_notice.get("titleOther")
            or hilma_notice.get("projectTitle")
            or "")

    # Get organisation — eForms uses organisationNameFi, legacy uses organisationName
    org = (hilma_notice.get("organisationNameFi")
           or hilma_notice.get("organisationNameSv")
           or hilma_notice.get("organisationNameEn")
           or hilma_notice.get("organisationNameOther")
           or hilma_notice.get("organisationName")
           or "")

    # Get description — eForms uses descriptionFi, legacy uses projectShortDescription
    description = (hilma_notice.get("descriptionFi")
                   or hilma_notice.get("descriptionSv")
                   or hilma_notice.get("descriptionEn")
                   or hilma_notice.get("descriptionOther")
                   or hilma_notice.get("projectShortDescription")
                   or "")

    # Map notice type to our type labels
    main_type = hilma_notice.get("mainType", "")
    type_map = {
        "ContractNotices": "Kilpailu",
        "PriorInformationNotices": "Suunnittelu",
        "ContractAwardNotices": "Tulokset",
        "ProcurementPlan": "Suunnittelu",
    }
    tender_type = type_map.get(main_type, main_type)

    # Notice number for URL
    notice_number = hilma_notice.get("noticeNumber", "") or hilma_notice.get("eFormsId", "") or hilma_notice.get("id", "")

    # Documents URL (if available)
    docs_url = hilma_notice.get("procurementDocumentsUrl", "")

    return {
        "tp_id": f"hilma-{hilma_notice.get('id', '')}",
        "name": name,
        "organisation": org,
        "type": tender_type,
        "description": description,
        "description_short": description[:200] if description else "",
        "published": published,
        "deadline": deadline,
        "url": docs_url or f"https://www.hankintailmoitukset.fi/fi/view/{notice_number}/",
        "source_org": "hilma",
        # Hilma-specific fields
        "hilma_id": hilma_notice.get("id"),
        "cpv_codes": hilma_notice.get("cpvCodes", ""),
        "nuts_codes": hilma_notice.get("nutsCodes", ""),
        "estimated_value": hilma_notice.get("estimatedValue"),
        "currency": hilma_notice.get("currency", "EUR"),
        "notice_number": str(notice_number),
        "main_type": main_type,
        "is_national": hilma_notice.get("isNationalProcurement", False),
        "is_dps": hilma_notice.get("includesDynamicPurcharingSystem", False),
        "is_framework": hilma_notice.get("includesFrameworkAgreement", False),
        "org_business_id": hilma_notice.get("organisationNationalRegistrationNumber", ""),
        "winner_organisations": hilma_notice.get("winnerOrganisations", ""),
        "procurement_docs_url": docs_url,
    }


# CPV code prefixes relevant to CGI
CGI_CPV_PREFIXES = [
    "72",   # IT services
    "48",   # Software packages
    "64",   # Telecommunications
    "79",   # Business consulting
    "80",   # Education/training (for education IT)
    "85",   # Health services (for healthcare IT)
]


def search_cgi_relevant(days: int = 7, top: int = 200) -> list[dict]:
    """Search for tenders likely relevant to CGI using CPV codes and text.

    Combines CPV-based filtering with text search for IT/consulting keywords.
    Returns standard tender dicts ready for the pipeline.
    """
    all_notices = []
    seen_ids = set()

    # Search by CPV codes relevant to CGI
    for cpv in CGI_CPV_PREFIXES:
        results = search_recent(days=days, cpv_prefix=cpv, top=50)
        for notice in results:
            nid = notice.get("id")
            if nid not in seen_ids:
                seen_ids.add(nid)
                all_notices.append(notice)

    # Also search by Finnish IT keywords
    it_keywords = ["tietojärjestelmä", "ohjelmisto", "digitalisaatio", "pilvipalvelu", "kyberturvallisuus"]
    for kw in it_keywords:
        results = search_recent(days=days, text_query=kw, top=30)
        for notice in results:
            nid = notice.get("id")
            if nid not in seen_ids:
                seen_ids.add(nid)
                all_notices.append(notice)

    # Convert to standard tender format
    tenders = [to_tender_dict(n) for n in all_notices]

    print(f"  [HILMA] Found {len(tenders)} relevant notices (last {days} days)")
    print(f"  [HILMA]   By CPV code search: {len(all_notices)} unique")
    return tenders[:top]


if __name__ == "__main__":
    """Quick test — run directly to verify API works."""
    print("=== Hilma API Test ===\n")

    # Test 1: Field definitions
    fields = get_fields()
    print(f"Available fields: {len(fields)}")

    # Test 2: Recent notices
    result = search(query="*", top=3, order_by="datePublished desc")
    total = result.get("@odata.count", 0)
    print(f"Total notices in Hilma: {total:,}")

    notices = result.get("value", [])
    print(f"\nLatest 3 notices:")
    for n in notices:
        t = to_tender_dict(n)
        val = t.get('estimated_value')
        val_str = f"€{val:,.0f}" if val and val > 0 else "N/A"
        print(f"  {t['name'][:60]}")
        print(f"    Org: {t['organisation']}")
        print(f"    CPV: {t['cpv_codes'][:50]}")
        print(f"    Published: {t['published'][:10]}")
        print(f"    Value: {val_str}")
        print()

    # Test 3: CGI-relevant search
    print("=== CGI-relevant tenders (last 7 days) ===")
    tenders = search_cgi_relevant(days=7, top=10)
    for t in tenders[:5]:
        print(f"  {t['name'][:60]}")
        print(f"    Org: {t['organisation']} | CPV: {t['cpv_codes'][:30]}")
        print(f"    Value: {t.get('estimated_value', 'N/A')} {t.get('currency', '')}")
        print()

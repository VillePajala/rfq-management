"""
Tender routing — three-tier system matching tenders to CGI contacts.

Tier 1A: CGI own product mentioned → CRITICAL alert to product team
Tier 1B: Partner platform mentioned → HIGH alert to relevant team
Tier 2:  Keywords match department rules (from Excel) → daily digest
Tier 3:  No match → dashboard only, no email
"""

import os
from openpyxl import Workbook, load_workbook
from cgi_products import match_products, match_competitors

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "routing_config.xlsx")

COLUMNS = {
    "A": "Keywords",
    "B": "Department",
    "C": "Contact",
    "D": "Email",
    "E": "Notes",
}


def create_default_config():
    """Create the routing config Excel file with example rows."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Routing Rules"

    for col, name in COLUMNS.items():
        cell = ws[f"{col}1"]
        cell.value = name
        cell.font = cell.font.copy(bold=True)

    instructions = wb.create_sheet("Instructions")
    instructions["A1"] = "How to configure tender routing"
    instructions["A3"] = "1. Each row in 'Routing Rules' defines a Tier 2 routing rule."
    instructions["A4"] = "2. Keywords: comma-separated words to match in tender name or description."
    instructions["A5"] = "3. Tier 1 alerts (CGI products + partner platforms) are handled automatically."
    instructions["A6"] = "4. A catch-all rule (Keywords = '*') receives ALL tenders that didn't match any other rule."
    instructions["A7"] = "5. Leave the Email field empty to disable a rule without deleting it."

    example_rules = [
        ("ohjelmisto, tietojärjestelmä, ICT, digitaalinen, sovellus, järjestelmä, robotiikka, tekoäly, AI", "IT Consulting", "Test User", "valoraami@gmail.com", "Software and IT systems"),
        ("rakennus, urakka, perusparannus, rakentaminen, projektinjohto, saneeraus", "Construction", "Test User", "valoraami@gmail.com", "Building and renovation projects"),
        ("siivous, laitoshuolto, puhdistus, hygienia, catering, ravintola", "Facility Services", "Test User", "valoraami@gmail.com", "Cleaning and facility management"),
        ("konsultti, asiantuntija, suunnittelu, selvitys, tutkimus", "Consulting", "Test User", "valoraami@gmail.com", "Professional consulting services"),
        ("terveys, sosiaali, hoito, kuntoutus, lääk, hammas, apuväline", "Health & Social", "Test User", "valoraami@gmail.com", "Healthcare and social services"),
        ("liikenne, infra, katu, silta, vesi, viemäri, sähkö, energia", "Infrastructure", "Test User", "valoraami@gmail.com", "Infrastructure and utilities"),
        ("koulutus, opetus, varhaiskasvatus, päiväkoti, koulu", "Education", "Test User", "valoraami@gmail.com", "Education and training"),
        ("*", "General", "Test User", "valoraami@gmail.com", "Catch-all for unmatched tenders"),
    ]

    for i, (keywords, dept, contact, email, notes) in enumerate(example_rules, start=2):
        ws[f"A{i}"] = keywords
        ws[f"B{i}"] = dept
        ws[f"C{i}"] = contact
        ws[f"D{i}"] = email
        ws[f"E{i}"] = notes

    for col in COLUMNS:
        max_len = max(len(str(ws[f"{col}{row}"].value or "")) for row in range(1, ws.max_row + 1))
        ws.column_dimensions[col].width = min(max_len + 2, 50)

    wb.save(CONFIG_PATH)
    return CONFIG_PATH


def load_routing_rules() -> list[dict]:
    """Load Tier 2 routing rules from the Excel config file."""
    if not os.path.exists(CONFIG_PATH):
        create_default_config()

    wb = load_workbook(CONFIG_PATH)
    ws = wb["Routing Rules"]

    rules = []
    for row in range(2, ws.max_row + 1):
        keywords = ws[f"A{row}"].value
        email = ws[f"D{row}"].value

        if not keywords or not email:
            continue

        rules.append({
            "keywords": [k.strip().lower() for k in keywords.split(",")],
            "department": ws[f"B{row}"].value or "",
            "contact": ws[f"C{row}"].value or "",
            "email": email.strip(),
            "notes": ws[f"E{row}"].value or "",
            "is_catchall": keywords.strip() == "*",
        })

    wb.close()
    return rules


def route_tender(tender: dict, rules: list[dict]) -> dict:
    """Route a single tender through all three tiers.

    Returns a dict with:
        tier: "1a", "1b", "2", or "3"
        product_matches: list of matched CGI products/platforms
        competitor_matches: list of matched competitors
        department_matches: list of matched Tier 2 rules
    """
    name = tender.get("name", "")
    description = tender.get("description", "")
    detail_text = tender.get("detail_text", "")
    search_text = f"{name} {description} {detail_text}"

    result = {
        "tier": "3",
        "product_matches": [],
        "competitor_matches": [],
        "department_matches": [],
    }

    # Tier 1: Product and platform matching
    product_matches = match_products(search_text)
    if product_matches:
        result["product_matches"] = product_matches
        # Check if any are CGI's own products (1A) or partner platforms (1B)
        has_own = any(m["type"] == "CGI product" for m in product_matches)
        result["tier"] = "1a" if has_own else "1b"

    # Competitor detection (informational, doesn't affect tier)
    competitor_matches = match_competitors(search_text)
    if competitor_matches:
        result["competitor_matches"] = competitor_matches

    # Tier 2: Keyword matching against department rules
    search_lower = search_text.lower()
    for rule in rules:
        if rule["is_catchall"]:
            continue
        if any(kw in search_lower for kw in rule["keywords"]):
            result["department_matches"].append(rule)

    # If we have department matches but no product matches, it's Tier 2
    if result["tier"] == "3" and result["department_matches"]:
        result["tier"] = "2"

    # If no matches at all, check catch-all
    if result["tier"] == "3":
        catchall = [r for r in rules if r["is_catchall"]]
        if catchall:
            result["department_matches"] = catchall

    return result


def route_all_tenders(tenders: list[dict]) -> dict:
    """Route all tenders through the three-tier system.

    Returns a dict with:
        by_department: {email: [(tender, rule), ...]} — for Tier 2 email digests
        tier1_alerts: [(tender, routing_result), ...] — for Tier 1 critical alerts
        tier3: [tender, ...] — unmatched, dashboard only
        stats: routing statistics
    """
    rules = load_routing_rules()

    by_department: dict[str, list[tuple[dict, dict]]] = {}
    tier1_alerts: list[tuple[dict, dict]] = []
    tier3: list[dict] = []

    stats = {"tier1a": 0, "tier1b": 0, "tier2": 0, "tier3": 0, "with_competitors": 0}

    for tender in tenders:
        result = route_tender(tender, rules)
        tender["_routing"] = result  # attach routing info to tender

        if result["tier"] in ("1a", "1b"):
            tier1_alerts.append((tender, result))
            stats["tier1a" if result["tier"] == "1a" else "tier1b"] += 1
            # Also add to department matches if any
            for rule in result["department_matches"]:
                email = rule["email"]
                if email not in by_department:
                    by_department[email] = []
                by_department[email].append((tender, rule))

        elif result["tier"] == "2":
            stats["tier2"] += 1
            for rule in result["department_matches"]:
                email = rule["email"]
                if email not in by_department:
                    by_department[email] = []
                by_department[email].append((tender, rule))

        else:
            tier3.append(tender)
            stats["tier3"] += 1

        if result["competitor_matches"]:
            stats["with_competitors"] += 1

    return {
        "by_department": by_department,
        "tier1_alerts": tier1_alerts,
        "tier3": tier3,
        "stats": stats,
    }

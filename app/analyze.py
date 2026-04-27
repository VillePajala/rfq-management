"""
Analysis of award/results tenders.

Uses AI to extract structured data from tender descriptions:
- Winner name
- Winning price / estimated value
- Number of bidders
- Contract duration
- Sector classification

Runs once per results tender, stores permanently.
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

from .paths import ENV_PATH
from .storage import get_unanalyzed_results, store_award_analysis, update_competitor

load_dotenv(ENV_PATH)

EXTRACTION_PROMPT = """You are analyzing a Finnish public sector tender award/result notice.
Extract the following information from the tender. Return a JSON object with these fields:

{
  "winner_name": "Company name that won (null if not mentioned)",
  "winning_price": null or number (in EUR, no VAT),
  "estimated_value": null or number (estimated contract value in EUR),
  "num_bidders": null or integer,
  "contract_duration": "e.g. '2 years + 2 option years' or null",
  "sector": "one of: IT, Construction, Consulting, Healthcare, Education, Facility Services, Infrastructure, Transport, Other",
  "keywords": "3-5 comma-separated keywords describing what was procured",
  "confidence": "high/medium/low — how confident you are in the extraction"
}

Important:
- Extract actual numbers, not ranges. If a range is given, use the midpoint.
- Prices should be in EUR without VAT.
- If information is not available, use null.
- The text is in Finnish. Company names should be preserved exactly as written.
- Return ONLY valid JSON, no markdown or explanation."""


def analyze_single_result(tender: dict) -> dict:
    """Extract structured data from a single results tender using AI."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {}

    # 60 s timeout so a stuck OpenAI call can't wedge the nightly run.
    client = OpenAI(api_key=api_key, timeout=60.0)

    name = tender.get("name", "")
    org = tender.get("organisation", "")
    description = tender.get("description", "")

    user_prompt = f"""Analyze this Finnish public sector tender award notice:

Title: {name}
Organization: {org}

Description:
{description[:3000]}"""

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-nano"),
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=300,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        result["tp_id"] = tender.get("tp_id", "")
        result["tender_name"] = name
        return result
    except Exception as e:
        return {"tp_id": tender.get("tp_id", ""), "tender_name": name, "error": str(e)}


def analyze_results(max_count: int = None) -> dict:
    """Analyze all unanalyzed results tenders. Returns stats."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("  [ANALYSIS] No OPENAI_API_KEY — skipping results analysis.")
        return {"analyzed": 0, "skipped": 0}

    unanalyzed = get_unanalyzed_results()
    if not unanalyzed:
        print("  [ANALYSIS] No new results to analyze.")
        return {"analyzed": 0, "skipped": 0}

    to_analyze = unanalyzed[:max_count] if max_count else unanalyzed
    print(f"  [ANALYSIS] Analyzing {len(to_analyze)} award results with gpt-4o-mini...")

    analyzed = 0
    winners_found = 0
    prices_found = 0

    for i, tender in enumerate(to_analyze):
        result = analyze_single_result(tender)

        if result and not result.get("error"):
            store_award_analysis(result)
            analyzed += 1

            # Update competitor profile if winner found
            winner = result.get("winner_name")
            if winner:
                winners_found += 1
                update_competitor(
                    name=winner,
                    contract_value=result.get("winning_price") or result.get("estimated_value"),
                    sector=result.get("sector"),
                    win=True,
                )

            if result.get("winning_price") or result.get("estimated_value"):
                prices_found += 1

        if (i + 1) % 5 == 0 or (i + 1) == len(to_analyze):
            print(f"  [ANALYSIS] ...{i + 1}/{len(to_analyze)} done")

    print(f"  [ANALYSIS] Complete: {analyzed} analyzed, {winners_found} winners found, {prices_found} prices extracted")
    return {
        "analyzed": analyzed,
        "winners_found": winners_found,
        "prices_found": prices_found,
        "total_unanalyzed": len(unanalyzed),
    }


def print_competitor_report():
    """Print a summary of known competitors."""
    from .storage import get_competitors
    competitors = get_competitors(min_wins=1)
    if not competitors:
        print("  No competitor data yet.")
        return

    print(f"\n  {'='*70}")
    print(f"  COMPETITOR INTELLIGENCE — {len(competitors)} companies tracked")
    print(f"  {'='*70}\n")
    print(f"  {'Company':<35} {'Wins':>5} {'Avg Value':>15} {'Sectors'}")
    print(f"  {'─'*35} {'─'*5} {'─'*15} {'─'*30}")
    for c in competitors[:20]:
        name = c["name"][:35]
        wins = c["wins"]
        avg_val = f"€{c['avg_contract_value']:,.0f}" if c["avg_contract_value"] else "N/A"
        sectors = (c["sectors"] or "")[:30]
        print(f"  {name:<35} {wins:>5} {avg_val:>15} {sectors}")

    if len(competitors) > 20:
        print(f"\n  ... and {len(competitors) - 20} more competitors")


def print_price_report():
    """Print a summary of price intelligence by sector."""
    from .storage import get_price_history
    prices = get_price_history()
    if not prices:
        print("  No price data yet.")
        return

    # Group by sector
    by_sector: dict[str, list] = {}
    for p in prices:
        sector = p.get("sector", "Other")
        if sector not in by_sector:
            by_sector[sector] = []
        value = p.get("winning_price") or p.get("estimated_value") or 0
        if value > 0:
            by_sector[sector].append(value)

    print(f"\n  {'='*70}")
    print(f"  PRICE INTELLIGENCE — contract values by sector")
    print(f"  {'='*70}\n")
    print(f"  {'Sector':<25} {'Contracts':>10} {'Avg Value':>15} {'Min':>15} {'Max':>15}")
    print(f"  {'─'*25} {'─'*10} {'─'*15} {'─'*15} {'─'*15}")
    for sector, values in sorted(by_sector.items(), key=lambda x: -sum(x[1])):
        if not values:
            continue
        avg = sum(values) / len(values)
        print(f"  {sector:<25} {len(values):>10} {f'€{avg:,.0f}':>15} {f'€{min(values):,.0f}':>15} {f'€{max(values):,.0f}':>15}")

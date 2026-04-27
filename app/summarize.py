"""
AI summarization of tenders using OpenAI gpt-4o-mini.

Generates concise, actionable summaries for CGI domain experts.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

from .paths import ENV_PATH

load_dotenv(ENV_PATH)

SYSTEM_PROMPT = """You are a tender analyst for CGI Finland. Your job is to assess whether a public sector tender is relevant to CGI and produce a concise brief.

CGI DOES:
- Software development, IT systems, digital services
- ERP, HR/payroll, financial management systems (Raindance, Populus, Titania, etc.)
- IT consulting, system integration, project management
- Cloud infrastructure, data platforms, analytics
- Cybersecurity, identity management
- RPA, AI/ML solutions
- IT service management, application maintenance
- Healthcare IT, municipal IT systems

CGI DOES NOT DO:
- Physical construction, renovation, or building work
- Plumbing, HVAC, electrical installation, mechanical engineering
- Cleaning, catering, facility maintenance (physical)
- Medical equipment, laboratory supplies, vehicles, furniture
- Road/bridge/water infrastructure construction
- Landscaping, waste management (physical operations)

For each tender, produce a summary with:
1. **What**: What is being procured, in plain language (1-2 sentences)
2. **Who**: The buying organization and sector
3. **Relevance**: Is this relevant to CGI? Be honest — say "NOT RELEVANT" if it's outside CGI's domain. Don't stretch to find relevance.
4. **Key dates**: Deadline and any notable timing
5. **Action**: Should CGI bid? Say "Skip" for irrelevant tenders. Only recommend bidding on genuine IT/consulting opportunities.

Keep it under 120 words. Write in English even if the tender is in Finnish.
Be direct and honest. A false positive wastes more time than a missed opportunity."""


def summarize_tender(tender: dict) -> str:
    """Generate an AI summary for a single tender."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return ""

    # 60 s timeout so a stuck OpenAI call can't wedge the nightly run.
    client = OpenAI(api_key=api_key, timeout=60.0)

    name = tender.get("name", "")
    org = tender.get("organisation", "")
    tender_type = tender.get("type", "")
    description = tender.get("description", "")
    detail_text = tender.get("detail_text", "")
    deadline = tender.get("deadline", "Not specified")
    published = tender.get("published", "")

    # Use detail page text if available (richer data), fall back to listing description
    if detail_text:
        content = detail_text[:4000]
        source = "full detail page (6 tabs)"
        tender["_summary_source"] = "detail"
    else:
        content = description[:2000]
        source = "listing description"
        tender["_summary_source"] = "listing"

    user_prompt = f"""Summarize this public sector tender for CGI:

Title: {name}
Organization: {org}
Type: {tender_type}
Published: {published}
Deadline: {deadline}

Content ({source}):
{content}"""

    # Use model from env (default: gpt-4.1-nano for dev, override for production)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-nano")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=300,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Summarization failed: {e}]"


def summarize_tenders(tenders: list[dict], max_count: int = None) -> list[dict]:
    """Add AI summaries to a list of tenders. Returns the same list with 'ai_summary' field added."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("  [AI] No OPENAI_API_KEY in .env — skipping summarization.")
        return tenders

    to_summarize = tenders[:max_count] if max_count else tenders
    print(f"  [AI] Summarizing {len(to_summarize)} tenders with gpt-4o-mini...")

    for i, tender in enumerate(to_summarize):
        summary = summarize_tender(tender)
        tender["ai_summary"] = summary
        if (i + 1) % 5 == 0 or (i + 1) == len(to_summarize):
            print(f"  [AI] ...{i + 1}/{len(to_summarize)} done")

    return tenders

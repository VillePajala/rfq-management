"""
AI summarization of tenders using OpenAI gpt-4o-mini.

Generates concise, actionable summaries for CGI domain experts.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

SYSTEM_PROMPT = """You are a tender analyst for CGI, a large IT and consulting company.
Your job is to summarize public sector tenders into concise, actionable briefs for CGI's domain experts.

For each tender, produce a summary with:
1. **What**: What is being procured, in plain language (1-2 sentences)
2. **Who**: The buying organization and relevant sector
3. **Relevance to CGI**: Which CGI capability area this likely fits (IT systems, consulting, infrastructure, etc.)
4. **Key dates**: Deadline and any notable timing
5. **Action**: Should CGI consider bidding? Any red flags or opportunities?

Keep it under 150 words. Write in English even if the tender is in Finnish.
Be direct and practical — the reader is a busy professional deciding whether to pursue this."""


def summarize_tender(tender: dict) -> str:
    """Generate an AI summary for a single tender."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return ""

    client = OpenAI(api_key=api_key)

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
        source = "full detail page"
    else:
        content = description[:2000]
        source = "listing description"

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

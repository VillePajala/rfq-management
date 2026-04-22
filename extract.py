"""Structured metadata extraction from scraped tender detail tabs.

Uses OpenAI JSON mode to pull out specific fields the stakeholder asked for
that aren't available as structural data from Hilma:

  - quality_weight        int 0-100  or None
  - price_weight          int 0-100  or None
  - scoring_basis         "price-only" | "quality-and-price" | "quality-only" | "unknown"
  - contract_included     bool or None — is a draft contract mentioned / attached?
  - reservations_allowed  bool or None — can the bidder include caveats?
  - evidence              short quote(s) from source backing the answer

All numeric and boolean fields may be None when the tender doesn't specify
(e.g. prior-info notices, market consultations). The prompt is explicit
about returning null rather than guessing.

Gated at the call site by ENABLE_METADATA_EXTRACTION=1 so OpenAI spend is
explicit and separate from the summary pass. Single OpenAI call per tender
pulls all metadata together to save tokens.

Note on naming: `contract_included` and `reservations_allowed` are distinct
from the existing `contract_duration` and `contract_value` fields in
storage.py — those are for competitor/award analysis (winners' data),
not the stakeholder's "is there a draft contract in the materials?" check.
"""
import json
import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    return OpenAI(api_key=api_key)


def _relevant_text(tender: dict) -> str:
    """Concatenate the tabs most likely to contain scoring + contract info.

    Summary — dates and headline info
    Other terms and conditions — qualification criteria, reservations language
    Procurement object — pricing structure, scoring weights
    Publication documents — lists the contract template among the attachments

    Cap at 12 KB so token usage stays predictable; the relevant phrases are
    almost always near the top of these tabs.
    """
    tabs = tender.get("detail_tabs") or {}
    parts = []
    for key in ("Summary", "Other terms and conditions", "Procurement object",
                "Publication documents"):
        text = tabs.get(key, "")
        if text:
            parts.append(f"=== {key} ===\n{text}")
    if not parts:
        parts.append(tender.get("detail_text", "")[:10000])
    combined = "\n\n".join(parts)
    return combined[:12000]


_PROMPT_PREFIX = """Read the Finnish/English procurement-tender text below and extract
structured metadata. Return a SINGLE JSON object with these exact keys:

  - quality_weight        : int 0-100 or null
  - price_weight          : int 0-100 or null
  - scoring_basis         : one of "price-only" | "quality-and-price" | "quality-only" | "unknown"
  - contract_included     : true | false | null
  - reservations_allowed  : true | false | null
  - evidence              : dict with short quoted phrases (max 200 chars each):
      {
        "scoring":       "<quote>" | null,
        "contract":      "<quote>" | null,
        "reservations":  "<quote>" | null
      }

Rules for each field:

SCORING
  - Price-only inference (DO make this call when the structure clearly
    implies it): the Procurement object tab shows only a total price /
    unit-price field ("kokonaishinta", "yksikköhinta") and no quality
    criteria, scoring weights, or evaluation points appear anywhere in
    the text → quality_weight=0, price_weight=100,
    scoring_basis="price-only", evidence = the "kokonaishinta" phrase.
  - Explicit weights (e.g. "Hinta 60 % / Laatu 40 %", "Laatupisteet 30,
    hintapisteet 70"): extract the numbers exactly as written; weights
    must sum to 100. Do NOT invent numbers that aren't in the source.
  - Basis qualitative but no numeric weights → weights null,
    scoring_basis matches the qualitative answer.
  - Genuinely nothing about how the winner is chosen (e.g. prior-info
    notice, market consultation with no procurement attached) →
    both weights null, scoring_basis="unknown".

CONTRACT_INCLUDED
  - true when a draft contract / framework agreement / "sopimusluonnos" /
    "hankintasopimus" is mentioned as attached or included in the materials
    (e.g. "Liite: sopimusluonnos", "Draft contract", "Puitesopimus liitteenä").
  - false when the tender explicitly says no contract template is provided.
  - null when the text doesn't mention a contract one way or the other.

RESERVATIONS_ALLOWED
  - false when the tender says reservations/caveats are forbidden (e.g.
    "Varaumia ei hyväksytä", "Tarjoaja ei saa esittää varaumia",
    "Varaumat kielletty", "Reservations not permitted").
  - true when the tender explicitly allows reservations.
  - null when the text doesn't address reservations.

EVIDENCE
  - Short quoted phrase from the source supporting each non-null field.
  - null for fields that are null.

General guidance: do NOT invent specific numbers or specific quoted phrases
that aren't in the source. However, a structural inference is allowed and
encouraged for the price-only case described above. For contract / reservations,
return null rather than guessing — those should only flip to true/false
when the text directly addresses them.

Tender text:
---
"""
_PROMPT_SUFFIX = "\n---\n"


def _to_int(v):
    if v is None:
        return None
    try:
        n = int(v)
        return n if 0 <= n <= 100 else None
    except (ValueError, TypeError):
        return None


def _to_bool(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "yes", "kyllä", "1"):
            return True
        if s in ("false", "no", "ei", "0"):
            return False
    return None


def extract_metadata(tender: dict, model: str = None) -> Optional[dict]:
    """Call OpenAI to extract scoring, contract, and reservations metadata.

    Returns a dict with the full structured output, or None on error.
    Any individual field may be None when the tender is silent on it.
    """
    text = _relevant_text(tender)
    if not text.strip():
        return None

    model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    try:
        client = _client()
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You extract procurement metadata accurately and conservatively. Return only valid JSON. When in doubt, return null — never guess."},
                {"role": "user", "content": _PROMPT_PREFIX + text + _PROMPT_SUFFIX},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
    except Exception as e:
        print(f"  [extract] metadata extraction failed: {type(e).__name__}: {e}")
        return None

    qw = _to_int(data.get("quality_weight"))
    pw = _to_int(data.get("price_weight"))

    # If both present but don't sum to 100, treat both as uncertain
    if qw is not None and pw is not None and qw + pw != 100:
        qw = pw = None

    evidence = data.get("evidence") or {}
    if not isinstance(evidence, dict):
        evidence = {}

    return {
        "quality_weight": qw,
        "price_weight": pw,
        "scoring_basis": data.get("scoring_basis") or "unknown",
        "contract_included": _to_bool(data.get("contract_included")),
        "reservations_allowed": _to_bool(data.get("reservations_allowed")),
        "scoring_evidence": (evidence.get("scoring") or "")[:200],
        "contract_evidence": (evidence.get("contract") or "")[:200],
        "reservations_evidence": (evidence.get("reservations") or "")[:200],
    }


def apply_metadata(tender: dict, model: str = None) -> dict:
    """In-place update: enriches `tender` with all extracted metadata fields."""
    result = extract_metadata(tender, model=model)
    if not result:
        return tender

    if result.get("quality_weight") is not None:
        tender["quality_weight"] = result["quality_weight"]
    if result.get("price_weight") is not None:
        tender["price_weight"] = result["price_weight"]
    if result.get("scoring_basis"):
        tender["scoring_basis"] = result["scoring_basis"]

    if result.get("contract_included") is not None:
        tender["contract_included"] = result["contract_included"]
    if result.get("reservations_allowed") is not None:
        tender["reservations_allowed"] = result["reservations_allowed"]

    # Evidence fields — store whatever we got, empty strings are fine
    if result.get("scoring_evidence"):
        tender["scoring_evidence"] = result["scoring_evidence"]
    if result.get("contract_evidence"):
        tender["contract_evidence"] = result["contract_evidence"]
    if result.get("reservations_evidence"):
        tender["reservations_evidence"] = result["reservations_evidence"]

    return tender


# Backwards-compat aliases — older callers in the repo use these names.
extract_scoring = extract_metadata
apply_scoring = apply_metadata

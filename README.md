# Tender Intelligence

Automated monitoring of Finnish public-sector tenders for CGI Finland. Reads
both Hilma (REST API) and tarjouspalvelu.fi (browser automation), filters with
CPV codes + keywords, summarises with OpenAI, routes to CGI departments via
an Excel-defined rule set, and emails a daily digest with attached tender
documents archived to SharePoint.

**Status (2026-04-27):** PoC code complete and locally verified end-to-end.
Headless Chrome verified on Azure B2s North Europe. Ready for handover to
the Azure team for production deployment.

- **Effort to production:** ~17–23 active developer days + 4-week shadow pilot, ~7–9 weeks elapsed (`docs/project_spec.md` § 12.4–12.7)
- **Running cost:** ~€30–50/month all-in (`docs/project_spec.md` § 5.1)
- **Pilot success gates:** 10 measurable criteria (`docs/project_spec.md` § 10.2)
- **Finnish procurement terms** for non-Finnish team members: `docs/project_spec.md` § 16

---

## Where to start, by audience

| If you are… | Read first | Then |
|---|---|---|
| **Azure / DevOps engineer about to deploy this** | [`deploy/README.md`](deploy/README.md) — the production handbook | [`docs/project_spec.md`](docs/project_spec.md) for full spec, [`docs/tasks.md`](docs/tasks.md) for the MVP checklist |
| **Stakeholder / product owner** | [`docs/mvp_requirements_stakeholder.md`](docs/mvp_requirements_stakeholder.md) (verbatim CGI requirements, Finnish) | [`docs/project_spec.md`](docs/project_spec.md) § 1–3 (executive summary + scope) |
| **Developer continuing the code** | [`.claude/CLAUDE.md`](.claude/CLAUDE.md) — technical deep-dive | The module under `app/` you're touching |
| **Trying it out locally for the first time** | [§ Run locally](#run-locally) below | The offline demo (`scripts/run_offline_demo.sh`) — no creds needed |
| **Editing routing rules** | [`config/routing_config.xlsx`](config/routing_config.xlsx) — open in Excel | [`docs/project_spec.md`](docs/project_spec.md) § 3.5 (ohjaustiedosto schema) |

---

## What this system does

Nightly pipeline (~7–15 minutes):

1. Query Hilma API for new notices (last 24 h, CPV-filtered)
2. Log into tarjouspalvelu.fi via Cloudia SSO + scrape global search
3. Merge + deduplicate the two sources
4. Classify (open competition / early signal / DPS / direct award / result)
5. AI-summarise relevant tenders (OpenAI)
6. Extract structured metadata (deadlines, scoring weights, contract included, reservations allowed)
7. Three-tier routing: CGI products (1A) → partner platforms (1B) → department keywords (2) → unmatched (3)
8. Download ZIP attachments → upload to SharePoint staging library
9. Build digest emails per department; in pilot, route to one reviewer
10. Persist state to SQLite; render minimal koontinäkymä; flush logs

See [`docs/project_spec.md`](docs/project_spec.md) § 4.2 for the full sequence.

---

## Data sources

| | Hilma (hankintailmoitukset.fi) | tarjouspalvelu.fi |
|---|---|---|
| Owner | Hansel Oy (state) | Cloudia / Mercell (commercial) |
| Access | Free REST API (subscribe at [developer portal](https://hns-hilma-prod-apim.developer.azure-api.net/)) | No API — browser automation only |
| Above-threshold tenders | ✓ (mandatory by law) | ✓ |
| Below-threshold tenders | rare | ✓ (often only here) |
| Full documents / attachments | ✗ | ✓ (ZIP download) |
| Q&A, evaluation criteria | ✗ | ✓ (per-tender tabs) |
| CPV codes, structured value | ✓ | ✗ |
| Winner names (awards) | ✓ | only in description text |

Both sources are needed for full coverage. `app/merge.py` reconciles them
on `notice_number` and falls back to fuzzy match on title + organisation.

---

## Repo layout

```
rfq-management/
├── app/                     ★ Production application (containerised)
│   ├── main.py              entry point — `python -m app.main`
│   ├── paths.py             centralised path resolution
│   ├── hilma.py             Hilma API client
│   ├── merge.py             Hilma + tarjouspalvelu deduplication
│   ├── storage.py           SQLite (tenders, awards, competitors)
│   ├── routing.py           three-tier routing engine
│   ├── cgi_products.py     products / partner platforms / competitors
│   ├── notify.py            digest builder + SMTP send + iCal attach
│   ├── summarize.py         OpenAI tender summaries
│   ├── extract.py           OpenAI metadata extraction
│   ├── analyze.py           winner / price / competitor extraction
│   ├── ical.py              calendar invite generator
│   ├── sharepoint.py        Graph API upload (3 modes)
│   ├── reply_tracker.py     STUB — Graph Mail polling for claim tracking
│   ├── dashboard.py         STUB — koontinäkymä HTML generator
│   └── logger.py
│
├── deploy/                  ★ Azure deployment artifacts
│   ├── README.md            production handbook (start here for ops)
│   ├── Dockerfile           Python 3.12 + Chrome + the three known gotchas
│   ├── .dockerignore
│   ├── infra/               Bicep IaC (skeleton — modules to fill in)
│   └── pipelines/           GitHub Actions (skeleton)
│
├── docs/                    Specifications, runbooks, architecture
│   ├── project_spec.md      authoritative spec (read this for "what to build")
│   ├── tasks.md             MVP checklist
│   ├── mvp_requirements_stakeholder.md   verbatim source requirements
│   ├── sharepoint_setup.md  Graph API auth walkthrough (3 modes)
│   ├── defender_runbook.md  Microsoft Defender for Storage enablement
│   └── *.html               architecture / process / cost diagrams (open in browser)
│
├── config/                  User-editable configuration
│   └── routing_config.xlsx  Tier 2 routing rules — non-technical CGI users edit this
│
├── scripts/                 Local-dev convenience
│   ├── run_demo.sh          live scrape with email + good AI model
│   ├── run_offline_demo.sh  replay saved data — no browser, no creds
│   └── run_comparison.sh    visible vs. headless parity check
│
├── tests/                   Smoke-test scripts (compare_runs, test_headless, test_anonymous)
├── tools/                   PoC / sales tooling — NOT deployed
│   ├── create_presentation.py + cgi_template.{pptx,potx} + presentation_assets/
│   └── streamlit_dashboard.py (untested local UI)
│
├── data/                    Runtime state — gitignored, auto-created
│   ├── tenders.db, scraper.log, downloads/, chrome_profile/, previews/, demo_results.json
├── scratch/                 Debug artifacts — gitignored
│
├── .env / .env.example      Credentials (.env gitignored)
├── requirements.txt         Production runtime deps
├── requirements-dev.txt     PoC tooling deps (Streamlit, python-pptx, Pillow)
└── README.md                You are here
```

The deployable surface is exactly `app/` + `deploy/` + `requirements.txt`
+ `config/`. Everything else is documentation, local-dev convenience,
or PoC tooling.

---

## Run locally

```bash
# First-time setup
cd ~/projects/rfq-management
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt          # runtime deps only
# pip install -r requirements-dev.txt    # add for Streamlit / PowerPoint tools

# Credentials (optional — most modes degrade gracefully without them)
cp .env.example .env
# edit .env — set HILMA_API_KEY at minimum; OPENAI_API_KEY for summaries;
# TARJOUSPALVELU_* for the live scraper; SMTP_* for real email send

# Offline demo — no browser, no creds, replays data/demo_results.json
./scripts/run_offline_demo.sh

# Live demo — logs into tarjouspalvelu.fi, sends real emails
./scripts/run_demo.sh

# Direct invocation
python -m app.main --mode=tenders         # tarjouspalvelu only
python -m app.main --mode=combined        # Hilma + tarjouspalvelu (production default)
python -m app.main --mode=analytics       # award results / winners
python -m app.main --mode=offline         # replay data/demo_results.json
```

Every module under `app/` resolves paths through `app/paths.py` — `.env`,
`config/routing_config.xlsx`, and everything in `data/` are found from
the repo root regardless of which directory you invoke from.

---

## Tech stack

- **Python 3.12** — single language across scrape, AI, routing, email
- **undetected-chromedriver 3.5.5** — only tool that bypasses Cloudflare Turnstile reliably (Playwright variants tested, all failed)
- **OpenAI SDK** — gpt-4o-mini for summaries, gpt-4.1-nano for cheap dev runs (configurable via `OPENAI_MODEL` env)
- **MSAL (Microsoft Authentication Library)** — for Graph API auth (SharePoint upload, planned reply-tracker)
- **openpyxl** — reads `config/routing_config.xlsx` so non-technical users can edit routing rules without a code change
- **SQLite** — local database, sufficient for this scale; backs up to Blob in production

Why not UiPath / Power Automate / etc.: all targets are web. undetected-chromedriver
bypasses the bot detection both alternatives would also have to defeat. Python
keeps data flowing directly into the AI pipeline without serialisation hops.
No license cost.

---

## Project status & background

- **Stakeholder:** CGI Finland tender-collection section (specific PO TBD)
- **SME:** Riku Turkia (deep tarjouspalvelu.fi knowledge)
- **Developer:** Ville Pajala
- **MVP demo to CGI:** done 2026-04-13 (well-received; project pivoted from "alert system" to "tender intelligence platform")
- **Headless / Azure-IP feasibility:** verified 2026-04-23 on B2s North Europe — Cloudflare Turnstile passes, full page loads
- **Refactor for handover:** done 2026-04-27 (this commit) — production code under `app/`, deployment under `deploy/`

For full status, decisions log, open questions, and effort estimates see
[`docs/project_spec.md`](docs/project_spec.md). For day-to-day MVP progress
see [`docs/tasks.md`](docs/tasks.md).

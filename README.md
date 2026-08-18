# Tender Intelligence

> **Azure / DevOps engineer?** Start here:
> 1. [`deploy/README.md`](deploy/README.md) — the production deployment handbook (13-phase roadmap with options + definitions of done)
> 2. [`docs/project_spec.md`](docs/project_spec.md) — full functional spec
> 3. **Tender Intelligence estimate.docx** (handed over separately) — agreed scope and effort estimate
>
> The rest of this README is orientation for other audiences. You should not need to run the application locally — see Phase 11 of the deploy handbook for the smoke-test approach.

Automated monitoring of Finnish public-sector tenders for CGI Finland. Reads
both Hilma (REST API) and tarjouspalvelu.fi (browser automation), filters with
CPV codes + keywords, summarises with an in-tenant AI service, routes to CGI
departments via an Excel-defined rule set, and emails a daily digest with
attached tender documents archived to SharePoint.

**Status (2026-04-29):** PoC code complete and locally verified end-to-end.
Headless Chrome verified on Azure B2s North Europe. Ready for handover to the
Azure team for production deployment.

- **Agreed scope:** **Scenario A — Strict stakeholder MVP** (drops reply-tracker Job + koontinäkymä HTML; both deferred to Phase 2)
- **Effort to production:** **13.0–14.5 active developer days** (~11 days Azure team + ~2–3 days application code) + 4-week shadow pilot, ~6–8 weeks elapsed
- **Running cost:** ~€45–90/month all-in (incl. Azure SQL Serverless + AI inference + Container Apps Job + Defender + Storage + ACR)
- **Pilot success gates:** 10 measurable criteria (`docs/project_spec.md` § 10.2)
- **Architecture + process diagrams:** `docs/Tender_Intelligence_Architecture_Process.html` (Mermaid, open in browser)
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
3. Per matched tender during scraping: open detail page → 6 tabs → AI metadata extract → ZIP download → SharePoint upload (gated by env flags)
4. Merge + deduplicate the two sources
5. Classify (open competition / early signal / DPS / direct award / result)
6. Persist to Azure SQL Database
7. AI-summarise relevant tenders (OpenAI)
8. Three-tier routing: CGI products (1A) → partner platforms (1B) → department keywords (2) → unmatched (3)
9. Build digest emails per department; in pilot, route to one reviewer; attach iCal with deadlines
10. Award analysis on results-tenders → competitor + pricing intelligence reports
11. Render the read-only koontinäkymä HTML (planned, stub today)

See [`docs/project_spec.md`](docs/project_spec.md) § 4.2 for the high-level
sequence and the full Mermaid diagrams below for everything in detail.

## Architecture & process diagrams

Open [`docs/Tender_Intelligence_Architecture_Process.html`](docs/Tender_Intelligence_Architecture_Process.html)
in any browser (Mermaid loads from CDN). Six diagrams + supporting tables:

| # | Diagram | What it shows |
|---:|---|---|
| 1 | System architecture | Azure tenant + external services, both Container Apps Jobs, all data stores, secrets/auth flow |
| 2 | Process flow — high level | Sequence diagram from cron trigger through container exit |
| 3 | **Process — detailed step-by-step** | **Every action and decision branch in `app/main.py`, ~100 nodes, including the per-tender nested loop where detail scrape + metadata extract + ZIP download + SharePoint upload all happen** |
| 4 | Reply tracker process | The second Job: poll mailbox → parse `[TENDER-id]` → update claim → mark read |
| 5 | Data lifecycle & analytics | Hilma + tarjouspalvelu → Azure SQL → Power BI / ad-hoc T-SQL / future ML |
| 6 | Cost impact | SQLite-in-Blob vs Azure SQL comparison with ~€45–90/mo all-in figure |

Quick view from this terminal (WSL):
```bash
explorer.exe docs/Tender_Intelligence_Architecture_Process.html
```

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

> *Developer use only. Azure / DevOps engineers should not need to run anything locally — the deployment pipeline (`deploy/pipelines/build-and-push.yml`) builds the container image in CI, and the smoke test runs in Azure (Phase 11 of the deployment handbook).*

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

## Demo vs production — same code, different env vars

The codebase is single-path. The same `python -m app.main` runs the demo
on a laptop and the production Job in Azure. What differs is the env
vars the process sees. No code branches, no separate "dev mode" / "prod
mode" paths.

| Behaviour | Demo (laptop, no Azure) | Production (Azure Container Apps Job) |
|---|---|---|
| Scope of tarjouspalvelu scrape | All Finland (`/Default/Index`) by default; pass `helsinki` / `espoo` / etc. as a positional arg to restrict | All Finland (`/Default/Index`) |
| Database | `DATABASE_URL` unset → SQLite at `data/tenders.db` | `DATABASE_URL=mssql+pyodbc://…` → Azure SQL Database |
| AI provider | `AZURE_OPENAI_ENDPOINT` unset → OpenAI direct (uses `OPENAI_API_KEY`) | `AZURE_OPENAI_ENDPOINT=https://…` → Azure OpenAI / AI Foundry inside CGI tenant |
| AI model name | `OPENAI_MODEL=gpt-4.1-nano` (cheap dev) or `gpt-4o-mini` | `OPENAI_MODEL=<your-deployment-name>` (the deployment chosen at AOAI provisioning) |
| ZIP attachments | Local `data/downloads/` only (`ENABLE_SHAREPOINT_UPLOAD=0`) | `ENABLE_SHAREPOINT_UPLOAD=1` + Graph API creds → CGI SharePoint staging library |
| Email send | No SMTP credentials → HTML preview written to `data/previews/` | `SMTP_*` set → real send via CGI M365 |
| Recipients | Per-department BU emails from `routing_config.xlsx` | Pilot: `REVIEWER_MODE=1` + `REVIEWER_EMAIL` → all digests to one reviewer. Post-pilot: `REVIEWER_MODE=0` → BU leaders direct |

Concrete examples below.

### Demo (any laptop, zero Azure)

```bash
# 1. One-off setup
git clone https://github.com/VillePajala/rfq-management
cd rfq-management
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Optional: set OPENAI_API_KEY in .env if you want AI summaries
cp .env.example .env

# 3. Run the offline demo — no browser, no creds, replays saved tender data
python -m app.main --mode=offline
```

What you get: 100 tenders from a previous run replayed through the full
pipeline (classify, route, email previews to `data/previews/`, summary
counts to console). ~30 seconds. Works on any OS.

### Live demo (laptop, with credentials)

Same as above, plus credentials in `.env`:

```bash
HILMA_API_KEY=...                                    # free, get one at hns-hilma-prod-apim.developer.azure-api.net
OPENAI_API_KEY=...                                   # for AI summaries
TARJOUSPALVELU_EMAIL=you@cgi.com                     # for full detail tabs + ZIP downloads
TARJOUSPALVELU_PASSWORD=...
SMTP_USER / SMTP_PASSWORD / SMTP_FROM (optional)     # for real email send
```

Then:

```bash
python -m app.main --mode=combined          # Hilma API + tarjouspalvelu scrape (all Finland)
python -m app.main --mode=combined helsinki # restrict tarjouspalvelu side to Helsinki only (dev / testing)
python -m app.main --mode=tenders           # tarjouspalvelu only (no Hilma)
python -m app.main --mode=analytics         # award results / winners (price + competitor intelligence)
```

### Production (Azure Container Apps Job — Azure team's territory)

Same `python -m app.main --mode=combined`, but inside the container with
production env vars sourced from Key Vault. Conceptually:

```bash
DATABASE_URL='mssql+pyodbc://server.database.windows.net,1433/tenderdb?driver=ODBC+Driver+18+for+SQL+Server&Authentication=ActiveDirectoryMsi' \
AZURE_OPENAI_ENDPOINT='https://cgi-aoai.openai.azure.com/' \
AZURE_OPENAI_API_VERSION='2024-08-01-preview' \
OPENAI_MODEL='gpt-4o-mini-deployment' \
HILMA_API_KEY='...' \
TARJOUSPALVELU_EMAIL='svc-tender-agent@cgi.com' \
TARJOUSPALVELU_PASSWORD='...' \
ENABLE_SHAREPOINT_UPLOAD=1 \
GRAPH_TENANT_ID='...' GRAPH_CLIENT_ID='...' GRAPH_CLIENT_SECRET='...' \
SHAREPOINT_SITE_HOST='cgi.sharepoint.com' \
SHAREPOINT_SITE_PATH='/sites/TenderAgent' \
ENABLE_EMAIL=1 \
SMTP_USER='svc-tender-agent@cgi.com' SMTP_PASSWORD='...' SMTP_FROM='svc-tender-agent@cgi.com' \
REVIEWER_MODE=1 \
REVIEWER_EMAIL='reviewer@cgi.com' \
python -m app.main --mode=combined
```

In practice the Azure team does not type these on the command line —
they live in Key Vault and are surfaced as Container Apps secret
references in the Bicep Job spec. See `deploy/README.md` Phase 4
(secrets) and Phase 5 (Container hosting).

---

## Modes at a glance — minimum env vars per mode

| Mode | What you get | Minimum env vars |
|---|---|---|
| **Offline demo** (`--mode=offline`) | Full pipeline replayed against `data/demo_results.json`. Routing + email previews work. No browser, no network beyond AI. | None required. With `OPENAI_API_KEY` set you also get fresh AI summaries. |
| **Live demo, Hilma only** (`--mode=tenders` or `combined` with no tarjouspalvelu creds) | Real Hilma fetch, no tarjouspalvelu scrape, no SharePoint upload. Email saved as preview. | `HILMA_API_KEY` + (optional) `OPENAI_API_KEY` |
| **Live demo, full** (`--mode=combined`) | Both sources, AI summaries, email preview to disk, ZIPs to local `data/downloads/` | `HILMA_API_KEY` + `TARJOUSPALVELU_EMAIL/PASSWORD` + `OPENAI_API_KEY` |
| **Pilot production** (Container Apps Job, REVIEWER_MODE=1) | All sources + Azure SQL + Azure OpenAI + SharePoint upload + real email send to ONE reviewer | All credentials + `DATABASE_URL` + `AZURE_OPENAI_ENDPOINT` + all `ENABLE_*=1` + `REVIEWER_MODE=1` + `REVIEWER_EMAIL` |
| **Live production** (post-pilot, REVIEWER_MODE=0) | Same as pilot but digests go to BU leaders per `routing_config.xlsx` | Same as pilot, except `REVIEWER_MODE=0` |

---

## Run parameters reference (every env var)

The full list, grouped by purpose. The same groups appear in `.env.example`.

### 1. Source credentials

| Var | Required? | Default | What it does |
|---|---|---|---|
| `HILMA_API_KEY` | Recommended (free) | — | API key for Hilma's AVP-Read product. Without it, Hilma fetch is skipped. |
| `TARJOUSPALVELU_EMAIL` | Optional | — | Login for tarjouspalvelu.fi. Without it, scraper can read public listings only — no detail tabs, no ZIP downloads. |
| `TARJOUSPALVELU_PASSWORD` | Optional | — | Same. |

### 2. AI provider (pick ONE)

| Var | Required? | Default | What it does |
|---|---|---|---|
| `OPENAI_API_KEY` | For demo | — | OpenAI direct. Used when `AZURE_OPENAI_ENDPOINT` is empty. |
| `AZURE_OPENAI_ENDPOINT` | For prod | — | Presence of this triggers AzureOpenAI client (instead of OpenAI direct). |
| `AZURE_OPENAI_API_VERSION` | Optional | `2024-08-01-preview` | API version for Azure OpenAI calls. |
| `AZURE_OPENAI_API_KEY` | If using Azure OpenAI without Managed Identity | — | API key for Azure OpenAI. (Production should prefer MI.) |
| `OPENAI_MODEL` | Optional | `gpt-4.1-nano` | OpenAI direct: model ID. Azure OpenAI: deployment name. |

### 3. Database

| Var | Required? | Default | What it does |
|---|---|---|---|
| `DATABASE_URL` | For prod | `sqlite:///data/tenders.db` | SQLAlchemy URL. Set to `mssql+pyodbc://…` for Azure SQL. Empty = SQLite local. |

### 4. Email

| Var | Required? | Default | What it does |
|---|---|---|---|
| `SMTP_HOST` | If `ENABLE_EMAIL=1` | `smtp.gmail.com` | SMTP server. |
| `SMTP_PORT` | If `ENABLE_EMAIL=1` | `587` | SMTP port. |
| `SMTP_USER` | If `ENABLE_EMAIL=1` | — | SMTP username. Without it, emails are written to `data/previews/`. |
| `SMTP_PASSWORD` | If `ENABLE_EMAIL=1` | — | SMTP password (Gmail App Password or M365 relay creds). |
| `SMTP_FROM` | Optional | = `SMTP_USER` | Sender address. |
| `REVIEWER_MODE` | Pilot only | `0` | `1` = redirect every digest to one reviewer with a banner. |
| `REVIEWER_EMAIL` | If `REVIEWER_MODE=1` | — | The reviewer's mailbox. |

### 5. SharePoint upload (Graph API)

| Var | Required? | Default | What it does |
|---|---|---|---|
| `GRAPH_TENANT_ID` | If `ENABLE_SHAREPOINT_UPLOAD=1` | — | Entra tenant GUID (or `consumers` for personal MSA). |
| `GRAPH_CLIENT_ID` | If `ENABLE_SHAREPOINT_UPLOAD=1` | — | App registration client ID. |
| `GRAPH_CLIENT_SECRET` | For app-only auth | — | Presence enables app-only (no user prompt). Absence triggers device-code delegated auth. |
| `SHAREPOINT_SITE_HOST` | For SharePoint (vs OneDrive) | — | e.g. `cgi.sharepoint.com`. Empty → uploads go to personal OneDrive. |
| `SHAREPOINT_SITE_PATH` | For SharePoint | — | e.g. `/sites/TenderAgent`. |
| `SHAREPOINT_FOLDER` | Optional | `Tender-Staging` | Folder name within the library. |

### 6. Feature toggles

| Var | Default | What `1` does |
|---|---|---|
| `ENABLE_EMAIL` | `0` | Real SMTP send instead of writing previews to disk |
| `ENABLE_SUMMARIZATION` | `1` | OpenAI summary per relevant tender |
| `ENABLE_ANALYSIS` | `1` | Award winner / price / competitor extraction for `result` tenders |
| `ENABLE_DETAIL_SCRAPE` | `0` | Open detail page per tender; scrape 6 tabs |
| `ENABLE_DOWNLOAD_ATTACHMENTS` | `0` | Download ZIP per tender (requires login) |
| `ENABLE_METADATA_EXTRACTION` | `0` | Extra OpenAI call to extract scoring/contract/reservations |
| `ENABLE_SHAREPOINT_UPLOAD` | `0` | Upload downloaded ZIPs to OneDrive/SharePoint |

### 7. Limits & tuning

| Var | Default | What it does |
|---|---|---|
| `HILMA_DAYS` | `1` | Hilma look-back window in days |
| `SUMMARIZE_COUNT` | `10` | Max tenders to summarise per run (caps OpenAI spend) |
| `ANALYSIS_COUNT` | `20` | Max award-results to analyse per run |
| `DETAIL_SCRAPE_COUNT` | `0` (no cap) | Cap detail scrapes for time-box runs |
| `MAX_EMAILS` | `0` (no cap) | Cap number of department digest emails sent |

### 8. Runtime

| Var | Default | What it does |
|---|---|---|
| `HEADLESS` | `1` | Headless Chrome (always 1 in containers; 0 to watch the browser locally) |
| `DEMO_PAUSE` | `0` | Pause for Enter key at demo checkpoints (only when `HEADLESS=0`) |
| `OUTPUT_JSON` | `data/demo_results.json` | Path to write the full run output to |

---

## Tech stack

- **Python 3.12** — single language across scrape, AI, routing, email
- **undetected-chromedriver 3.5.5** — only tool that bypasses Cloudflare Turnstile reliably (Playwright variants tested, all failed)
- **OpenAI SDK** — same library, two providers selected by env (`AZURE_OPENAI_ENDPOINT` set → AzureOpenAI client; otherwise OpenAI direct). Model configurable via `OPENAI_MODEL` env
- **MSAL (Microsoft Authentication Library)** — Graph API auth for SharePoint upload
- **openpyxl** — reads `config/routing_config.xlsx` so non-technical users can edit routing rules without a code change
- **SQLAlchemy** — backend-agnostic database access. `DATABASE_URL` env: unset → SQLite at `data/tenders.db` (demo); set → whatever (Azure SQL via pyodbc in production)

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

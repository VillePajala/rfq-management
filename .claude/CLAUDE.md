# Tender Intelligence Project

CGI project to automate Finnish public sector tender monitoring from tarjouspalvelu.fi. Scrapes tenders, filters noise, AI-summarizes, routes to CGI departments via three-tier system, sends email notifications, and builds price/competitor intelligence.

## Project Structure

```
rfq-management/
├── demo_scraper.py          # Main pipeline: scrape → classify → summarize → route → notify → analyze
├── hilma.py                 # Hilma API client (hankintailmoitukset.fi) — structured tender data, CPV codes
├── merge.py                 # Merge + deduplicate tenders from Hilma and tarjouspalvelu.fi
├── storage.py               # SQLite: tenders, award_analysis, competitors tables. Classification logic.
├── routing.py               # Three-tier routing: Tier 1 (products) + Tier 2 (keywords from Excel) + Tier 3
├── cgi_products.py          # CGI own products (34), partner platforms (75), competitors (20)
├── notify.py                # Email: one HTML digest per department via SMTP
├── summarize.py             # OpenAI: tender summaries (model configurable via OPENAI_MODEL env)
├── analyze.py               # Award results analysis: extract winners, prices, build competitor profiles
├── logger.py                # File logger — writes to scraper.log
├── app.py                   # Streamlit web dashboard (not tested recently — may need fixes)
├── create_presentation.py   # Generates CGI PowerPoint (outputs to project dir + Windows desktop)
├── run_demo.sh              # Demo script: fast run with emails enabled, good AI model
├── run_offline_demo.sh      # Offline demo: replays saved data, no browser needed
├── routing_config.xlsx      # Tier 2 routing rules (auto-generated, editable by non-technical users)
├── email_sample.html        # Mock email for presentation screenshot
├── cgi_products.py          # Product/platform/competitor matching with word boundary support
├── tenders.db               # SQLite database (auto-created, gitignored)
├── scraper.log              # Run log (auto-created, gitignored)
├── chrome_profile/          # Persistent Chrome profile (Zscaler certs, session)
├── cgi_template.pptx        # CGI PowerPoint template (converted from .potx)
├── .env                     # Credentials (NEVER committed)
├── .env.example             # Template for credentials
├── .gitignore               # Excludes .env, DB, Chrome profile, screenshots, logs
└── README.md                # Full project documentation (may be outdated — CLAUDE.md is authoritative)
```

## What Actually Works (verified 2026-04-09)

| Feature | Status | Notes |
|---|---|---|
| Chrome automation + Cloudflare bypass | ✅ Working | undetected-chromedriver, `--headless=new` verified (2026-04-22) from Finnish residential IP |
| Login via Cloudia SSO | ✅ Working | Sometimes needs retry, username may double-enter |
| Global search (all Finland) | ✅ Working | 100 tenders from 68 orgs in test run |
| Notice type pre-filtering | ✅ Working | Only open tenders, no results/awards |
| Pagination | ✅ Working | 5 pages × 20 = 100 tenders per run |
| Classification (open/signal/closed) | ✅ Working | 92 open + 8 signals from 100 |
| Three-tier routing | ✅ Working | Tier 1B: 2 matches (Wilma, Suomi.fi). Tier 2: 93. Tier 3: 5. |
| Word boundary matching | ✅ Working | Fixed SAP/SAS/Kanta false positives |
| AI summarization | ✅ Working | Tested with gpt-4o-mini. Default now gpt-4.1-nano for dev |
| Email per department | ✅ Working | 8 department emails sent in test |
| SQLite storage + dedup | ✅ Working | Tracks new vs seen tenders |
| CGI product/platform list | ✅ Working | 50+ own products, 90+ platforms, 20 competitors |
| Detail page (full access) | ✅ Working | Click-navigate from listings preserves login session. driver.get(url) still loses session. |
| Detail page scraping code | ✅ Refactored | Per-page scraping (no pagination bug). Clicks through all tabs (Summary, Publication Docs, Q&A, Terms, Procurement Object, Persons in Charge). Needs live testing. |
| Offline demo mode | ✅ Working | `--mode=offline` replays from demo_results.json, no browser needed |
| Login retry | ✅ Working | Retries login up to 3 times before falling back to public data |
| Award/price analysis | ⚠️ Untested | Code exists, never run end-to-end with working AI |
| Streamlit dashboard | ⚠️ Untested | May need fixes after routing refactor |
| Scheduling | ❌ Not built | Manual runs only |
| Tier 1A own product alerts | ❌ No matches yet | Code works but no CGI products appeared in 100-tender sample |

## Critical: Login Flow

This was the hardest part. Getting any step wrong breaks login silently.

1. Navigate to `https://tarjouspalvelu.fi/Default/Index` (global portal, NOT org-specific)
2. Enter email in `input#user` field (top-right corner)
3. Click `button#continue` — triggers SSO redirect
   - **NOT `#oldlogin`** — that's local login, always fails with "Check the username"
4. Redirects to `login.cloudia.net` — a **Vaadin app**, not standard HTML
5. `input#username` — **check if pre-filled** from URL parameter. If already correct, don't re-enter (causes doubling)
6. `#password input[type='password']` — nested inside Vaadin custom component `div#password`. Clear with JS first: `driver.execute_script("arguments[0].value = '';", pw_field)`
7. Click `div#login-btn` using **Selenium ActionChains** (move_to_element + click)
   - JavaScript `.click()` does NOT work on Vaadin buttons
   - Must be a native simulated mouse click
8. Wait ~12 seconds for redirect back to tarjouspalvelu.fi
9. If stuck on `login.cloudia.net`, manually navigate to `tarjouspalvelu.fi/Default/Index`

**Login pitfalls discovered:**
- Username field gets pre-filled from URL `?username=email` — if we also type it, it doubles
- Password field needs JS clear before typing (Vaadin quirk)
- ActionChains click is required for Vaadin buttons (JS click doesn't fire events)

## Detail Page Scraping

Login session persists when **clicking a tender link from within the page** (ActionChains click on `a.tp-list__row`). Session is **LOST** with `driver.get(url)`.

**Current implementation (refactored 2026-04-10):**
1. Detail scraping happens **per-page during extraction** (not after all pages)
2. For each tender on the current page: ActionChains click → detail page
3. On detail page, clicks through all sidebar tabs to collect full content:
   - Summary, Publication documents, Questions and answers
   - Other terms and conditions, Procurement object, Persons in charge
4. Each tab's text stored separately in `tender["detail_tabs"]`
5. All tab text combined into `tender["detail_text"]` for AI consumption
6. `driver.back()` to return to listings, repeat for next tender on same page
7. Then paginate to next page

**Tab selectors:** `button.sidebar__item` with IDs `sidebar0` through `sidebar6`. Tabs load content via AJAX into `div.content`. Disabled tabs (like Activities) are automatically skipped.

**Configuration:** `ENABLE_DETAIL_SCRAPE=1` and `DETAIL_SCRAPE_COUNT=N` (0 = all per page)

## Global Search (logged in)

- URL: `tarjouspalvelu.fi/Default/Index` — shows ALL Finnish tenders (~5,215)
- 20 per page (50 setting may not stick after filter application)
- Pagination via `HaeSivu(pageNum)` JavaScript function
- Notice type filtering via `ilmoitustyypit-multiselect` Select2 dropdown
- Same `a.tp-list__row` selectors as org-specific pages
- Org field has `<span class="sr-only">Open the call for tenders: </span>` to strip

**Available search filters (on the page):**
- Notice type: Competition (57), Planning (56), DPS (61), National (1), Request for info (26)
- Procurement category: Service (2), Health (3), Works (5), Supplies (1), etc.
- CPV codes, NUTS codes, organisation, date ranges

**Two scraping modes:**
- `--mode=tenders` — filters to open Competition + Planning + DPS types only
- `--mode=analytics` — filters to Results + Awards only (for price/competitor analysis)
- `--mode=all` — no filtering

## Three-Tier Routing

Implemented in `routing.py`, uses `cgi_products.py` for Tier 1:

| Tier | Trigger | Action | Status |
|---|---|---|---|
| 1A | CGI own product name in text (Aromi, Raindance, Titania...) | CRITICAL alert | Working in code, 0 matches in test (expected — rare in random 100) |
| 1B | Partner platform name in text (SAP, Azure, ServiceNow...) | HIGH alert | Working — caught Wilma and Suomi.fi correctly |
| 2 | Keywords match department rules in routing_config.xlsx | Email digest | Working — 93/100 matched |
| 3 | No match | Dashboard only, no email | Working — 5/100 |

**Word boundary matching:** Short keywords (SAP, SAS, AWS, etc.) use regex `\b` boundaries to prevent false positives in Finnish words. "Kanta" replaced with "Kanta-palvelu"/"Kanta-järjestelmä" to avoid matching region names.

**Tier 1 alerts show in console** but are NOT yet sent as separate emails — they go into the regular department routing.

## Environment Variables (.env)

```
TARJOUSPALVELU_EMAIL=       # Cloudia SSO login email
TARJOUSPALVELU_PASSWORD=    # Cloudia SSO password
OPENAI_API_KEY=             # OpenAI API key
OPENAI_MODEL=gpt-4.1-nano  # Default model (cheap for dev). Use gpt-4o-mini for production.
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=                  # Email sender address
SMTP_PASSWORD=              # Gmail App Password
SMTP_FROM=                  # Sender address
HILMA_API_KEY=              # Hilma API key (free, from developer portal)
```

## Feature Toggles

| Variable | Default | What it does |
|---|---|---|
| `ENABLE_EMAIL` | `0` | Email notifications (OFF to prevent spam in dev) |
| `ENABLE_SUMMARIZATION` | `1` | AI summarization |
| `ENABLE_ANALYSIS` | `1` | Award results analysis |
| `ENABLE_DETAIL_SCRAPE` | `0` | Detail page scraping (slow, OFF in dev) |
| `SUMMARIZE_COUNT` | `10` | Max tenders to summarize per run |
| `ANALYSIS_COUNT` | `20` | Max results to analyze per run |
| `DETAIL_SCRAPE_COUNT` | `0` | Max detail pages (0 = all that passed filter) |
| `OPENAI_MODEL` | `gpt-4.1-nano` | AI model (cheapest for dev) |

## How to Run

```bash
# Development run (no emails, cheap AI, fast)
source venv/bin/activate
rm -f tenders.db
python demo_scraper.py --mode=tenders

# Demo run (emails ON, good AI model)
./run_demo.sh

# Offline demo (no browser — replays from saved demo_results.json)
./run_offline_demo.sh

# Combined run (Hilma API + tarjouspalvelu.fi — best coverage)
HILMA_DAYS=7 python demo_scraper.py --mode=combined

# Analytics run (award results for price/competitor intelligence)
python demo_scraper.py --mode=analytics

# Dashboard
streamlit run app.py

# Regenerate PowerPoint (saves to project + Windows desktop)
python create_presentation.py
```

## Presentation

PowerPoint at `Tender_Intelligence_CGI.pptx` and Windows desktop. Generated from `create_presentation.py` using CGI template (`cgi_template.pptx`). 9 slides:

1. Title
2. Email example (screenshot of sample email with AI summaries)
3. Routing config (screenshot of Excel)
4. Process diagram (pipeline + 3-tier routing)
5. Tarjouspalvelu.fi access (pipeline, data available, challenges solved)
6. Filter funnel (5,000 → relevant, "need your input" flags)
7. AI costs per task (Basic/Standard/Advanced models)
8. Console output (what a run looks like)
9. To Get Started (what we need from them + next steps)

**Important:** User has manually adjusted some slide positions in PowerPoint. The generator preserves slide 2 layout edits. If user edits other slides, re-read positions with the analysis script before regenerating.

## What Needs Stakeholder Input

1. **Procurement categories** — which ones does CGI bid on? (Service, Health, Works, all?)
2. **CGI product list** — verify/extend the list in cgi_products.py (Aromi, Raindance, Titania — what else?)
3. **Department contacts** — who receives which tenders? (name + email per CGI business unit)
4. **Keywords per department** — what terms define each department's area?
5. **Service account** — dedicated tarjouspalvelu.fi login (not personal account)

## Demo Preparation

**Before any demo, do a pre-run to generate fresh fallback data:**

```bash
# 1. Do a live run to capture fresh data
source venv/bin/activate
rm -f tenders.db
export ENABLE_EMAIL=0
export ENABLE_SUMMARIZATION=1
export SUMMARIZE_COUNT=20
export OPENAI_MODEL=gpt-4o-mini
python demo_scraper.py --mode=tenders

# 2. Verify demo_results.json was generated
ls -la demo_results.json

# 3. Test the offline replay (this is your demo fallback)
rm -f tenders.db
./run_offline_demo.sh
```

**Demo flow (recommended order):**
1. Open `email_sample.html` in browser — "This is what your team gets every morning"
2. Open `routing_config.xlsx` — "You control routing, no code needed"
3. Run `./run_offline_demo.sh` — shows the full pipeline in ~30 seconds, no browser risk
4. Show PowerPoint slides if they want architecture details
5. Live run (`./run_demo.sh`) only if they specifically ask — have fallback ready

**If live demo login fails:** Don't panic. Switch to `./run_offline_demo.sh` and say "Let me show you with the data we captured earlier." The pipeline output is identical.

## Next Steps (prioritized)

1. **Test detail page scraping** — refactored to per-page with tab clicking, needs live run with ENABLE_DETAIL_SCRAPE=1
2. **Test demo run** — run `./run_demo.sh`, verify emails arrive with AI summaries
3. **Test analytics mode** — run `--mode=analytics` to verify price/competitor extraction
4. **Fix Streamlit dashboard** — likely broken after routing refactor
5. **Implement Tier 1 separate email** — critical alerts should be a distinct urgent email, not mixed into department digests
6. **Expand pagination** — currently 5 pages (100 tenders). Production needs all pages.
7. **Production deployment** — Azure Container Apps Jobs with headless Chrome, scheduled cron trigger, CGI service account (Xvfb no longer needed — `--headless=new` verified 2026-04-22)

## People

- **Riku Turkia** — SME, deep knowledge of tarjouspalvelu.fi platform
- **CGI stakeholder** — TBD, from the section responsible for tender collection
- **Ville Pajala** — developer building this PoC

## Production Deployment (Option 1: Azure VM)

Target: single Azure VM running nightly scheduled scrapes.

**Infrastructure:**
```
Azure Container Apps Job (schedule-triggered, Python 3.12 image)
├── Python 3.12 + Chrome + undetected-chromedriver (headless=new)
├── Scheduled trigger: runs --mode=combined at 06:00 EET/EEST daily
├── SQLite in Blob Storage (loaded on start, flushed on exit)
├── ZIP attachments → Blob Storage → SharePoint (via Graph)
└── Outputs:
    ├── SharePoint (via Microsoft Graph API) — ZIPs + structured data
    ├── CGI SMTP / Microsoft 365 — email notifications
    └── Optionally: Azure SQL if dashboard needed
```

**Monthly cost estimate (personal Azure account):**

| Item | Cost |
|---|---|
| VM B2s (24/7) | ~€30 |
| Disk 30 GB SSD | ~€5 |
| OpenAI API (300 tenders, gpt-4o-mini) | ~€20-30 |
| Hilma API | Free |
| Network / data transfer | ~€1 |
| **Total** | **~€55-65/month** |

Note: if VM is deallocated after each run (~10 min/day), compute drops to ~€1-2/month. Total ~€25-35/month. Azure free tier gives €200 credit for first month (covers 3-5 months of testing).

**Setup steps:**
1. Create Azure VM (Ubuntu 22.04, B2s, allow SSH)
2. Install: `apt install python3 python3-venv xvfb chromium-browser`
3. Clone repo: `git clone https://github.com/VillePajala/rfq-management.git`
4. Create venv, install deps: `pip install -r requirements.txt`
5. Copy `.env` with production credentials (service account, CGI SMTP)
6. Install Zscaler certs into Chrome NSS database (if on CGI network)
7. Test: `xvfb-run python demo_scraper.py --mode=combined`
8. Add cron: `0 6 * * * cd /home/user/rfq-management && xvfb-run python demo_scraper.py --mode=combined`

**What CGI needs to provide:**
- Azure subscription (or approval to use personal)
- Service account for tarjouspalvelu.fi
- CGI SMTP server details (or M365 app registration for Graph API mail)
- SharePoint site/library for document storage
- Department contacts + emails for routing (real ones, not test)
- Procurement categories and CPV codes for filtering
- Security review: credential storage, data handling

**What's missing before production:**
- `requirements.txt` (not yet generated)
- SharePoint upload module
- CGI SMTP / M365 mail integration
- Proper logging and error alerting (email on failure)
- Health monitoring (did the nightly run succeed?)

## Future Ideas

**Two-pass selective detail scraping:** Instead of detail-scraping all tenders (slow) or a fixed count (random), use a two-pass approach: (1) scrape all listings and AI-summarize from short descriptions, (2) filter to relevant-only based on AI verdict, (3) go back and detail-scrape only those, (4) re-summarize with richer data. This would mean ~15 detail pages instead of 100. Prerequisite: AI relevance classification must be reliable enough — a false negative means missing a good tender's detail data. The per-page architecture already supports this; the main work is keeping the browser open between passes and paginating back to find specific tenders by tp_id.

## Key Technical Decisions (for future reference)

- **undetected-chromedriver** — only tool that bypasses Cloudflare Turnstile. Tested Playwright (5 variants), all failed.
- **Zscaler SSL** — import certs into Chrome NSS database (`~/.pki/nssdb/`). Do NOT use `--ignore-certificate-errors` — Cloudflare detects it.
- **Headless mode is the default as of 2026-04-22.** `--headless=new` + `undetected-chromedriver` 3.5.5 bypasses Cloudflare Turnstile from a Finnish residential IP. Azure datacenter-IP verification still pending (see Known Risks #4 in README). Historical note: early testing concluded "headless blocked" — that was pre-Chrome-109 and older uc versions; the combo now works.
- **ActionChains for Vaadin** — Cloudia login uses Vaadin framework. JS click doesn't work. Must use Selenium ActionChains.
- **Word boundary matching** — short product names (SAP, SAS) match Finnish words. Use regex `\b` boundaries.
- **Session persistence** — login session only persists when clicking links from within the page. `driver.get(url)` loses the session.

## Hilma API (hankintailmoitukset.fi)

Hilma is the official Finnish public procurement notice channel, managed by Hansel Oy. It has a **free public REST API** (no scraping needed).

**Developer portal:** https://hns-hilma-prod-apim.developer.azure-api.net/
**GitHub docs:** https://github.com/Hankintailmoitukset/hilma-api
**Authentication:** Self-service registration at developer portal, subscribe to AVP-Read product, instant API key (`Ocp-Apim-Subscription-Key` header)
**Cost:** Free, commercial use allowed
**SSL:** Requires `verify=False` in requests due to Zscaler SSL interception on CGI network

**Working endpoints (verified 2026-04-13):**

| Endpoint | Method | Purpose |
|---|---|---|
| `POST /avp/eformnotices/docs/search` | POST | Search eForms notices (current, 149k+ notices) |
| `GET /avp/eformnotices` | GET | Get eForms index field definitions (85 fields) |
| `POST /avp/notices/docs/search` | POST | Search legacy notices (frozen at Aug 2023, 105k notices) |
| `GET /avp/notices` | GET | Get legacy index field definitions (45 fields) |

**Base URL:** `https://api.hankintailmoitukset.fi`

**Search uses Azure Search syntax** (POST with JSON body):
```python
requests.post(
    "https://api.hankintailmoitukset.fi/avp/eformnotices/docs/search",
    headers={"Ocp-Apim-Subscription-Key": KEY, "Content-Type": "application/json"},
    json={"search": "tietojärjestelmä", "top": 50, "orderby": "datePublished desc",
          "filter": "datePublished ge 2026-04-01T00:00:00Z", "count": True},
    verify=False
)
```

**Key eForms fields (85 total):**
- `titleFi/titleSv/titleEn` — tender title in Finnish/Swedish/English
- `organisationNameFi` — organisation name
- `descriptionFi` — tender description
- `cpvCodes` — EU procurement categories (filterable, searchable)
- `estimatedValue` + `currency` — contract value
- `datePublished` — publication date (filterable)
- `deadline` — submission deadline (filterable)
- `type` — notice type code (see below)
- `mainType` — ContractNotices, PriorInformationNotices, ContractAwardNotices, ProcurementPlan
- `winnerOrganisations` — award result winners
- `procurementDocumentsUrl` — link to tender documents
- `organisationNationalRegistrationNumber` — org business ID (Y-tunnus)
- `isNationalProcurement`, `isEuProcurement` — threshold flags
- `noticeNumber`, `eFormsId` — identifiers

**Notice type codes:**
- 4, 7 = Ennakkoilmoitus (Prior info)
- 16, 17, 18, 19, 20, 21 = Hankintailmoitus (Contract notice)
- 29, 30, 31, 32, 33, 34, 35 = Jälki-ilmoitus (Award notice)
- E1 = Markkinakartoitusilmoitus (Market consultation)
- E3 = Kansallinen hankintailmoitus (National contract notice)
- E4 = Kansallinen jälki-ilmoitus (National award notice)

**Hilma vs tarjouspalvelu.fi — why we need both:**

| | Hilma | tarjouspalvelu.fi |
|---|---|---|
| Owner | Hansel Oy (state) | Cloudia/Mercell (commercial) |
| API | Yes (free REST) | No (browser automation) |
| Above-threshold tenders | Yes | Yes |
| Below-threshold tenders | Rarely | Yes — often ONLY here |
| Full documents/attachments | No | Yes (ZIP download working) |
| Q&A, evaluation criteria | No | Yes (detail page tabs) |
| CPV codes, estimated value | Yes (structured) | No |
| Winner names (awards) | Yes | Only in description text |

**Combined mode (`--mode=combined`):** Queries Hilma API for CGI-relevant tenders (CPV-filtered), scrapes tarjouspalvelu.fi for below-threshold + documents, merges and deduplicates. Tested: 200 from Hilma + 100 from tarjouspalvelu = 263 unique (39 matched in both).

**Implementation:** `hilma.py` (API client), `merge.py` (dedup logic). CGI-relevant CPV prefixes: 72 (IT), 48 (software), 64 (telecom), 79 (consulting), 80 (education), 85 (health).

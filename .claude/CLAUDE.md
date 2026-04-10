# Tender Intelligence Project

CGI project to automate Finnish public sector tender monitoring from tarjouspalvelu.fi. Scrapes tenders, filters noise, AI-summarizes, routes to CGI departments via three-tier system, sends email notifications, and builds price/competitor intelligence.

## Project Structure

```
rfq-management/
├── demo_scraper.py          # Main pipeline: scrape → classify → summarize → route → notify → analyze
├── storage.py               # SQLite: tenders, award_analysis, competitors tables. Classification logic.
├── routing.py               # Three-tier routing: Tier 1 (products) + Tier 2 (keywords from Excel) + Tier 3
├── cgi_products.py          # CGI own products (50+), partner platforms (90+), competitors (20+)
├── notify.py                # Email: one HTML digest per department via SMTP
├── summarize.py             # OpenAI: tender summaries (model configurable via OPENAI_MODEL env)
├── analyze.py               # Award results analysis: extract winners, prices, build competitor profiles
├── logger.py                # File logger — writes to scraper.log
├── app.py                   # Streamlit web dashboard (not tested recently — may need fixes)
├── create_presentation.py   # Generates CGI PowerPoint (outputs to project dir + Windows desktop)
├── run_demo.sh              # Demo script: fast run with emails enabled, good AI model
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
| Chrome automation + Cloudflare bypass | ✅ Working | undetected-chromedriver, non-headless |
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
| Detail page (full access) | ⚠️ Partially | Works when clicking from listing page (ActionChains click). Fails with driver.get(url). See "Detail Page Fix" below. |
| Detail page scraping code | ⚠️ Needs testing | Code exists but the back-and-forth navigation needs verification |
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

## Detail Page Fix (IMPORTANT)

Login session persists when **clicking a tender link from within the page** (ActionChains click on `a.tp-list__row`). This redirects to `EditoiTarjousta?p=XXX` with full access (all tabs: Publication Documents, Q&A, General Criteria, etc.).

Session is **LOST** when using `driver.get(url)` to navigate directly. The detail page then shows public-only data.

**Fix approach (implemented but needs more testing):**
1. Stay on listings page after extraction
2. For each tender to enrich: find its row by tpId, ActionChains click it
3. Scrape detail page text
4. `driver.back()` to return to listings
5. Repeat for next tender

**Known issue:** After pagination (scraping 5 pages), going back to page 1 may not show the same tenders. Detail scraping should be done per-page during extraction, not after.

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
SMTP_USER=                  # Gmail address (valoraami@gmail.com for test)
SMTP_PASSWORD=              # Gmail App Password
SMTP_FROM=                  # Sender address
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

## Next Steps (prioritized)

1. **Fix detail page scraping** — the click-back approach works but needs testing in the full pipeline
2. **Test demo run** — run `./run_demo.sh`, verify emails arrive with AI summaries
3. **Test analytics mode** — run `--mode=analytics` to verify price/competitor extraction
4. **Fix Streamlit dashboard** — likely broken after routing refactor
5. **Implement Tier 1 separate email** — critical alerts should be a distinct urgent email, not mixed into department digests
6. **Expand pagination** — currently 5 pages (100 tenders). Production needs all pages.
7. **Production deployment** — Azure VM with Xvfb, cron scheduling, service account

## People

- **Riku Turkia** — SME, deep knowledge of tarjouspalvelu.fi platform
- **CGI stakeholder** — TBD, from the section responsible for tender collection
- **Ville Pajala** — developer building this PoC

## Key Technical Decisions (for future reference)

- **undetected-chromedriver** — only tool that bypasses Cloudflare Turnstile. Tested Playwright (5 variants), all failed.
- **Zscaler SSL** — import certs into Chrome NSS database (`~/.pki/nssdb/`). Do NOT use `--ignore-certificate-errors` — Cloudflare detects it.
- **Non-headless required** — Cloudflare blocks all headless browsers. Production needs Xvfb.
- **ActionChains for Vaadin** — Cloudia login uses Vaadin framework. JS click doesn't work. Must use Selenium ActionChains.
- **Word boundary matching** — short product names (SAP, SAS) match Finnish words. Use regex `\b` boundaries.
- **Session persistence** — login session only persists when clicking links from within the page. `driver.get(url)` loses the session.

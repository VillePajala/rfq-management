# Tender Intelligence — Public Sector Tender Management for CGI

Automation and AI-powered system for monitoring and responding to Finnish public sector tenders (julkiset kilpailutukset). Collects open calls for tender, analyzes bidding opportunities, and provides competitive intelligence to help CGI win more contracts.

## Data Sources

- **Hilma** (hankintailmoitukset.fi) — official Finnish tender notification platform. **Has a free public API** (AVP API, JSON, self-service). All above-threshold tenders must be published here by law. API docs: https://github.com/Hankintailmoitukset/hilma-api, developer portal: https://hns-hilma-prod-apim.developer.azure-api.net/
- **tarjouspalvelu.fi** — Cloudia Supplier Portal (owned by Mercell). The actual eTendering platform where full tender documents live and bids are submitted. **No public API** — requires browser automation. Hilma is essentially a downstream mirror of tarjouspalvelu.fi for above-threshold tenders. tarjouspalvelu.fi also contains **below-threshold tenders not found on Hilma**.
- **SME contact**: Riku Turkia (deep knowledge of tarjouspalvelu.fi)

### Hilma vs tarjouspalvelu.fi

| Aspect | Hilma | tarjouspalvelu.fi |
|---|---|---|
| Role | Official notice channel (metadata) | eTendering platform (full documents) |
| Legal status | Mandatory for above-threshold | Used by choice (most popular in Finland) |
| Below-threshold tenders | Rarely published | Often published |
| Document depth | Summary only | Full tender docs, attachments, specs |
| Login required | No (fully public) | Browsing partly public; documents need login |
| API available | Yes (free REST API) | No |
| Data flow | Receives notices FROM tarjouspalvelu.fi | Source system; pushes to Hilma |

## 7-Step Pipeline

### Step 1: Collect & Route (MVP) ✓ IMPLEMENTED
Automated collection of open tenders from tarjouspalvelu.fi. Tenders are classified, filtered, and routed to the right domain experts within CGI based on keyword matching rules defined in an Excel file.

**Current capabilities:**
- Scrapes all tenders from any organization on tarjouspalvelu.fi (Helsinki demo: 191 tenders)
- Extracts: name, organisation, type, description, publication date, deadline, URL
- Classifies into: open competitions (63), early signals (19), dynamic purchasing (5), direct awards (4), closed/results (100 filtered out)
- Stores in SQLite database with deduplication (tracks new vs already-seen tenders)
- Routes tenders to contacts via keyword rules in `routing_config.xlsx`
- Sends **one digest email per department** (HTML formatted with clickable links, deadlines, descriptions)
- Each department gets only their relevant tenders; if two departments share an email, they receive separate categorized emails
- SMTP via Gmail (App Password) or any SMTP server; falls back to local HTML preview if no SMTP configured

### Step 2: AI Summarization (MVP) — NOT YET IMPLEMENTED
AI-generated summary of each tender delivered alongside the notification. Domain experts can quickly assess whether a tender is worth bidding on without reading the full documents.

### Step 3: AI-Assisted Bid Building (Future)
Automated bid/proposal generation based on tender requirements. Complex — long-term vision.

### Step 4: Price Intelligence
Analysis of historical tender award decisions. Build a database of past awards to understand winning bid price levels for similar contracts, reducing guesswork in pricing.

### Step 5: Competitor Profiling
Track competitors' win/loss history and financial status. Use qualification criteria (e.g. revenue thresholds) to predict which competitors will enter a given tender. Factor in competitor circumstances — e.g. a competitor in financial trouble may underbid aggressively.

### Step 6: Early Signal Detection
Monitor public sector organizations' meeting minutes (pöytäkirjat) and board documents for hints of upcoming tenders. Gives CGI a head start before the call for tender is even published. The scraper already captures market dialogues (markkinavuoropuhelu) and info requests (tietopyyntö) as early signals.

### Step 7: Post-Loss Monitoring
Track how winning bidders perform after contract award. Spot failing projects where the winning supplier underdelivers, creating opportunities for CGI to intervene and capture business.

## What's Built

```
rfq-management/
├── demo_scraper.py          # Main scraper — full pipeline from scraping to notifications
├── storage.py               # SQLite storage — tender classification, deduplication, tracking
├── routing.py               # Excel-based routing — matches tenders to CGI contacts by keyword
├── notify.py                # Email notifications — HTML digest per recipient
├── routing_config.xlsx      # Routing rules (auto-generated, editable by non-technical users)
├── tenders.db               # SQLite database (auto-created)
├── .env                     # Credentials (never committed)
├── .env.example             # Template for credentials
├── .gitignore               # Excludes .env, DB, Chrome profile, screenshots
└── chrome_profile/          # Persistent Chrome profile (Zscaler certs)
```

### How to Run

```bash
# First time setup
cd ~/projects/rfq-management
python3 -m venv venv
source venv/bin/activate
pip install undetected-chromedriver python-dotenv openpyxl selenium setuptools

# Copy and fill in credentials (optional)
cp .env.example .env
nano .env

# Run the scraper
python demo_scraper.py              # Helsinki (default)
python demo_scraper.py espoo        # Other organizations
python demo_scraper.py tampere
```

### Tender Classification

Tenders are automatically classified based on type and name:

| Category | What it means | CGI action |
|---|---|---|
| `open_competition` | Active tender, open for bids | **Bid on these** |
| `dynamic_purchasing` | Ongoing DPS framework | **Join the framework** |
| `early_signal` | Market dialogue, info request, advance notice | **Prepare — tender coming soon** |
| `direct_award` | Direct award, not open | Monitor only |
| `result` | Award decision, post-award notice, cancellation | Filtered out |

### Routing Configuration

Edit `routing_config.xlsx` to define who receives which tenders:

| Keywords | Department | Contact | Email |
|---|---|---|---|
| ohjelmisto, ICT, järjestelmä | IT Consulting | Person Name | person@cgi.com |
| rakennus, urakka | Construction | Person Name | person@cgi.com |
| * | General | Catch-all | manager@cgi.com |

- Keywords are comma-separated, matched against tender name and description (case-insensitive)
- A tender matching multiple rules is sent to all matching contacts
- `*` is a catch-all for unmatched tenders

## Tech Stack

Unified Python stack — no separate RPA tool needed since all targets are web-based.

### Core
- **Python 3.12** — single language for collection, AI, and analysis
- **SQLite** — local database for tender tracking and deduplication
- **openpyxl** — Excel-based routing configuration

### Data Collection
- **undetected-chromedriver** — browser automation for tarjouspalvelu.fi. Patches Chrome to bypass Cloudflare Turnstile bot detection. Must run non-headless (real browser with GUI/display).
- **Hilma AVP API** — direct API calls (not yet integrated, covers above-threshold tenders)

### Notifications
- **SMTP (Gmail or corporate)** — one HTML digest email per department, sent to department contact
- **HTML preview mode** — when no SMTP credentials configured, saves emails as local HTML files
- **Routing via Excel** — `routing_config.xlsx` maps keyword patterns to department contacts (editable by non-technical users)

### AI / Analysis (planned)
- **Azure OpenAI API** — LLM for summarization (step 2), signal detection (step 6), analysis (steps 4, 5, 7)

### Scheduling (planned)
- **Cron or APScheduler** — periodic collection runs

### Why Not UiPath
- All targets are web apps, not desktop applications
- undetected-chromedriver bypasses Cloudflare; UiPath would face the same CAPTCHA problem
- Python integration means data flows directly into AI pipeline, database, and email
- Simpler to maintain, deploy, and extend
- No license cost

## Known Risks & Open Questions

_Last updated: 2026-04-23 after Azure datacenter IP verification._

### Resolved

| Topic | Resolution |
|---|---|
| **Cloudflare Turnstile** | `undetected-chromedriver` patches out automation indicators; Turnstile auto-resolves without human interaction. Works with Chrome `--headless=new` (verified 2026-04-21 on residential IP, 2026-04-23 on Azure datacenter IP). |
| **Zscaler SSL** | Import Zscaler certs into Chrome NSS database (see setup script in this file). Not needed outside the CGI network. |
| **Login** | Cloudia SSO via `login.cloudia.net`. The final redirect from `/Authentication/ExternalLogin` to `/Default/Index` sometimes stalls — the scraper waits up to 45s and then force-navigates to `/Default/Index`, which succeeds. Works in both visible and headless modes. Account: `ville.pajala@cgi.com`. |
| **Headless feasibility** | `--headless=new` produces the same listings output as visible mode (verified: both yield 1,612 search results, same classification, same Tier 1B routing matches). See `test_headless.py` and `test_anonymous.py`. |
| **No public API** | Confirmed by Riku Turkia (2026-04-21): tarjouspalvelu.fi has no supported API. All automation must use browser UI. |
| **Azure datacenter IP reputation** | ✅ Verified 2026-04-23 on B2s North Europe VM: full page load, zero Cloudflare challenges. **B2s minimum** (B1s crashes Chrome). **Python 3.12 + `setuptools` shim** required. **`--disable-dev-shm-usage`** Chrome flag required for containerized environments. |

### Active risks

**1. Draft creation on tender open (BY DESIGN)**
When a logged-in user opens a tender via `/UX/TP/SiirryTarjouspyyntoon?tpId=X`, Cloudia automatically creates an offer draft (`Tarjous`) or response draft (`Vastaus`) in the user's account. Riku confirmed 2026-04-21: _"It's used to track who has reviewed the tender request."_ This is not a bug — it's a supplier-tracking feature. We cannot bypass it while logged in. Consequences:
- Each opened tender becomes an empty draft visible to the procurement organisation
- Each draft triggers an email-notification subscription to the tender (document updates, Q&A, deadlines)
- Accumulated drafts clutter the `Keskeneräiset` list for all CGI users of the account

**2. Draft backlog from prior test runs**
Past visible and headless runs opened tenders while logged in and therefore created drafts. These need a manual sweep in Cloudia under *Tarjoukset → Keskeneräiset*, filtered by `Aloittaja = Ville Pajala` in the 2026-04-21 10:58–11:42 window (today's test runs) plus any earlier dates from previous demos.

**3. Login redirect is fragile**
The scraper papers over an incomplete SSO redirect with a force-navigate fallback. If Cloudia changes the SSO flow, the fallback may also fail. Separately, the scraper uses ~25 hardcoded `time.sleep()` calls in other places; ~9 of those wait blindly for async events and should be converted to `WebDriverWait` conditions over time.

**4. Azure datacenter IP reputation — ✅ RESOLVED (2026-04-23)**
Verified on a B2s VM in Azure's North Europe region: `undetected-chromedriver 3.5.5` + Chrome `--headless=new` successfully loads `https://tarjouspalvelu.fi/Default/Index` with zero Cloudflare challenge markers and all expected page markers present (420 KB body, elapsed 14.8 s). Container Apps Jobs deployment path is unblocked. Two operational facts captured during the test:
- **B2s (4 GB RAM) is the minimum** — B1s (1 GB) causes Chromedriver OOM-related timeouts under headless Chrome.
- **Python 3.12 needs `setuptools` installed** to shim the removed `distutils` module for `undetected-chromedriver` 3.5.5.
- `--disable-dev-shm-usage` Chrome flag required on containerized environments (small `/dev/shm` default).

**5. Detail access needs a policy decision**
Anonymous users see: reference number, title, type, organisation, published/deadline dates, and full description (~1–2 KB of Finnish procurement text). Anonymous users do NOT see: publication documents, Q&A, attachments, or the tabbed edit-view. To access attachments + full detail, login is required — which creates a draft. See Decisions Needed #1 below.

### Decisions needed from CGI stakeholders

_Each item is framed as a concrete choice so we can get answers quickly._

| # | Decision | Option A | Option B |
|---|---|---|---|
| 1 | **How do we access tender details?** | **Anonymous-only** for routing/AI/email. Skip ZIP attachments entirely. No drafts ever created. | **Hybrid:** anonymous for bulk scraping; log in selectively for the 5–15 highest-priority tenders per day to download ZIPs. Accept drafts as cost. |
| 2 | **Do we delete drafts we create?** | **Yes, UI-automated:** after scraping, click "Poista tarjous" to remove. Keeps account clean. _Risk: "started and withdrew" may look unprofessional to procurement orgs._ | **No, keep them:** each draft legitimately represents real CGI interest, which is Cloudia's intended signal. Accept notification volume. |
| 3 | **Scope of tenders we monitor** | **All Finland** via `/Default/Index` global search (current default, 1,612 tenders/day). | **Targeted subset** — specific CPV codes, specific orgs, specific procurement categories. |
| 4 | **Below-threshold tender coverage** | **Skip them** — Hilma only (above-threshold only). | **Cover them** — requires tarjouspalvelu (below-threshold tenders are often published only there). |
| 5 | **Deployment target** | **Azure VM** with cron + Xvfb (original plan; proven reliable; ~€60/month). | **Azure Container Apps Jobs** (cheaper ~€10–15/month; requires Azure-IP Cloudflare test to pass). |
| 6 | **Production email infrastructure** | **CGI M365 SMTP relay** (standard). | **Microsoft Graph API** (modern, supports per-message audit). |
| 7 | **Service account** | **Dedicated account** created for this scraper (recommended; avoids polluting Ville's personal profile). | **Continue on Ville's account** (unsafe long-term). |

### Questions for SMEs (Riku Turkia and CGI stakeholders)

**Answered:**
- ~~Q12: Does logged-in session bypass Cloudflare?~~ → Yes, but Cloudflare wasn't the primary blocker; draft creation is the real issue.
- ~~Q13: Data feed / API?~~ → No API (Riku, 2026-04-21).

**Still open — scope & coverage:**
1. Which public sector organizations should we monitor? All of Finland, or specific ones?
2. Which below-threshold tenders are published only on tarjouspalvelu.fi and not on Hilma?
3. Are there other platforms besides tarjouspalvelu.fi and Hilma that CGI should monitor?

**Still open — filtering & relevance:**
4. What types of tenders is CGI actually interested in? (IT only? Consulting? All sectors?)
5. Are there minimum contract values below which CGI wouldn't bid?
6. Should we filter by geographic region or is all of Finland relevant?
7. How should we handle Dynamic Purchasing Systems (DPS)?

**Still open — routing & notifications:**
8. Who are the actual CGI department contacts that should receive tender notifications?
9. How should tenders be categorized for routing?
10. Notification cadence — real-time, daily digest, weekly?

**Still open — platform access:**
11. Does the Cloudia procurement organisation see a visible record when we open-then-delete a draft? (informs Decision #2 above)
12. Is it acceptable to run this automation at the scale of ~1,600 opens/day anonymously? Does Cloudia consider that abusive even without account load?

**Still open — competitor intelligence:**
13. Who are CGI's main competitors in Finnish public procurement?
14. What competitor information would be most valuable?

## Project Context

- **Client organization**: CGI (specific section TBD)
- **Core problem**: Manual, reactive process for finding and responding to public sector tenders. Too much guesswork in bid pricing and competitor assessment.
- **MVP scope**: Steps 1-2 (automated tender collection, routing, and summarization)
- **Demo status**: Step 1 fully working end-to-end (scrape → classify → filter → store → route → email notifications). Step 2 (AI summarization) next.

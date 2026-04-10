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

### Cloudflare Bot Protection on tarjouspalvelu.fi (SOLVED)
tarjouspalvelu.fi uses Cloudflare Turnstile CAPTCHA. This affects ALL automation tools equally (Playwright, UiPath, Selenium).

**What we tested:**
| Approach | Cloudflare result |
|----------|------------------|
| Playwright headless | Fully blocked |
| Playwright non-headless | CAPTCHA checkbox shown, does NOT auto-resolve |
| Playwright non-headless + stealth patches | Same — checkbox shown |
| Playwright with system Chrome (`channel="chrome"`) | Same — checkbox shown |
| **undetected-chromedriver** | **CAPTCHA auto-resolves — site loads successfully** |

**Solution:** `undetected-chromedriver` patches Chrome binary to remove all automation indicators. Turnstile auto-resolves without human interaction.

**Requirements:**
- Google Chrome installed (`google-chrome-stable`)
- GUI/display environment (headless servers need Xvfb)

### Corporate SSL Proxy (Zscaler) (SOLVED)
CGI uses Zscaler which re-signs SSL certificates. Linux Chrome doesn't trust the Zscaler root CA by default.

**Solution:** Import Zscaler certs into Chrome's NSS database:
```bash
sudo apt-get install -y libnss3-tools
echo | openssl s_client -connect tarjouspalvelu.fi:443 -servername tarjouspalvelu.fi -showcerts 2>/dev/null \
  | awk '/BEGIN CERTIFICATE/,/END CERTIFICATE/{print}' > /tmp/zscaler_chain.pem
mkdir -p ~/.pki/nssdb
certutil -d sql:$HOME/.pki/nssdb -A -t "CT,C,C" -n "Zscaler Root CA" -i /tmp/zscaler_chain.pem
```
Note: production deployments outside the corporate proxy would not need this.

### tarjouspalvelu.fi Login (PENDING)
Full tender details (estimated value, qualification requirements, attachments) require a logged-in account. CGI is already registered on the platform — an admin needs to create a user account. Registration was submitted, waiting for admin approval.

### Questions for SMEs (Riku Turkia and CGI stakeholders)

**Scope & Coverage:**
1. Which public sector organizations should we monitor? All of Finland, or specific ones?
   - Currently we scrape one org at a time (e.g. Helsinki = 191 tenders)
   - tarjouspalvelu.fi has a cross-org search at `/Default/Index` — could we use that instead of scraping org by org?
   - The Organisations listing page on tarjouspalvelu.fi is broken (server error) — is there another way to get the full list of orgs?
2. Which below-threshold tenders are published only on tarjouspalvelu.fi and not on Hilma?
3. Are there other platforms besides tarjouspalvelu.fi and Hilma that CGI should monitor? (e.g. Hanki, other eTendering systems)
4. Should we also monitor Hilma via its API for completeness, or is tarjouspalvelu.fi sufficient?

**Filtering & Relevance:**
5. What types of tenders is CGI actually interested in? (IT only? Consulting? All sectors?)
6. Are there minimum contract values below which CGI wouldn't bid?
7. Should we filter by geographic region or is all of Finland relevant?
8. How should we handle Dynamic Purchasing Systems (DPS) — are these relevant to CGI?

**Routing & Notifications:**
9. Who are the actual CGI department contacts that should receive tender notifications?
10. How should tenders be categorized for routing? By sector? By CGI business unit? By contract type?
11. How often should notifications be sent — real-time, daily digest, weekly?

**Platform Access:**
12. Does a logged-in tarjouspalvelu.fi session bypass Cloudflare entirely?
13. Does tarjouspalvelu.fi offer any data feed, export, or API for registered customers?
14. Can we get a tarjouspalvelu.fi account approved? (registration submitted, waiting for CGI admin)

**Competitor Intelligence:**
15. Who are CGI's main competitors in Finnish public procurement?
16. What competitor information would be most valuable — win rates, pricing patterns, sector focus?

**Deployment:**
17. Where should this run in production? CGI's Azure? On-premise server? Developer workstation?
18. Does CGI have a preferred email system for automated notifications (SMTP relay, Microsoft 365, etc.)?

## Project Context

- **Client organization**: CGI (specific section TBD)
- **Core problem**: Manual, reactive process for finding and responding to public sector tenders. Too much guesswork in bid pricing and competitor assessment.
- **MVP scope**: Steps 1-2 (automated tender collection, routing, and summarization)
- **Demo status**: Step 1 fully working end-to-end (scrape → classify → filter → store → route → email notifications). Step 2 (AI summarization) next.

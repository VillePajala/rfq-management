# Tender Intelligence — Project Specification

**Version:** Draft 1 (2026-04-22)
**Status:** Working document. Iterating with Ville Pajala (developer) and CGI stakeholders.
**Purpose:** Authoritative reference for planning, Azure resource estimation, and build kick-off.

**Related docs:**
- `docs/mvp_requirements_stakeholder.md` — verbatim source requirements from CGI stakeholder (Finnish).
- `docs/mvp_spec.md` — earlier working notes, now superseded by this document.
- `README.md` § *Known Risks & Open Questions* — current blockers and decisions pending CGI input.
- `.claude/CLAUDE.md` — technical deep-dive (selectors, auth flow, API details).

---

## 1. Executive summary

CGI Finland currently discovers and tracks Finnish public-sector procurement opportunities manually across two platforms (Hilma and tarjouspalvelu.fi). This is time-consuming, prone to missed tenders, and doesn't scale. **Tender Intelligence** is an automated system that:

- Monitors both platforms nightly
- Filters ~1,600+ daily notices to a relevant subset
- Extracts descriptions, deadlines, documents
- Runs initial AI analysis (subject area, value, procedure type, scoring)
- Routes each tender to the right CGI department
- Delivers a daily digest email with AI summary + link to archived documents

**Expected value:** fewer missed relevant tenders; faster triage (hours → minutes); analyst attention focused on bid/no-bid decisions rather than data collection.

**Stakeholders:**
- **Product owner:** CGI stakeholder (TBD — from tender-collection section)
- **Subject-matter expert:** Riku Turkia (deep knowledge of tarjouspalvelu.fi platform)
- **Developer:** Ville Pajala
- **Azure team:** to be engaged for deployment estimate

---

## 2. Current state (as of 2026-04-22)

**What works end-to-end (verified locally):**

- Headless Chrome scraping of tarjouspalvelu.fi (Cloudflare Turnstile bypassed via `undetected-chromedriver`)
- Cloudia SSO login with force-navigate fallback for slow SSO redirects
- Hilma API integration (149k+ notices available, CPV-filtered)
- Combined mode: merges both sources, deduplicates
- Detail-page scraping (all 6 tabs: Summary, Publication documents, Q&A, Terms, Procurement object, Persons in charge)
- ZIP attachment downloads (via `requests` + Selenium session cookies)
- AI summarization using OpenAI gpt-4o-mini (relevance verdict per tender)
- Three-tier routing: own-product alerts, partner-platform alerts, Excel-based department rules
- Email digest generation
- SQLite persistence with new-vs-seen deduplication

**Verified with comparison runs (2026-04-22):**
- Headless mode produces identical scraped data to visible mode — same 1,612 search results, same metadata, same detail extraction, same ZIP file (18,863 KB).

**What isn't built yet:**
- Azure deployment (Infrastructure-as-Code)
- Dockerfile
- SharePoint upload (Microsoft Graph API)
- Calendar integration (iCal)
- Dashboard (Full scope, not MVP)
- Automated draft cleanup
- CI/CD pipeline

**Codebase:** `github.com/VillePajala/rfq-management` (private). Python 3.12, Selenium + undetected-chromedriver, OpenAI SDK, OpenPyXL, SQLite, python-dotenv. ~3,000 LOC total.

---

## 3. Scope

### 3.1 MVP — First deployable version

Matches the Finnish stakeholder requirements (`mvp_requirements_stakeholder.md`).
**Philosophy:** kevyt, shadow use ~1 month, NO SPAM. One shared inbox during pilot,
expand gradually after validation.

**Included:**

| # | Capability | Status |
|---|---|---|
| 1 | Monitor Hilma + tarjouspalvelu.fi nightly (RFPs, tietopyynnöt, markkinavuoropuhelut) | Scraper complete; scheduling TBD |
| 2 | CPV-code filtering (list to be confirmed by CGI — § 14) | Complete |
| 3 | Upload tender documents (ZIPs) to a single **staging SharePoint workspace**; manual move to the per-opportunity ("oppo") workspace downstream | SharePoint upload TBD |
| 4 | **Subject identification — keyword-based primary, AI summary secondary.** Tier 1A (CGI own products), Tier 1B (partner platforms), Tier 2 (department keyword Excel), Tier 3 unmatched | Complete (three-tier engine in `routing.py`) |
| 5 | Extract structured metadata per tender: key dates (question deadline, tender deadline), estimated size, restricted vs. open procedure, scoring mechanism (quality vs. price), contract included, reservations allowed | Key dates + relevance working; remaining extraction fields TBD (may come from Hilma structurally + AI from attachments for the rest) |
| 6 | **Human-in-the-loop reviewer gate:** digest email is sent to ONE reviewer (not the real BU-leader distribution). Reviewer verifies the matched keywords and the proposed recipients, then forwards manually to the actual team. Automation produces "what it would have done"; reviewer confirms. See § 3.5 | Email generation + SMTP send complete; Graph Mail send TBD |
| 7 | **Koontinäkymä (minimal):** read-only status dashboard — see § 3.3 | Not built |
| 8 | **Email-reply claim tracking:** dashboard reflects who has claimed each tender — see § 3.4 | Not built |
| 9 | Antivirus scanning of downloaded attachments — see § 7.2.1 | Not built (recommended: Microsoft Defender for Storage) |
| 10 | **Dedicated service mailbox** for outbound digests + inbound replies — see § 3.6 | Not provisioned (CGI M365 admin task) |
| 11 | ~1 month pilot shadow use | Plan only |

**Nice-to-haves (build if marginal effort):**
- iCal calendar invites for tender deadlines (sent as .ics attachment in the digest email)

**Explicitly NOT in MVP (deferred to Full):**
- Auto-routing to teams (stakeholder: *"ei spämmää"*)
- Full dashboard with login + status editing + question-submission tracking — only the minimal read-only koontinäkymä is in MVP
- Pricing database / simulation
- Automated draft cleanup in Cloudia
- Workspace (oppo) auto-provisioning
- Level 3 document intelligence (full attachment reading)
- Competitor tracking dashboard

### 3.2 Full project — Future phases

Everything MVP delivers, plus:

| # | Capability | Depends on |
|---|---|---|
| F1 | Auto-route to responsible teams (no human triage step) | MVP shadow-use feedback on routing accuracy |
| F2 | Level 3 AI agents — read tender attachments (RFP spec, pricing templates, evaluation criteria) | Document-parsing AI spike |
| F3 | Bid/no-bid recommendation engine | F2 + historical bid data |
| F4 | Outlook calendar integration (write critical dates to calendars of responsible team members) | Graph API calendar permissions |
| F5 | Cloud dashboard — CGI portal showing all active tenders, delegation status, question-submission state, deadlines | Separate UI project |
| F6 | Pricing data collection + simulation | F2 + database of awarded prices |
| F7 | Competitor intelligence dashboard (wins, pricing patterns, sector focus) | Analytics mode already scaffolded |
| F8 | Automated draft lifecycle management — UI-click delete drafts for "no-bid" tenders | UI-automation work; policy approval |
| F9 | Workspace (oppo) auto-provisioning when a tender goes to bid | SharePoint / Teams permissions |
| F10 | **Deadline reminders on active tenders.** When a tender is `claimed` / `under_work`, automatically send reminder emails before the question deadline and before the tender deadline. Default cadence: 7 days / 3 days / 1 day before each deadline, configurable per department. Recipients: claimant + Asiakasvastaava (per ohjaustiedosto). Reminder events logged in the koontinäkymä. Could move into late MVP if effort proves marginal — deadlines are already captured by the scraper, the work is mostly scheduling + one new email template. Est. ~2–3 days. | Requires koontinäkymä state (claim tracking from § 3.4) to know which tenders are active; deadline fields already scraped |

### 3.3 Koontinäkymä — MVP minimal + Full vision

"Koontinäkymä" = aggregated overview / summary view. Stakeholder's *"kalenterinäkymä"*
in the source requirements points at the same idea.

#### 3.3.1 MVP version — cheap minimal, read-only

A **single static HTML page**, regenerated at the end of each nightly run, published
to Blob Storage (or Azure Static Web Apps / Azure Storage static website hosting).

Content (all read-only):
- **Today's new tenders** — grouped by tier (1A critical, 1B high, 2 department, 3 unmatched)
- **Active tenders awaiting action** — notified, no reply yet (with "days since notified")
- **Claimed & in progress** — who claimed, when
- **Deadline countdown** — next 14–30 days, sorted by urgency
- **Summary counts per department**
- **Unmatched tenders list** (signals that routing rules need expansion)

| Property | MVP choice |
|---|---|
| Auth | None — protected by obscure URL or Entra ID app-level auth. Sketch option for Azure team: Static Web App with Entra ID integration (built-in, no code). |
| Data source | Nightly JSON output + mailbox-reply state file |
| Refresh | Regenerated at end of each nightly run + end of each reply-tracker run (~every 2 h on weekdays) |
| Editing | None |
| State tracking | Via emails, not via clicks (see § 3.4) |

**Effort (MVP):** ~1–2 days on top of already-written Jinja template logic in the scraper.

#### 3.3.2 Full version — stakeholder's vision

Proper web app, out of scope for MVP but part of Full:

- **Entra ID SSO login** — each CGI user identified
- **Interactive dashboard** with claim / status / comment actions via UI
- **Calendar mode** — month view, deadlines per team
- **Question-submission tracking** — scraper polls tarjouspalvelu.fi Q&A tabs for each claimed tender and reflects state changes
- **Pricing history database** — record of awarded prices, CGI's own bids, and competitor wins
- **Simulation mode** — stakeholder's future-state idea; pricing what-if analysis

**Effort (Full):** 3–5 weeks as its own sub-project (stack suggestion: Next.js on Static Web Apps or a containerized React app; Azure SQL backend; shared Container Apps Environment with the scraper).

### 3.4 Claim tracking via email reply (MVP mechanism)

**Idea:** use email reply as the "claim this tender" signal. No clickable UI needed
in MVP — CGI people already reply to emails. The agent's service mailbox is polled
periodically; any reply is interpreted as a claim and surfaces in the koontinäkymä.

#### 3.4.1 How it works

1. Digest email goes out with a machine-parseable subject:
   `[TENDER-609121] Kuumasairaalan maarakennusurakka — Infra`
2. `From` and `Reply-To` are a dedicated service mailbox (e.g. `tender-agent@cgi.com`).
3. Recipient replies → reply lands back in the service mailbox.
4. `reply_tracker.py` (new module) polls the mailbox via Microsoft Graph Mail API
   every 2 hours on weekdays, extracts tender ID from subject, captures `sender + timestamp`.
5. Tender's state in the shared JSON / SQLite is updated:
   `status: claimed, claimed_by: <email>, claimed_at: <timestamp>`.
6. Koontinäkymä reflects the claim on its next regeneration.

#### 3.4.2 Chosen defaults (with options noted for the Azure team)

| Question | MVP default | Option the Azure team may prefer |
|---|---|---|
| What counts as a claim? | **Any non-auto-reply response** from a CGI employee | Require explicit keyword ("OTAN" / "TAKE") in the reply body — stricter but requires user training |
| Auto-reply filtering | **Best-effort header + subject filter:** ignore messages with `Auto-Submitted: auto-replied`, `X-Autoreply: yes`, or subject containing "Automatic reply" / "Poissaoloviesti" / "Out of Office" | Strict whitelist — only accept messages that pass a positive-content heuristic (e.g. body > 20 chars of human text) |
| Multiple replies | **First reply = primary claimant; subsequent replies stored as "also interested" list** | First-come-locked (subsequent replies rejected); or latest-reply-wins (hand-over friendly) |
| Claim transfer | **Allowed via a new reply from a different user; dashboard shows claim history** | Require explicit handover keyword ("SIIRTO" / "HANDOVER") to transfer; silent re-claims rejected |
| Un-claim | **Allowed via reply containing "EI" / "NOT ME" / "PASS"** | No un-claim — only forward/transfer |
| Reminder on no-reply | **After 3 working days without reply, send one reminder; then escalate to the stakeholder distribution list after 5 days** | Configurable per department; or no reminder at all |
| Bid-submission detection | **Manual** — "reply SUBMITTED" (or Finnish "LÄHETETTY") updates status to `submitted` | Automatic — scraper checks tarjouspalvelu.fi offer state per claimed tender (needs to revisit each detail page, creates more drafts — drafts being by-design per Riku) |

#### 3.4.3 Required infrastructure

| Piece | Who owns |
|---|---|
| Dedicated service mailbox (e.g. `tender-agent@cgi.com`) | CGI M365 admin |
| Entra App Registration with **Mail.Read** + **Mail.Send** on the service mailbox only | CGI Azure admin |
| Graph API poll schedule (every 2 h on weekdays, via second Container Apps Job or triggered from main Job) | Azure team |
| Email footer explaining monitored mailbox: *"This mailbox is monitored by an automated tender-tracking system; your reply will be used to record claim ownership."* | Spec-level (transparency / GDPR) |

#### 3.4.4 Privacy / transparency notes

- Service mailbox reads ALL replies. Employees should be told.
- Only sender address + timestamp are stored, not the reply body content.
- Reply body may be logged at DEBUG level for troubleshooting during pilot — off in production.
- GDPR: employee email + timestamp is standard work-tracking data; covered under existing employee-data handling.

**Effort:** ~4 days on top of the minimal koontinäkymä (Graph registration, poll module, state schema, dashboard extensions, scheduling, edge-case testing).

### 3.5 Ohjaustiedosto — routing control file

**File:** `routing_config.xlsx` (already exists in the repo; current columns will be
aligned with the structure below during MVP build).

**What it is:** the single source of truth for routing decisions. Non-technical
CGI users edit it; no code changes required to add a department, adjust keywords,
or update recipients.

#### 3.5.1 Proposed column structure

| Column | Purpose | Example |
|---|---|---|
| `Area` / `Department` | Human-readable identifier of the business area | `Ruokahuolto`, `Kiinteistöhallinta`, `Infra` |
| `Keywords` | Comma/semicolon-separated match terms (case-insensitive, Finnish stem-aware) | `Aromi; ruokahuolto; ruokapalvelu; ravintola` |
| `CPV filter (optional)` | Further narrow by CPV code prefix | `55520000;15000000` |
| `Asiakasvastaava email` | Account manager / opportunity owner — primary contact for this area | `anna.virtanen@cgi.com` |
| `Notification recipients` | Semicolon-separated list of emails who receive the digest when this rule matches. **First wave (pilot): BU leader(s) only.** Expands gradually after validation. | `bu-infra-lead@cgi.com; head-of-sector@cgi.com` |
| `Active` | `Y`/`N` — allow disabling a rule without deleting the row | `Y` |
| `Notes` | Free-text context (who owns it, when last reviewed) | `Reviewed 2026-04 by Riku T.` |

**Scope for MVP build:** the scraper already uses an Excel config. The Azure team
task is to ensure the in-code schema matches the columns above and that
changes to the Excel are picked up on the next run without a redeploy.

**Who owns editing:** CGI procurement team (business side). Should live in SharePoint
alongside the staging workspace, so the scraper reads the latest version each run
(via Graph API → SharePoint file read).

#### 3.5.2 Reviewer gate in MVP pilot

During MVP shadow use, automation does NOT send emails directly to
`Notification recipients`. Flow instead:

```
┌─────────────────────────────────────────────────────────────┐
│  Scraper run finds a matching tender                         │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  Digest email generated, showing:                            │
│   • matched keywords                                          │
│   • proposed recipients (from ohjaustiedosto)                 │
│   • Asiakasvastaava                                           │
│   • AI summary + metadata                                     │
│   • link to SharePoint material                               │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  Email goes to ONE reviewer mailbox (not real recipients)    │
│  e.g. reviewer@cgi.com  —  a designated CGI person           │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  Reviewer checks:                                             │
│    ✓ Did the keywords match correctly?                        │
│    ✓ Is the Asiakasvastaava right?                            │
│    ✓ Are the proposed recipients the right BU leaders?        │
│  Then forwards manually to the actual team.                   │
│  (Also replies to agent to record claim in koontinäkymä)      │
└─────────────────────────────────────────────────────────────┘
```

**Why:** stakeholder is explicit about NOT spamming. The reviewer is a trust
layer during pilot — confirms routing quality before anything reaches
department leaders. Also generates tight feedback to improve the ohjaustiedosto
(wrong routing → reviewer updates the Excel → next run is better).

**Transition to steady state:** after ~1 month of shadow pilot, when the
reviewer sees "keywords and recipients are essentially always right," the
reviewer gate is removed (automation sends directly to the
`Notification recipients` list). This is the *"kun ratkaisua on ajettu ja
testattu"* point in the stakeholder's plan.

#### 3.5.3 Interaction with koontinäkymä

During the reviewer-gate phase:
- Dashboard shows each tender's proposed recipients and the reviewer's action status (pending review / forwarded / rejected).
- When the reviewer forwards to the actual team, they also reply to the agent email with something like `FORWARDED to <team>` — that reply updates the tender's state to `notified + forwarded`.
- BU-leader replies after the forward come back to the service mailbox and register as claims normally (see § 3.4).

In steady state (post-reviewer), the koontinäkymä flow matches § 3.4 directly.

### 3.6 Service mailbox requirements

The automation requires a **dedicated shared mailbox in CGI's M365 tenant** that is
used for all outbound digests and all inbound replies. The agent reads this mailbox
via Microsoft Graph API to drive state updates in the koontinäkymä.

#### 3.6.1 What it is

A **shared mailbox** (not a user mailbox) in M365. Shared mailboxes are:

- **Free** — no M365 license required
- Can be co-owned by multiple admins for oversight
- Can both send and receive mail
- Accessible via Graph API with scoped `Mail.Read` and `Mail.Send` permissions

A regular user mailbox would also work but costs an M365 license (~€5–10/month) — not recommended.

#### 3.6.2 One mailbox, three roles

| Flow | From | To | Reply-To | Notes |
|---|---|---|---|---|
| **MVP pilot digest** | service-mailbox | reviewer (single real person) | service-mailbox | Reviewer is the only human recipient during pilot |
| **MVP reviewer forward** | reviewer (manual) | BU leaders | service-mailbox (BCC) | Reviewer's manual forward BCCs the service mailbox so the agent sees it too |
| **Post-pilot steady state** | service-mailbox | BU leaders directly | service-mailbox | Reviewer gate removed |
| **Reply / claim / handoff** | BU leader or reviewer | service-mailbox | — | Agent polls mailbox via Graph API every 2 h on weekdays |

#### 3.6.3 Naming

CGI's M365 admin chooses the address per their conventions. Candidates:

- `tarjousagentti@cgi.com` (Finnish-native)
- `tender-agent@cgi.com` (English)
- `hankintabotti@cgi.com`
- `procurement-monitor@cgi.com`

**Principle:** short, clearly non-human, and obviously belongs to an automated system
so recipients don't expect a person behind it.

#### 3.6.4 Graph API permissions required on this mailbox

| Permission | Purpose |
|---|---|
| `Mail.Send` (application, scoped to this mailbox only) | Agent sends digest emails |
| `Mail.Read` (application, scoped to this mailbox only) | Reply-tracker reads inbox |
| `Mail.ReadWrite` (application, scoped to this mailbox only) | To mark messages as read after processing |

All scoped to **this single mailbox** via Application Access Policy — agent cannot
read any other CGI mailbox.

#### 3.6.5 Email footer — transparency notice

Every outgoing email from the service mailbox includes a short footer (Finnish +
English) so recipients understand it's automated and their replies are tracked:

> *"Tämä sähköposti on lähetetty automaattisen tarjouspyyntöagentin toimesta.
> Vastaukset kirjautuvat järjestelmään. / This email was sent by an automated
> tender-tracking agent. Your reply will be logged for claim tracking."*

#### 3.6.6 Ownership

- **CGI M365 admin** — creates the shared mailbox; maintains access policy
- **CGI Azure admin** — configures the Entra App Registration with scoped Graph permissions
- **Project owner** — chooses the final address and the footer wording

### 3.7 Prerequisites from CGI + PoC mocks

Build work cannot complete without these CGI-provided inputs. Until they arrive,
the PoC uses mocks (Ville's own email and placeholder keywords) — matches
stakeholder's "light pilot" philosophy.

| Prerequisite | Who provides | MVP / Production need | PoC mock (currently used) |
|---|---|---|---|
| **Authoritative CPV code list** (the codes CGI actually wants to monitor) | CGI procurement | Required for meaningful filtering | Developer-assumed prefixes: 72, 48, 64, 79, 80, 85 (IT, software, telecom, consulting, education, health) |
| **Keyword list per department** (for the ohjaustiedosto — see § 3.5) | CGI procurement / department leads | Required; determines routing quality | Placeholder keywords from stakeholder example (`ruokahuolto → Aromi`, `kiinteistöhallinta → Koki`, `infrapalvelut → GTO`) |
| **Contact persons per department** — both Asiakasvastaava and BU leader(s) | CGI HR / procurement | Required for production; first wave = BU leaders | Ville's personal email for everything |
| **Reviewer mailbox address** (MVP pilot gate) | CGI IT + stakeholder | Required for MVP pilot | Ville's personal email |
| **Service mailbox** (agent's sending mailbox — see § 3.6) | CGI M365 admin | Required for production | Gmail App Password + Ville's personal sender address |
| **tarjouspalvelu.fi service account** | Riku Turkia / CGI | Required for production; pilot can continue on Ville's account short-term | Ville's personal CGI tarjouspalvelu.fi account |
| **SharePoint target** — site URL + staging library + Entra app permissions | CGI SharePoint admin | Required for production | Local `downloads/` folder, Azure Blob in personal-Azure simulation |
| **CGI Public Azure tenant access** | CGI Azure admin | Required for production | Ville's personal Azure subscription |
| **OpenAI / Azure OpenAI subscription** | CGI procurement | Required for production at scale | Ville's personal OpenAI key |
| **M365 SMTP relay or Graph Send consent** | CGI IT | Required for outbound email production | Gmail App Password |
| **DPSC / data-classification approval** | CGI security | Required before production | Not applicable for personal PoC |

**None of these are code blockers for continued PoC work** — they're production-handover prerequisites. Building on mocks lets the Azure team prove the pipeline before CGI resources are provisioned.

### 3.8 Current code gaps vs stakeholder requirements

Audit of `demo_scraper.py`, `storage.py`, `summarize.py`, `notify.py`, `hilma.py`,
`routing.py` against the stakeholder's MVP requirements
(`docs/mvp_requirements_stakeholder.md`) as of 2026-04-22.

| # | Stakeholder requirement | Current code state | Action for Azure team |
|---|---|---|---|
| 1 | Monitor **tarjouspyynnöt, tietopyynnöt, markkinavuoropuhelut** | All three captured; `tietopyyntö` + `markkinavuoropuhelu` go into `early_signal` bucket; `tarjouspyyntö` into `open_competition` | ✅ No change |
| 2 | Hilma via API | Integrated in `hilma.py` | ✅ No change |
| 3 | tarjouspalvelu.fi via scraper | Working headless in `demo_scraper.py` | ✅ No change |
| 4 | **CPV-code filtering** | Hilma side: CPV-filtered. Tarjouspalvelu side: NOT CPV-filtered — only filtered by notice type. CPV tags arrive only when a tarjouspalvelu tender also exists in Hilma (via `merge.py`) | ✅ **Decided (2026-04-22): accept tarjouspalvelu-only tenders without CPV tag for MVP.** Three-tier keyword routing already narrows tarjouspalvelu-only tenders. Cross-source items pick up CPV via `merge.py`. Tarjouspalvelu-only tenders tend to be below-threshold local procurements where CPV is often unassigned at source anyway. AI CPV inference (8-digit hierarchy) rejected for MVP due to hallucination risk. Revisit in Full scope if pilot shows a measurable gap. |
| 5 | Download to **one agreed SharePoint workspace** | Saves to local `downloads/` folder only | 🟡 **Code-complete (2026-04-22):** `sharepoint.py` with 3-mode design (personal OneDrive / SharePoint delegated / SharePoint app-only). MSAL device-code flow, chunked upload for large files, `docs/sharepoint_setup.md` walkthrough. **Live end-to-end verification deferred to personal-Azure deployment phase.** |
| 6 | Preliminary analysis — **keyword-based subject identification** | Three-tier routing in `routing.py` using `cgi_products.py` + `routing_config.xlsx` | ✅ No change |
| 7 | Preliminary analysis — **question deadline + tender deadline** | Only tender deadline (`deadline`) captured as structured field. **Question deadline NOT separately persisted** (it appears in raw detail text but isn't extracted) | ✅ **Done (2026-04-22):** `_extract_question_deadline()` parses Summary tab for FI / EN label, persists as `question_deadline` in tender dict + DB column + renders in email. |
| 8 | Preliminary analysis — **estimated size** (kokoluokka) | Captured from Hilma as `estimated_value`; tarjouspalvelu-only tenders don't get this | ✅ **Decided (2026-04-22): accept partial coverage for MVP — Hilma-only.** Hilma covers all EU-threshold + most above-minimum national procurements, which is where size matters most. Tarjouspalvelu-only tenders are typically below-threshold / smaller. Adding an AI extraction step for size adds cost + complexity without strong value signal. Revisit in Full scope if pilot feedback shows size is a decisive routing factor. |
| 9 | Preliminary analysis — **restricted vs. open procedure** | Not extracted | ✅ **Done (2026-04-22):** Captured via Hilma's structural `procedureType` field (EU eForms code list: `open`, `restricted`, `neg-wo-call`, etc.). Propagates through `merge.py`, persisted to DB, rendered in email with Finnish translations. 74% of Hilma notices populated; blanks are correctly-blank prior-info / market-consultation notices. |
| 10 | Preliminary analysis — **scoring mechanism (quality vs. price)** | Not extracted | ✅ **Done (2026-04-22):** New `extract.py` module uses OpenAI JSON mode to return `quality_weight`, `price_weight`, `scoring_basis` with evidence quote. Opt-in via `ENABLE_METADATA_EXTRACTION=1`. Conservative null-when-unknown behavior; structural price-only inference supported. |
| 11 | Preliminary analysis — **contract included + reservations allowed** | Not extracted. Note: existing `contract_duration` / `contract_value` fields are for competitor analysis (winners), not this requirement. **Name collision risk** | ✅ **Done (2026-04-22):** Extracted by the same unified OpenAI call as #10. Field names `contract_included` / `reservations_allowed` deliberately distinct from competitor-analysis `contract_duration` / `contract_value`. Both booleans stored as `INTEGER` in SQLite (null / 0 / 1). |
| 12 | Initial in-house routing | Three-tier working | ✅ No change |
| 13 | Email to **agreed mailbox** (not direct to teams) | Currently sends to addresses in `routing_config.xlsx`. If addresses are real department emails, it goes direct. **No reviewer-gate code path.** | ✅ **Done (2026-04-22):** `REVIEWER_MODE=1` + `REVIEWER_EMAIL` env flags. When enabled, all per-department digests redirect to one reviewer; subject gets `[REVIEW → <dept>]` prefix; body gets a yellow "intended recipient" banner with forward instruction. Graceful fallback if `REVIEWER_EMAIL` is blank. |
| 14 | Email contains **link to downloaded material** | Current email has a link to the tarjouspalvelu tender page. **No SharePoint link** (because no upload yet) | 🟡 Depends on #5 live verification. Once `sharepoint.py` upload is exercised end-to-end, capture the returned `webUrl` and add a `SharePoint link:` line to the digest — trivial follow-up. |
| 15 | No direct routing to teams yet ("ei spämmää") | See #13 | ✅ **Done** via #13's REVIEWER_MODE flag. |
| 16 | iCal for deadlines (nice-to-have) | Not built | ✅ **Done (2026-04-22):** new `ical.py` parses FI/EN date formats with DST-aware Helsinki tz conversion, emits RFC 5545 VCALENDAR with 2 VEVENTs per tender (question + tender deadline), attached as `text/calendar;method=PUBLISH` MIMEBase part. |
| 17 | Cloud dashboard (nice-to-have) | Not built; MVP minimal version spec'd in § 3.3 | 🟡 Cheap minimal version in MVP per § 3.3 |
| 18 | Antivirus for attachments (open question) | No scanning | 🔴 Enable Microsoft Defender for Storage (see § 7.2.1) |

**Summary (as of 2026-04-22, end of MVP-closure day):**
- ✅ 15 items resolved (originally-fine + now-done + decided)
- 🟡 3 items code-complete pending live verification or deployment (SharePoint upload #5, email-link #14, cloud dashboard #17)
- ⚪ 0 items blocking MVP code. Only #18 Defender remains — infra, not code (runbook in `docs/defender_runbook.md`).

---

## 4. System architecture

### 4.1 High-level diagram

```
                               ┌─── Azure tenant (CGI Public) ───┐
                               │                                 │
                               │  Container Apps Job             │
                               │   (Python scraper image)        │
                               │        │                        │
  ┌─ Scheduler (cron) ───────▶│        ▼                        │
  │                            │  Key Vault ◀── Managed Identity │
  │                            │  Blob Storage                   │
  │                            │  Log Analytics                  │
  │                            │  Container Registry             │
  │                            └──────────────┬──────────────────┘
  │                                           │
  │                                  outbound │
  │                                  requests │
  ▼                                           ▼
  06:00 UTC+3 daily     ┌────────────┬────────────┬──────────────┐
                        │            │            │              │
                        ▼            ▼            ▼              ▼
                  Hilma API    tarjouspalvelu   OpenAI API   SharePoint (Graph API)
                  (REST)       (browser auto)   (summaries)  (ZIP uploads)
                                                            +
                                                            CGI M365 SMTP (email)
```

### 4.2 Nightly run sequence (MVP)

1. Container Apps Job fires at 06:00 UTC+3
2. Pull image from Container Registry; start container
3. Managed Identity → fetch secrets from Key Vault (credentials, API keys)
4. Query Hilma API for yesterday's new notices, CPV-filtered
5. Log into tarjouspalvelu.fi via Cloudia SSO
6. Scrape global search listings (all Finland)
7. Merge + deduplicate Hilma and tarjouspalvelu sources
8. Classify (open / signal / closed)
9. AI-summarize each relevant tender (OpenAI)
10. Apply three-tier routing (Excel rules)
11. For priority tenders: open detail page → scrape tabs → download ZIP → upload to SharePoint
12. Build and send email digest to shared inbox
13. Persist state (SQLite → Azure Blob on exit, or managed DB in Full scope)
14. Flush logs to Log Analytics
15. Container exits

**Expected runtime:** 7–15 minutes depending on how many priority tenders trigger detail scraping.

### 4.3 Data flow

| Source | → | Target | Protocol | Volume |
|---|---|---|---|---|
| Hilma API | → | scraper | HTTPS REST | ~200–500 KB / run |
| tarjouspalvelu.fi | → | scraper | HTTPS browser | ~10–50 MB / run |
| scraper | → | OpenAI | HTTPS REST | ~100 KB in / ~50 KB out per tender |
| scraper | → | Azure Blob | Azure SDK | 10–50 MB ZIPs per relevant tender |
| scraper | → | SharePoint | Graph API | Same ZIPs |
| scraper | → | M365 SMTP | SMTP/TLS | 1 email per department per day |
| scraper | → | Log Analytics | Azure Monitor SDK | ~1–5 MB / run |

---

## 5. Azure resource requirements

### 5.1 MVP resources

| Resource | Purpose | Spec / SKU | Estimated monthly cost |
|---|---|---|---|
| Resource Group | Logical container | — | €0 |
| Container Apps Environment | Hosts the Job | Consumption | ~€0 baseline |
| Container Apps Job | Executes nightly scrape | 2 vCPU / 4 GB, 15-min timeout | ~€2–5 (7 min × 30 days) |
| Azure Container Registry | Stores Docker image | Basic SKU (10 GB) | ~€4 |
| Key Vault | Secrets: SSO password, API keys, SMTP | Standard | ~€0.50 |
| Azure Blob Storage | ZIP archive + state backup | Standard LRS, Hot tier | ~€1 (50 GB growth) |
| Log Analytics workspace | Logs + metrics | 5 GB/day free quota | €0 |
| Application Insights | Metrics + alerts | Linked to Log Analytics | €0 |
| Managed Identity | Auth for Key Vault + Blob | — | €0 |
| App Registration (Entra ID) | Graph API: **Sites.ReadWrite.All** (SharePoint upload), **Mail.Send** + **Mail.Read** (service mailbox, see § 3.4) | — | €0 |
| Microsoft Defender for Storage | Malware scanning of ZIP attachments before SharePoint upload (see § 7) | Per-transaction | ~€0.50 |
| Azure Static Web App OR Blob static website | Hosts the minimal koontinäkymä (see § 3.3) | Free / Standard | €0–€9 |
| Alerting (action group + email) | Failure notifications | — | €0 |

**MVP Azure infra total:** **~€12–20/month** (raised slightly with Defender for Storage + Static Web App).

External (not Azure):
- OpenAI API (gpt-4o-mini): ~€20–30/month at ~300 tenders/day

**Total MVP running cost:** **~€35–50/month**.

### 5.2 Full-project additional resources

| Resource | Purpose | Spec / SKU |
|---|---|---|
| Azure SQL Database | Persistent tender history, bid outcomes, pricing | Basic DTU / Serverless General Purpose |
| App Service Plan | Hosting the dashboard UI | B1 or S1 |
| Static Web App (alt.) | Hosting the dashboard UI | Standard |
| Service Bus | Async queue for Level 3 AI document analysis | Basic |
| Cognitive Search (optional) | Full-text search across historical tenders | Basic |
| Azure AI Document Intelligence (optional) | Complement Claude/GPT for structured doc parsing | S0 |
| Azure OpenAI (alternative to OpenAI API) | If CGI prefers keeping inference inside Azure | S0 |

**Full-project infra total:** ~€40–100/month above MVP.
**Total Full-project running cost (incl. AI):** **~€80–200/month** depending on Level 3 AI usage.

### 5.3 Environments

| Environment | Tenant | Purpose |
|---|---|---|
| Dev | Ville's personal Azure | End-to-end simulation (see § 5.3.1) |
| Staging | CGI Public | Pre-production validation, no real emails |
| Production | CGI Public | Live nightly runs, real outputs |

#### 5.3.1 Personal-Azure simulation scope

Strategy: **build and prove the entire pipeline in Ville's personal Azure
subscription first, then migrate to CGI Public** once the design is locked.
Avoids waiting on CGI provisioning cycles while we're still iterating.

**Fully simulatable in personal Azure:**

| Piece | How it's simulated |
|---|---|
| Scheduled runtime | Azure Container Apps Job (identical to CGI target) |
| Cloudflare-from-datacenter-IP | Any Azure IP tests the same question — Cloudflare doesn't distinguish tenants |
| Secrets | Personal Key Vault |
| Container image | Personal Azure Container Registry (or Docker Hub) |
| ZIP archive | Azure Blob — identical SDK calls as production |
| Logs + alerting | Personal Log Analytics workspace |
| Antivirus (Defender for Storage) | Enable on personal Blob container — same behaviour |
| Email sending | Gmail App Password (SMTP) or personal M365 shared mailbox |
| OpenAI, Hilma | Same APIs either way |
| Koontinäkymä | Hosted in personal Storage static website / Static Web App |

**Cannot be truly simulated (needs CGI target):**

| Piece | Why |
|---|---|
| CGI SharePoint upload | Only the production SharePoint library exists in CGI tenant; Graph API code path is identical, target changes |
| CGI internal email distribution | Personal simulation uses test addresses, not real CGI BU leaders |
| Zscaler / CGI network specifics | Only visible from inside CGI |
| DPSC / data-classification process | CGI procedure, not technical |

**Simulation monthly cost (running 24/7 for the duration of development):**

| Resource | Cost |
|---|---|
| Container Apps Jobs | ~€2–4 |
| Blob Storage (growing to ~50 GB) | ~€1 |
| Key Vault | ~€0.50 |
| Log Analytics (within 5 GB free tier) | €0 |
| Container Registry (Basic) | ~€4 |
| OpenAI API (~300 tenders/day × gpt-4o-mini) | ~€20–30 |
| Defender for Storage | ~€0.50 |
| **Total** | **~€30/month** |

Azure's €200 free credit for new subscriptions covers the first 30 days; after
that, ~€30/month personal out-of-pocket for as long as the simulation is live.

**Migration cost (personal → CGI Public):** roughly one day. If infrastructure is
written as Bicep from the start, the migration is essentially one
`az deployment` command targeting the CGI subscription + manual copy of secrets
from personal Key Vault to CGI Key Vault + swap of SharePoint site / service
mailbox endpoints.

---

## 6. External integrations

| System | Owner | Protocol | What CGI needs to provide |
|---|---|---|---|
| Hilma API | Hansel Oy (public) | REST | API key (free; self-service registration at `hns-hilma-prod-apim.developer.azure-api.net`) |
| tarjouspalvelu.fi | Cloudia / Mercell | Browser automation (no API) | Dedicated service account (NOT Ville's personal) |
| OpenAI API | OpenAI | REST | API key + billing account |
| SharePoint site | CGI Public | Graph API | Site URL + library ID + Entra app registration with Sites.ReadWrite.All |
| M365 SMTP relay | CGI Public | SMTP/TLS or Graph Mail | Service mailbox + credentials, or app registration with Mail.Send |
| Outlook Calendar (Full) | CGI Public | Graph API | App registration + Calendars.ReadWrite on responsible employees' mailboxes |

---

## 7. Security & compliance

### 7.1 Data classification

Procurement notices are **public information** by Finnish law — this is explicitly published data. The system does NOT process confidential CGI internal data, personal data of citizens, or classified information.

Minor personal data scope: CGI employee email addresses (routing recipients). Standard GDPR employee-data handling applies.

### 7.2 Secrets handling

- All credentials (tarjouspalvelu.fi password, API keys, SMTP) in **Azure Key Vault**
- Container uses **Managed Identity** to fetch secrets — no secret values in the image, env file, or source code
- `.env` file exists only in local dev, gitignored

### 7.2.1 Attachment antivirus scanning

Stakeholder open question: *"Onko riskiä, että liitetiedostojen mukana tulee
haittaohjelmia, miten voitaisiin tehdä virustarkistus?"*

**Recommended:** **Microsoft Defender for Storage** on the Blob container where
ZIPs land before SharePoint upload.

- Scans every blob on upload (BlobCreated event)
- Emits malware-detection alert to Defender for Cloud / Security Center
- Native to Azure, no extra infrastructure
- Cost: ~€0.15 per 1,000 transactions — negligible for our volume (~300 scans/day)

Pipeline:
```
scraper → Blob container (staging)
              │
              ├─[Defender scans]──▶ clean: proceed to SharePoint upload
              │                    infected: quarantine, alert SecOps, skip upload
              ▼
         SharePoint
```

**Alternative options for the Azure team to consider:**
- Defender for Cloud with broader scope (if CGI already subscribes).
- On-box ClamAV in the scraper container (simpler, but no centralized alerting).
- Trust the source portals (tarjouspalvelu.fi / Hilma) and skip scanning — **not recommended**; attachments are attacker-controlled in a supply-chain sense.

### 7.3 Compliance checklist (CGI Public tenant)

- [ ] DPSC (Data Processing Security Classification) — request via CGI procedure before production deployment
- [ ] DPIA — likely not required (public data, minimal PII), but confirm with CGI DPO
- [ ] Service account terms-of-use review — confirm with Riku / tarjouspalvelu.fi that automated supplier-portal use is permitted
- [ ] Container image vulnerability scanning — enable ACR scan on push
- [ ] Dependency scanning — Dependabot on the GitHub repo

### 7.4 Known legal considerations

- **Draft creation** on tender open is Cloudia's intentional supplier-tracking feature (confirmed by Riku). Accept as by-design behavior. The drafts represent genuine CGI interest in those tenders — this is what procurement organisations are meant to see.
- **No circumvention** of paid tiers (SPS Premium). We only use features accessible to free-tier logged-in users.

---

## 8. CI/CD

| Stage | Tool | Trigger |
|---|---|---|
| Source | GitHub (`VillePajala/rfq-management`) | push |
| Build | GitHub Actions (or Azure DevOps Pipelines — CGI standard TBD) | on push to `main` |
| Image push | GitHub Actions → Azure Container Registry | after successful build |
| Infrastructure | Bicep (Azure native) — 100–200 LOC template | manual apply for now, automatable |
| Deploy | Container Apps Job picks latest image | next scheduled run |
| Rollback | Deploy previous image tag | manual |

**Recommendation:** Bicep over Terraform for tighter Azure tooling integration, unless CGI standardizes on Terraform.

---

## 9. Observability

| Signal | Tool | Alert threshold |
|---|---|---|
| Run success/failure | Log Analytics (structured log line) | Email if run fails |
| Run duration | Log Analytics | Alert if > 20 minutes |
| Tender count per run | Log Analytics | Alert if < 50% of rolling 7-day average (possible site change) |
| OpenAI spend | Azure Budget + OpenAI usage API | Monthly cap alert |
| Key Vault access failures | Azure Monitor | Any failure |
| Cloudflare challenge failures | Scraper log → Log Analytics | Any failure (scraper-level retry first) |

---

## 10. Pilot plan (per stakeholder)

**Duration:** ~1 month shadow use, matching stakeholder's request.

| Week | Focus | Outputs |
|---|---|---|
| 1 | Deploy, runs nightly, emails to test inbox only | Daily digests reviewed by stakeholder |
| 2 | Stakeholder feedback — routing rules tuning, keyword refinements, CPV tweaks | Updated `routing_config.xlsx` |
| 3 | Expand emails to 2–3 real department inboxes (willing early adopters) | Real-world feedback |
| 4 | Full routing active, monitor deliverability and relevance | Go/no-go decision for full rollout |

---

## 11. Roadmap

| Phase | What | Duration (estimate) |
|---|---|---|
| **Phase 0** | Local PoC working | ✅ Done |
| **Phase 1a** | Personal-Azure simulation (Ville's sub) | 1–2 weeks |
| **Phase 1b** | Validation from Azure IP (Cloudflare test) | 0.5 day |
| **Phase 2** | Dockerize + Bicep IaC + CI pipeline | 1 week |
| **Phase 3** | SharePoint upload + Graph API integration | 3–5 days |
| **Phase 4** | Deploy to CGI Public, staging env | 0.5–1 week (including DPSC) |
| **Phase 5** | Pilot (~1 month) | 4 weeks |
| **Phase 6** | Go-live in production | 2–3 days |
| **Phase 7+** | Full-project features (F1–F9, prioritized) | Multi-quarter roadmap |

**MVP target:** from today, ~6–9 weeks to production if Azure team starts next week.

---

## 12. Azure team — effort estimate inputs

### 12.1 What's already built (reduces scope)

| Component | Done | Notes |
|---|---|---|
| Python scraper with Selenium | ✅ | ~3,000 LOC, tested |
| Hilma API integration | ✅ | Production-ready |
| undetected-chromedriver + Cloudflare bypass | ✅ | Verified working |
| Cloudia SSO login (with fallback) | ✅ | Works headless |
| Detail page + ZIP download | ✅ | Works headless |
| AI summarization | ✅ | OpenAI integration complete |
| Three-tier routing | ✅ | Excel-driven |
| Email digest generation | ✅ | HTML rendering complete |
| SQLite persistence | ✅ | Dedup working |

### 12.2 What Azure team needs to build

| Item | Description | Est. effort |
|---|---|---|
| Ohjaustiedosto schema alignment | Confirm scraper reads the MVP column set from § 3.5; swap from local file to SharePoint-hosted Excel (Graph API file read) | 0.5–1 day |
| Dockerfile | Python 3.12 + Chrome + the scraper | 0.5 day |
| Bicep templates | RG, ACR, Container Apps Environment + Job(s), Key Vault, Blob, Log Analytics, App Insights, Managed Identity, Entra App Registration, Static Web App (for koontinäkymä) | 1.5–2 days |
| GitHub Actions pipeline | Build → push to ACR → trigger Job update | 1 day |
| Graph API / SharePoint upload module | Python module using `msgraph-sdk` — upload ZIPs to staging workspace | 1–2 days |
| Graph Mail module (`reply_tracker.py`) | Poll service mailbox, parse `[TENDER-X]` subjects, update tender state — see § 3.4 | 1.5 days |
| Second Container Apps Job | Reply tracker on 2-hour weekday schedule | 0.25 day |
| Minimal koontinäkymä | Jinja template + Blob/Static Web App publish at end of each run — see § 3.3 | 1–2 days |
| SMTP / Graph Send integration (production) | Already has SMTP; may swap to Graph Mail for service-mailbox sending | 0.25–0.5 day |
| Defender for Storage configuration | Enable on staging Blob container + alert routing | 0.25 day |
| Alerting rules + runbooks | Log Analytics queries + action group | 0.5 day |
| Migration from personal to CGI tenant | Apply same Bicep template, swap secrets | 0.5 day |
| DPSC documentation package | Data flow diagrams + security classification | 1 day |
| Environment configs (dev / staging / prod) | Separate Bicep parameter files | 0.5 day |

**Total estimate for Azure team:** **10–14 working days** (one developer) from start to first production deployment, assuming no blockers from CGI provisioning. *(Revised up to include koontinäkymä + email reply tracking + Defender for Storage + ohjaustiedosto schema + SharePoint-hosted routing config.)*

### 12.3 Dependencies on CGI (not in Azure team's control)

- Subscription + resource-group provisioning in CGI Public tenant
- Entra app registration for Graph API (admin consent required)
- SharePoint site / library permissions granted to the app
- Service account on tarjouspalvelu.fi provisioned
- Service mailbox for email sender
- Access to CGI Container Registry or green-light to use a new ACR
- DPSC approval

---

## 13. Non-goals / out of scope

- **Submitting actual bids** — never. CGI humans decide.
- **Editing or uploading responses** to procurement notices.
- **Paid-tier features** (Cloudia SPS Premium).
- **Real-time notifications** — daily digest only, no push/SMS.
- **Languages beyond Finnish + Swedish + English** for procurement content.
- **Countries beyond Finland** — out of scope for v1.
- **Platforms beyond Hilma and tarjouspalvelu.fi** (e.g. Hanki, other EU eTendering) — could be added later, not MVP.
- **Document editing** — we read docs, never modify them.
- **Supplier management** — no CRM features.

---

## 14. Open questions (need stakeholder / CGI answers)

Tracked primarily in `README.md` § *Known Risks & Open Questions*. Items specific to spec + Azure planning:

### Operational scope (needs CGI business-side input)

1. **Exact CPV code list CGI wants to monitor?** Current code uses assumed prefixes from `CLAUDE.md` (72 IT, 48 software, 64 telecom, 79 consulting, 80 education, 85 health) but these are developer assumptions, not confirmed with CGI procurement. Need an authoritative list from the procurement team — ideally as a CSV or Excel so it's easy to update without code changes.
2. **Oppo-workspace naming + location?** Which SharePoint site is the agent's staging workspace? Is "Opportunity workspace" the right term for the downstream manual destination, and who owns creating them?
3. **Shared inbox for MVP digest?** Which single mailbox receives the daily email during the pilot?
4. **Ohjaustiedosto ownership + columns?** Who builds and maintains the routing Excel (see § 3.5 proposed columns)? Are the columns right — are we missing anything CGI tracks? How do we measure coverage (e.g., % of tenders falling into Tier 3 "unmatched")?
5. **Service account ownership on tarjouspalvelu.fi?** Who creates the dedicated account (NOT Ville's personal), and who rotates the password?
6. **Reviewer gate — who?** Which single CGI person sits in the reviewer role during the MVP pilot? What's their SLA for forwarding (same-day? 24 h?) — and fallback if they're away?
7. **Reviewer gate — exit criteria?** When does the reviewer gate come down (emails start going direct to BU leaders)? Suggested: after N weeks of "no routing corrections needed," or a go-decision meeting with stakeholder.

### Azure / infrastructure

6. **Azure OpenAI vs. OpenAI API directly?** CGI preference TBD. Azure OpenAI keeps inference in Azure (simpler compliance) but limited model choice and currently no gpt-4o-mini parity.
7. **CI/CD tool standard?** GitHub Actions or Azure DevOps Pipelines — what does CGI standardize on?
8. **IaC standard?** Bicep (Azure-native) or Terraform?
9. **Environments strategy?** Personal-Azure dev → CGI staging → CGI prod, or direct to CGI staging?
10. **SharePoint target confirmed?** Which specific site and library receive ZIP uploads?
11. **Budget approval ceiling?** OK with ~€30–50/mo MVP, ~€100–200/mo Full?
12. **Antivirus approach for attachments?** Recommended: Microsoft Defender for Storage on the Blob staging container. Needs CGI security green-light vs. alternative tooling already in use.

---

## 15. Change log

| Date | Author | Change |
|---|---|---|
| 2026-04-22 | Ville + Claude | Initial draft of project spec based on stakeholder requirements, today's headless validation, and Azure deployment planning |

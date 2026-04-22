# Tender Intelligence — Task Checklist

Living progress tracker. Check items as they land. Derived from
`docs/project_spec.md` § 3.8 (gap analysis) + stakeholder requirements in
`docs/mvp_requirements_stakeholder.md`.

**Legend:** ✅ done  ·  🟡 in progress  ·  ⬜ not started  ·  🔵 decision needed

---

## ✅ Already done (pre-spec-phase work)

- [x] Python scraper with Selenium + undetected-chromedriver
- [x] Cloudflare Turnstile bypass
- [x] Cloudia SSO login (with smart-wait + force-navigate fallback)
- [x] Hilma API integration (CPV filtering at source)
- [x] Combined mode: merge + dedup Hilma + tarjouspalvelu
- [x] Detail-page scraping (all 6 tabs) — headless
- [x] ZIP attachment download via `requests` + session cookies
- [x] AI summarization (OpenAI gpt-4o-mini)
- [x] Three-tier routing (Tier 1A own products, 1B platforms, 2 department Excel, 3 unmatched)
- [x] Email digest generation (HTML)
- [x] SQLite persistence + dedup
- [x] Headless = visible output parity (verified 2026-04-22)
- [x] Written spec: `docs/project_spec.md` (v1 draft)
- [x] Written spec: `docs/mvp_requirements_stakeholder.md` (verbatim source)

---

## MVP gap closure — 11 items (from `project_spec.md` § 3.8)

Ordered for low-risk wins first, SharePoint big-rock last.

### Code extraction additions

- [ ] **1. Extract question deadline** (`question_deadline`)
  - Stakeholder: *"milloin kysymysten jättö, milloin tarjouksen jättö"*
  - Currently only tender deadline persisted. Question deadline visible in detail tabs but not captured as structured field.
  - **Files:** `demo_scraper.py` (tab scrape), `storage.py` (DB schema), `notify.py` (email template)
  - **Definition of done:** `question_deadline` key present in tender dict; visible in email; persisted to DB.

- [ ] **2. Extract procurement procedure type** (`procedure_type`: restricted | open | negotiated | dps | …)
  - Stakeholder: *"rajattu vs. avoin menettely"*
  - Try Hilma's `procedureType` field first. Fallback: regex/AI on description for tarjouspalvelu-only tenders.
  - **Files:** `hilma.py` (capture Hilma field), `summarize.py` or new `extract.py` (fallback)
  - **Definition of done:** field populated for ≥ 90% of tenders on a sample run.

- [ ] **3. Extract scoring mechanism** (`quality_weight`, `price_weight`)
  - Stakeholder: *"pisteytysmekanismi (laatu vs. hinta)"*
  - AI extraction from the "Muut ehdot" (Other terms) tab content using OpenAI.
  - **Files:** `summarize.py` or new extraction module; `notify.py` to display.
  - **Definition of done:** two numeric fields summing to 100 when both present; N/A when not found.

- [ ] **4. Extract contract-included and reservations-allowed flags** (`contract_included`, `reservations_allowed`)
  - Stakeholder: *"onko sopimusta mukana ja onko varaumat kielletty"*
  - AI extraction from Muut ehdot tab + contract template in attachments.
  - ⚠️ Avoid name collision with existing `contract_duration` / `contract_value` in `storage.py` (those are competitor-analysis fields).
  - **Definition of done:** two booleans populated per tender where evidence exists; null otherwise.

### Design decisions (documentation only)

- [ ] 🔵 **5. Decide estimated-size coverage strategy**
  - Stakeholder: *"arvioitu kokoluokka"*
  - Hilma provides `estimated_value` structurally. Tarjouspalvelu-only tenders don't.
  - **Options:** (a) accept partial coverage, (b) AI extraction fallback from description, (c) hardcoded bracket ranges.
  - **Definition of done:** decision recorded in `project_spec.md` § 3.8 and § 14.

- [ ] 🔵 **6. Decide CPV filtering approach for tarjouspalvelu**
  - Stakeholder: *"rajaa haettavan materiaalin CPV-koodilla"*
  - Hilma is CPV-filtered at source; tarjouspalvelu is not.
  - **Options:** (a) accept tarjouspalvelu-only items without CPV tag, (b) infer CPV from description + keywords, (c) cross-reference Hilma per tarjouspalvelu item.
  - **Definition of done:** decision recorded in `project_spec.md` § 3.8 and § 14.

### Pilot-enabling code

- [ ] **7. Build reviewer-gate mechanism**
  - Stakeholder: *"ei kuitenkaan spämmää yet"*
  - Add `REVIEWER_MODE=1` + `REVIEWER_EMAIL` env flags that override per-department recipients; all digest emails go to the reviewer during pilot.
  - Alternative (no code): populate `routing_config.xlsx` with the reviewer's email for every row.
  - **Definition of done:** when `REVIEWER_MODE=1`, all emails land at `REVIEWER_EMAIL`; subject/body show the proposed "real" recipients so the reviewer knows where to forward.

### Nice-to-have (if marginal effort)

- [ ] **8. Add iCal attachment to digest**
  - Stakeholder nice-to-have: *"luo kalenterimerkinnän tarjouksen kriittisille päivämäärille"*
  - Generate `.ics` file per tender (two events: question deadline + tender deadline), attach to email.
  - **Definition of done:** recipient can open the .ics attachment and see both deadlines on their calendar.

### Integration (bigger rocks)

- [ ] **9. Build SharePoint upload module (Graph API)**
  - Stakeholder: *"hakee materiaalin yhteen sovittuun SharePoint-työtilaan"*
  - New module `sharepoint.py` using `msgraph-sdk`. Upload downloaded ZIPs to configured SharePoint site + library.
  - Auth via Managed Identity in production; client credentials for personal-Azure simulation; personal OneDrive acceptable as dev target.
  - **Definition of done:** `upload_zip(local_path, site_id, drive_id, folder) -> share_url` works end-to-end; share URL is included in the tender dict.

- [ ] **10. Include SharePoint link in digest email** *(blocked by #9)*
  - Stakeholder: *"linkin haettuun materiaaliin"*
  - Use the share URL returned by #9; display in email alongside the existing tarjouspalvelu tender link.
  - **Definition of done:** digest email shows both links per tender.

### Infra configuration (runbook, not code)

- [ ] **11. Document Defender for Storage enablement**
  - Stakeholder open question on attachment antivirus.
  - Create `docs/deploy_runbook.md` (or add to existing deploy docs): exact steps to enable Microsoft Defender for Storage on the Blob container + alert-routing config.
  - **Definition of done:** Azure team can follow the runbook and enable Defender in one sitting without guessing.

---

## Prerequisites from CGI (blocking pilot)

Not tasks we do — inputs we wait for. Track as receive/provide log.

- [ ] Authoritative CPV code list from CGI procurement
- [ ] Real keywords per department (ohjaustiedosto content)
- [ ] Contact persons per department (Asiakasvastaava + BU leaders)
- [ ] Reviewer mailbox address (for MVP pilot gate)
- [ ] Service mailbox `tender-agent@cgi.com` (or similar) provisioned in CGI M365
- [ ] `tarjouspalvelu.fi` service account created (NOT Ville's personal)
- [ ] SharePoint staging site + library + permissions granted to the Entra app
- [ ] CGI Public Azure subscription + resource group access
- [ ] OpenAI or Azure OpenAI subscription for production volume
- [ ] M365 SMTP relay credentials or Graph Send consent
- [ ] DPSC / data-classification sign-off

---

## Azure build tasks (from `project_spec.md` § 12.2)

Handed to Azure team once prerequisites arrive. Listed here for single-page visibility.

- [ ] Dockerfile (Python 3.12 + Chrome)
- [ ] Bicep templates for all Azure resources
- [ ] Ohjaustiedosto schema alignment + SharePoint-hosted config read
- [ ] GitHub Actions CI/CD pipeline
- [ ] `reply_tracker.py` Graph Mail reader
- [ ] Second Container Apps Job for reply tracking
- [ ] Minimal koontinäkymä (static HTML → Blob / Static Web App)
- [ ] Defender for Storage enablement
- [ ] Alerting rules + runbooks
- [ ] Migration procedure (personal Azure → CGI Public)
- [ ] DPSC documentation package
- [ ] Environment config files (dev / staging / prod)

---

## Post-MVP / Full scope (from `project_spec.md` § 3.2)

- [ ] F1 — Auto-routing to teams (remove reviewer gate)
- [ ] F2 — Level 3 AI agents (attachment reading)
- [ ] F3 — Bid/no-bid recommendation engine
- [ ] F4 — Outlook calendar integration
- [ ] F5 — Full dashboard (login, status editing, Q&A tracking)
- [ ] F6 — Pricing database + simulation
- [ ] F7 — Competitor intelligence dashboard
- [ ] F8 — Automated draft lifecycle cleanup
- [ ] F9 — Workspace (oppo) auto-provisioning
- [ ] F10 — Deadline reminders on active tenders

---

## How to use this file

- Check boxes as items land. Leave a short note next to the item with date + commit reference if useful.
- **Don't move tasks between sections.** Once declared MVP it's MVP; scope creep goes into Full.
- When a new requirement appears (new stakeholder input), add it to the appropriate section with a date stamp, not inline into existing items.
- Keep this file + `project_spec.md` aligned — if a task's shape changes, update both.

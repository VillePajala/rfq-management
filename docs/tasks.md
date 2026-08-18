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
- [x] **Azure datacenter IP compatibility** verified on B2s North Europe (2026-04-23): Cloudflare Turnstile passes, `/Default/Index` loads clean (420 KB, zero challenge markers). B1s insufficient — OOM crashes Chrome. Python 3.12 requires `pip install setuptools` shim for `undetected-chromedriver 3.5.5`. Chrome flag `--disable-dev-shm-usage` required for containerized environments.
- [x] Written spec: `docs/project_spec.md` (v1 draft)
- [x] Written spec: `docs/mvp_requirements_stakeholder.md` (verbatim source)

---

## MVP gap closure — 11 items (from `project_spec.md` § 3.8)

Ordered for low-risk wins first, SharePoint big-rock last.

### Code extraction additions

- [x] **1. Extract question deadline** (`question_deadline`) — _done 2026-04-22_
  - Stakeholder: *"milloin kysymysten jättö, milloin tarjouksen jättö"*
  - Currently only tender deadline persisted. Question deadline visible in detail tabs but not captured as structured field.
  - **Files:** `app/main.py` (tab scrape), `storage.py` (DB schema), `notify.py` (email template)
  - **Definition of done:** `question_deadline` key present in tender dict; visible in email; persisted to DB.
  - Implementation: `_extract_question_deadline()` helper parses Summary-tab text for either `Kysymysten jätön määräaika` (FI) or `Deadline for submitting questions` (EN) label and returns the next line as the value. Verified live on tender 608992 (`27.4.2026 9.00 (UTC+03:00)`) — extracted, persisted to JSON + SQLite, renders in the email.

- [x] **2. Extract procurement procedure type** (`procedure_type`: restricted | open | negotiated | dps | …) — _done 2026-04-22_
  - Stakeholder: *"rajattu vs. avoin menettely"*
  - Try Hilma's `procedureType` field first. Fallback: regex/AI on description for tarjouspalvelu-only tenders.
  - **Files:** `hilma.py` (capture Hilma field), `summarize.py` or new `extract.py` (fallback)
  - **Definition of done:** field populated for ≥ 90% of tenders on a sample run.
  - Implementation: Hilma API's structural `procedureType` (EU eForms code list) captured in `hilma.to_tender_dict`; propagated through `merge.merge_tender`; persisted in `storage.py` with safe `ALTER TABLE` migration; rendered in `notify.py` with Finnish-labeled display (`open (avoin)` / `restricted (rajattu)` etc.) and raw passthrough for unknown codes. **Tarjouspalvelu-only tenders still blank** — flagged for decision in task #21 (CPV approach) if we need to fill that gap. Live Hilma run: 37 of 50 notices had a procedure type (74% — not 90%, but the blanks are correctly-blank prior-info / market-consultation notices, not scraping failures).

- [x] **3. Extract scoring mechanism** (`quality_weight`, `price_weight`) — _done 2026-04-22_
  - Stakeholder: *"pisteytysmekanismi (laatu vs. hinta)"*
  - AI extraction from the "Muut ehdot" (Other terms) tab content using OpenAI.
  - **Files:** `summarize.py` or new extraction module; `notify.py` to display.
  - **Definition of done:** two numeric fields summing to 100 when both present; N/A when not found.
  - Implementation: new module `extract.py` with `extract_scoring(tender)` using OpenAI JSON mode. Returns `{quality_weight, price_weight, scoring_basis, evidence}`. Scans Summary + Other terms + Procurement object tabs (capped at 12 KB). Three-layer validation: integers 0-100 only, weights must sum to 100 or both null, conservative "unknown" when source is silent. Gated by `ENABLE_METADATA_EXTRACTION=1` so OpenAI spend is explicit. DB columns added via ALTER TABLE migration. Email renders as `Scoring: Quality 40% / Price 60%` when both present, or the qualitative basis otherwise; nothing shown when unknown. Verified: (a) Malmi schoolyard 610326 → `price-only / 0 / 100` with evidence "kokonaishinta ALV 0 %"; (b) Tilitoimistopalvelut 610551 → `unknown` with evidence quoting "neuvottelumenettely" (correct — negotiated procedure has no weights at participation stage).

- [x] **4. Extract contract-included and reservations-allowed flags** (`contract_included`, `reservations_allowed`) — _done 2026-04-22_
  - Stakeholder: *"onko sopimusta mukana ja onko varaumat kielletty"*
  - AI extraction from Muut ehdot tab + contract template in attachments.
  - ⚠️ Avoid name collision with existing `contract_duration` / `contract_value` in `storage.py` (those are competitor-analysis fields).
  - **Definition of done:** two booleans populated per tender where evidence exists; null otherwise.
  - Implementation: **unified extraction** — same OpenAI call that does scoring (task #3) now also returns `contract_included` + `reservations_allowed` + per-field evidence quotes. Single call per tender: lower cost, consistent behavior. Stored as `INTEGER` in SQLite (SQLite bool convention: 0 / 1 / NULL). Email renders `Contract included: Yes|No` and `Reservations: Allowed|Not allowed` when non-null, hidden otherwise. Regression note: after adding the new fields, the scoring prompt became over-conservative on price-only tenders — re-tuned to explicitly allow the structural price-only inference (single `kokonaishinta` field + no quality criteria ⇒ `price-only`). Malmi 610326 re-tested: correct `price-only / 0 / 100` with evidence "Malmin koulun leikkipihaurakka kokonaishinta ALV 0 %".

### Design decisions (documentation only)

- [x] **5. Decide estimated-size coverage strategy** — _done 2026-04-22_
  - Stakeholder: *"arvioitu kokoluokka"*
  - Hilma provides `estimated_value` structurally. Tarjouspalvelu-only tenders don't.
  - **Options:** (a) accept partial coverage, (b) AI extraction fallback from description, (c) hardcoded bracket ranges.
  - **Definition of done:** decision recorded in `project_spec.md` § 3.8 and § 14.
  - **Decision:** Option (a) — accept Hilma-only coverage for MVP. Reasoning: Hilma covers EU-threshold + most above-minimum national procurements (where size matters most); tarjouspalvelu-only items are typically below-threshold / small; extra AI call per tender not worth it without pilot signal. Revisit for Full scope if pilot shows size is a decisive routing factor. Recorded in `project_spec.md` § 3.8 row 8.

- [x] **6. Decide CPV filtering approach for tarjouspalvelu** — _done 2026-04-22_
  - Stakeholder: *"rajaa haettavan materiaalin CPV-koodilla"*
  - Hilma is CPV-filtered at source; tarjouspalvelu is not.
  - **Options:** (a) accept tarjouspalvelu-only items without CPV tag, (b) infer CPV from description + keywords, (c) cross-reference Hilma per tarjouspalvelu item.
  - **Definition of done:** decision recorded in `project_spec.md` § 3.8 and § 14.
  - **Decision:** Option (a) — accept tarjouspalvelu-only tenders without CPV tag for MVP. Reasoning: three-tier keyword routing already narrows tarjouspalvelu-only tenders; overlapping tenders pick up CPV via `merge.py` Hilma merge; tarjouspalvelu-only items tend to be below-threshold local where CPV is often unassigned at source; AI CPV inference (8-digit hierarchy) rejected due to hallucination risk. Revisit in Full if pilot shows measurable gap. Recorded in `project_spec.md` § 3.8 row 4.

### Pilot-enabling code

- [x] **7. Build reviewer-gate mechanism** — _done 2026-04-22_
  - Stakeholder: *"ei kuitenkaan spämmää yet"*
  - Add `REVIEWER_MODE=1` + `REVIEWER_EMAIL` env flags that override per-department recipients; all digest emails go to the reviewer during pilot.
  - Alternative (no code): populate `config/routing_config.xlsx` with the reviewer's email for every row.
  - **Definition of done:** when `REVIEWER_MODE=1`, all emails land at `REVIEWER_EMAIL`; subject/body show the proposed "real" recipients so the reviewer knows where to forward.
  - Implementation: `REVIEWER_MODE=1` + `REVIEWER_EMAIL` env vars in `notify.py`. When enabled: (a) every digest email routes to `REVIEWER_EMAIL` instead of the per-department BU-leader address; (b) subject line becomes `[REVIEW → <dept>] … — would go to <intended_email>`; (c) body gets a yellow warning banner showing the intended department, intended recipient, and forward instruction. Missing `REVIEWER_EMAIL` is handled gracefully (logs warning, falls back to per-department addresses). Added to `.env.example` with comment. Smoke-tested in both modes: reviewer-on routes correctly to `reviewer@cgi.com` with banner; reviewer-off preserves existing behavior.

### Nice-to-have (if marginal effort)

- [x] **8. Add iCal attachment to digest** — _done 2026-04-22_
  - Stakeholder nice-to-have: *"luo kalenterimerkinnän tarjouksen kriittisille päivämäärille"*
  - Generate `.ics` file per tender (two events: question deadline + tender deadline), attach to email.
  - **Definition of done:** recipient can open the .ics attachment and see both deadlines on their calendar.
  - Implementation: new `ical.py` module. `parse_tender_date()` handles Finnish (`29.4.2026 16.00 (UTC+03:00)`), English (`29/04/2026 16:00`), and seconds-variant (`21.4.2026 11.20.14`) formats; converts to UTC. `build_tender_ics(tenders)` returns a single RFC 5545 VCALENDAR with up to 2 VEVENTs per tender (question + tender deadline). `notify.py` attaches as `text/calendar; method=PUBLISH` MIMEBase part with Content-Disposition attachment so Outlook / Gmail / Apple Mail recognize it. Preview mode writes the .ics alongside the .html file for inspection. Unit-tested all date formats (8 cases pass); smoke-tested the preview path produces a valid 767-byte .ics with 3 events across 2 test tenders.

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

- [x] **11. Document Defender for Storage enablement** — _done 2026-04-22_
  - Stakeholder open question on attachment antivirus.
  - Create `docs/deploy_runbook.md` (or add to existing deploy docs): exact steps to enable Microsoft Defender for Storage on the Blob container + alert-routing config.
  - **Definition of done:** Azure team can follow the runbook and enable Defender in one sitting without guessing.
  - Implementation: `docs/defender_runbook.md` — 6-step walkthrough (subscription-level plan enablement, per-account Malware Scanning, Action Group for alerts, EICAR verification, clean-file verification, scraper integration pattern). Portal clicks + CLI equivalents for every step. Cost expectations (~€15/mo all-in at MVP volume), responsibility matrix (Azure team / SecOps / developer), proposed Python code for the scraper's scan-result polling logic. Cross-linked to spec § 7.2.1 and stakeholder requirements doc.

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

- [ ] Dockerfile (Python 3.12 + Chrome + msodbcsql18 for Azure SQL — see § 17.4)
- [ ] Bicep templates for all Azure resources (incl. Azure SQL Database Serverless GP)
- [ ] **`app/storage.py` refactor: SQLite → SQLAlchemy with `DATABASE_URL` env. Local dev keeps SQLite (`sqlite:///data/tenders.db`); production uses Azure SQL via `mssql+pyodbc://…`. Schema migrations remain idempotent ALTER TABLE pattern (works in both dialects with minor care). See `docs/project_spec.md` § 12.5 task A6 + § 17.4.**
- [ ] Ohjaustiedosto schema alignment + SharePoint-hosted config read
- [ ] GitHub Actions CI/CD pipeline
- [ ] **(Scenario B only)** `reply_tracker.py` Graph Mail reader — drop for Scenario A (Strict MVP)
- [ ] **(Scenario B only)** Second Container Apps Job for reply tracking — drop for Scenario A
- [ ] **(Scenario B only)** Minimal koontinäkymä (static HTML → Blob / Static Web App) — drop for Scenario A
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

# Production deployment handbook

For the engineer putting Tender Intelligence into production. Read this
end-to-end before touching infrastructure — the steps are sequenced so
nothing gets blocked waiting on something later in the list.

> **Single source of truth for what to build:** [`docs/project_spec.md`](../docs/project_spec.md).
> This handbook is the *operational* companion — what to do, in what order,
> with what choices at each step. The spec is *what*, this is *how*.
>
> **Visual companion:** [`docs/Tender_Intelligence_Architecture_Process.html`](../docs/Tender_Intelligence_Architecture_Process.html) — six Mermaid diagrams covering system architecture, high-level process, detailed step-by-step process (every decision branch in `app/main.py`), reply tracker, data lifecycle, and cost impact. Open in any browser.

---

## TL;DR

You are deploying a single Python container that runs once a night
(Azure Container Apps Job, schedule-triggered). It scrapes Hilma + tarjouspalvelu.fi,
runs AI summarisation, uploads tender attachments to SharePoint, and emails a
digest to one reviewer mailbox. A second Job (planned) polls the agent's
service mailbox for reply-driven claim tracking. A third lightweight asset
(static HTML page on Azure Storage) gives a read-only "koontinäkymä" overview.

- **Compute:** Azure Container Apps Jobs, schedule-triggered, **2 vCPU / 4 GB minimum**
- **Region:** **North Europe** (Cloudflare bypass verified 2026-04-23 from B2s VM in this region)
- **Image:** Python 3.12 + Chrome stable + setuptools shim + undetected-chromedriver 3.5.5 — see `Dockerfile`
- **Database:** **Azure SQL Database (Serverless General Purpose, auto-pause).** All tenders, awards, claims, history. Power BI / ad-hoc T-SQL ready from day one. See [`docs/project_spec.md`](../docs/project_spec.md) § 17.4 for why we chose this over SQLite-in-Blob
- **Document storage:** Azure Blob (ZIP staging, scanned by Defender), SharePoint (final document home), Key Vault (secrets)
- **AV:** Microsoft Defender for Storage on the staging Blob container — runbook at [`docs/defender_runbook.md`](../docs/defender_runbook.md)
- **Cost:** ~€45–90 per month all-in (infra ~€25–60, OpenAI ~€20–30) — see [`docs/project_spec.md`](../docs/project_spec.md) § 5.1
- **Effort:** ~17–23 active developer days + 4-week pilot, ~7–9 weeks elapsed — full breakdown in [`docs/project_spec.md`](../docs/project_spec.md) § 12.4–12.7
- **Pilot success criteria:** [`docs/project_spec.md`](../docs/project_spec.md) § 10.2 (10 measurable gates)
- **Why each design choice:** [`docs/project_spec.md`](../docs/project_spec.md) § 17 (key technical decisions log)
- **Finnish procurement terms:** [`docs/project_spec.md`](../docs/project_spec.md) § 16 (glossary)

---

## What "done" looks like

Production is considered live when **all** of the following are true:

1. Azure Container Apps Job runs nightly at 06:00 EEST on a cron schedule, end-to-end without manual intervention, for 5 consecutive business days
2. Each run completes in < 20 minutes and produces a non-empty digest email to the reviewer mailbox
3. ZIP attachments for every Tier 1A / 1B / Tier 2 (with documents) tender land in the configured SharePoint staging library
4. Defender for Storage is enabled on the staging Blob container and an EICAR test file was successfully detected and quarantined
5. Failure alerts (run failure, timeout, anomalous tender count) reach the on-call inbox via Action Group
6. Reply tracker Job runs every 2 hours on weekdays and updates claim state visible in the koontinäkymä HTML page
7. Koontinäkymä page is served from Azure Storage / Static Web App with Entra ID app-level auth restricting access to CGI users
8. The reviewer has confirmed for ~1 month of shadow runs that routing matches the right keywords and the right BU leaders

Items 1–5 are infrastructure. Items 6–7 are the planned MVP code stubs
([`app/reply_tracker.py`](../app/reply_tracker.py), [`app/dashboard.py`](../app/dashboard.py)).
Item 8 is the pilot exit gate.

---

## MVP boundary — what's in, what's out

### In scope (build this)

- Nightly scraper Job (combined Hilma + tarjouspalvelu mode)
- CPV-code filtering on Hilma source; keyword routing on tarjouspalvelu-only items
- Three-tier routing (CGI products / partner platforms / department keywords)
- AI summarisation + AI metadata extraction (scoring, contract included, reservations)
- ZIP archive to one staging SharePoint library
- Reviewer-gate digest email (one human gates first wave)
- Email-reply claim tracking with Graph Mail polling
- Minimal read-only koontinäkymä (static HTML, regenerated each run)
- iCal attachment with question + tender deadlines
- Microsoft Defender for Storage on staging container
- Alerting on run failure, timeout, anomaly
- ~1 month shadow-use pilot

### Out of scope (do NOT build for MVP)

- Auto-routing direct to BU leaders (stakeholder: *"ei spämmää yet"* — see [`docs/project_spec.md`](../docs/project_spec.md) § 3.2)
- Interactive dashboard with login, status editing, comment actions
- Bid/no-bid recommendation engine
- Automated draft cleanup in Cloudia
- Auto-provisioning of opportunity ("oppo") workspaces
- Pricing database / simulation
- Per-attachment AI document analysis (Level 3 agents)
- Outlook calendar write-through

These are tracked as F1–F10 in [`docs/project_spec.md`](../docs/project_spec.md) § 3.2.
Building any of them in MVP will get pushback from the stakeholder.

---

## Architecture

```
                          ┌── Azure (CGI Public tenant) ──┐
                          │                               │
                          │  Container Apps Job: scraper  │  ← cron 06:00 EEST daily
                          │  Container Apps Job: replies  │  ← cron every 2h, weekdays
                          │       │      │                │
                          │       │      ├──→ Key Vault (secrets via MI)
                          │       │      ├──→ Azure SQL DB (tenders, awards, claims, history)
                          │       │      ├──→ Blob (ZIP staging) ── Defender for Storage
                          │       │      ├──→ Log Analytics + App Insights
                          │       │      └──→ Storage static website (koontinäkymä HTML)
                          │       │                       │
                          │   outbound ───────────────────┤
                          └───────┼───────────────────────┘
                                  │
        ┌───────────────┬─────────┼─────────┬───────────────┬────────────────┐
        ▼               ▼         ▼         ▼               ▼                ▼
   Hilma REST API   tarjouspalvelu  OpenAI   SharePoint   M365 SMTP/Graph    Service mailbox
   (free)           (browser auto)  (REST)   (Graph)      (digest send)      (reply read via Graph)
```

Per-run data flow: `docs/project_spec.md` § 4.3.

---

## Pre-flight checklist — what CGI must provide before you can start

These are **not** code blockers (the application runs on mocks today), but
they **are** deployment blockers. Get them on order on day 1.

| # | Item | Owner | Notes |
|---|---|---|---|
| 1 | CGI Public Azure subscription + new resource group with `Contributor` for the deployment principal | CGI Cloud team | Personal-Azure simulation phase doesn't need this |
| 2 | tarjouspalvelu.fi service account (NOT Ville's personal) — username + password | Riku Turkia / CGI procurement | Required before the production Job logs in |
| 3 | Service mailbox in CGI M365 (e.g. `tarjousagentti@cgi.com`) — shared mailbox is free | CGI M365 admin | See [`docs/project_spec.md`](../docs/project_spec.md) § 3.6 |
| 4 | Entra App Registration with: `Sites.ReadWrite.All` (SharePoint), `Mail.Send` + `Mail.Read` + `Mail.ReadWrite` (scoped to service mailbox via Application Access Policy) | CGI Entra admin | Admin consent required |
| 5 | SharePoint staging site + library created, app permission granted | CGI SharePoint admin | URL + library ID handed to the deploy team |
| 6 | Reviewer mailbox address (one human reviewer for the pilot gate) | Stakeholder | Often same as the service mailbox owner |
| 7 | Authoritative CPV code list (or "use the developer-assumed prefixes 72/48/64/79/80/85") | CGI procurement | Affects only the Hilma filter, easy to change |
| 8 | Real `config/routing_config.xlsx` content — keywords + BU contacts per area | CGI procurement / department leads | The pilot can run with mocks and be replaced mid-pilot |
| 9 | OpenAI subscription (or Azure OpenAI subscription if CGI prefers in-Azure inference) | CGI procurement | API key only; ~€20–30/month at production volume |
| 10 | DPSC / data-classification sign-off | CGI security | Procurement notices are public data; minimal PII (employee email + timestamps); typically straightforward |

Items 1, 4, 5, and 10 are usually the slowest. Start them in parallel on day 1.

---

## Recommended build phases

A staged path that minimises waiting on CGI provisioning while iterating
on the design:

| Phase | Duration | What | Where |
|---|---|---|---|
| 0 | done | Local PoC end-to-end | Ville's laptop |
| **1a** | **1–2 weeks** | **Personal-Azure simulation: stand up the full pipeline in Ville's personal subscription, run nightly, fix issues** | **Personal Azure → personal OneDrive + Gmail** |
| 1b | done | Headless Chrome from Azure datacenter IP — verified 2026-04-23 | — |
| 2 | 1 week | Dockerfile + Bicep IaC + CI/CD pipeline | Personal Azure |
| 3 | 3–5 days | SharePoint upload module (live verification against personal OneDrive, then CGI SP) | Personal Azure → CGI SharePoint |
| 4 | 0.5–1 week | Migrate Bicep + secrets to CGI Public; complete DPSC | CGI Public |
| 5 | 4 weeks | Pilot — emails to reviewer only, no spam | CGI Public |
| 6 | 2–3 days | Remove reviewer gate, ramp to BU leaders | CGI Public |

Phase 1a is **strongly recommended** — getting the entire data flow
working in personal Azure before CGI is involved means the migration to
CGI Public is reduced to a Bicep redeploy + secrets re-paste + endpoint
swap, ~1 day. Cost during phase 1a: ~€30/month personal out-of-pocket,
covered by Azure's first-month €200 free tier.

---

## Deployment steps

Each step has a **Goal**, **Options** (with recommendation), and a
**Definition of done** so you know when to move on.

### Step 1 — Provision the Azure resource group + foundation

**Goal:** A resource group with the always-on, shared resources (logging,
secrets, registry, identity) into which the Job will be deployed in step 4.

**Options:**

- **A. Bicep (recommended).** Native to Azure, tighter ARM integration, no
  state file to babysit. Skeleton in [`infra/main.bicep`](infra/main.bicep).
- **B. Terraform.** Use this only if CGI already standardises on it.
  Gives multi-cloud, but we don't need that.

**Resources to provision** (also listed in `docs/project_spec.md` § 5.1):

| Resource | SKU / Tier | Notes |
|---|---|---|
| Resource Group | — | One per environment (rg-tender-int-dev, rg-tender-int-prod) |
| Log Analytics workspace | Pay-as-you-go (5 GB/day free quota) | Shared across both Jobs |
| Application Insights | Workspace-based, linked to Log Analytics | Auto-instrumentation off (we log structured lines) |
| User-assigned Managed Identity | — | Granted Key Vault Secrets User + Storage Blob Data Contributor |
| Key Vault | Standard | Secrets only; no certs |
| Azure Container Registry | Basic (10 GB) | Single image, single tag stream |
| Storage Account | StorageV2, LRS, Hot tier | Two containers: `staging` (ZIPs, scanned) + `dashboard` (static website with index.html) |
| **Azure SQL Database** | **Serverless General Purpose, auto-pause when idle, 1 vCore min** | **Tenders, awards, claims, history. ~€15–40/mo (idle most of the day). See [`docs/project_spec.md`](../docs/project_spec.md) § 17.4 for the SQLite-vs-Azure-SQL decision.** |
| Container Apps Environment | Consumption | Hosts both Jobs |
| Static Web App (optional) | Free or Standard | Alternative to Storage static website for koontinäkymä; needed if you want Entra ID app-level auth out of the box |

**Definition of done:**

- `az group show -n rg-tender-int-<env>` returns the group
- All listed resources visible in the portal
- Managed Identity has Key Vault + Blob role assignments
- ACR can be logged into: `az acr login -n <acrname>`

---

### Step 2 — Build and push the container image

**Goal:** A reproducible image in ACR tagged with `:latest` and `:sha-<commit>`.

**Options:**

- **A. GitHub Actions (recommended).** Skeleton at [`pipelines/build-and-push.yml`](pipelines/build-and-push.yml).
  OIDC federation to Azure means no long-lived secret in the repo.
- **B. Azure DevOps Pipelines.** Use if CGI standardises on it. Same shape,
  different YAML.
- **C. Manual `docker build && docker push`.** Fine for the personal-Azure
  phase. Don't ship to production this way.

**The Dockerfile** ([`Dockerfile`](Dockerfile)) is opinionated and includes
three things that **must not be changed without testing**:

1. `pip install --upgrade pip setuptools` runs **before** `pip install -r requirements.txt`. Why: `undetected-chromedriver 3.5.5` imports `distutils.version.LooseVersion`, which Python 3.12 removed. setuptools provides `setuptools._distutils` as a shim. Without it, the import explodes before `app/main.py` even starts.
2. `--disable-dev-shm-usage` Chrome flag is set in `app/main.py`. Why: containers default `/dev/shm` to 64 MB, which crashes Chrome under load. Don't strip it.
3. The base image is `python:3.12-slim` and Chrome is installed from Google's apt repo. **Don't switch to `chromium-browser`** unless you've re-tested Cloudflare bypass; `undetected-chromedriver` is tuned to Google Chrome's User-Agent and feature flags.

**Definition of done:**

- `docker build -t <acr>/tender-intelligence:test -f deploy/Dockerfile .` succeeds
- Image is < 1.5 GB
- `docker run --rm <acr>/tender-intelligence:test python -c "from app import main; print('OK')"` prints OK
- Image pushed to ACR with both `:latest` and `:sha-<commit>` tags

---

### Step 3 — Load secrets into Key Vault

**Goal:** Every credential the Job needs is in Key Vault, never in the
image, env file, or repo.

**Mandatory secrets (production):**

| Secret name | What it is | Source |
|---|---|---|
| `tarjouspalvelu-email` | Service-account login email | CGI / Riku |
| `tarjouspalvelu-password` | Service-account password | CGI / Riku |
| `hilma-api-key` | Hilma AVP-Read API key | Free, self-service at developer portal |
| `openai-api-key` | OpenAI key | CGI procurement |
| `graph-tenant-id` | Entra tenant GUID | CGI Entra admin |
| `graph-client-id` | App registration client ID | CGI Entra admin |
| `graph-client-secret` | App registration secret (app-only auth path) | CGI Entra admin |
| `smtp-user` / `smtp-password` | M365 SMTP relay creds (if Option A in Step 6) | CGI M365 admin |

**Options for getting secrets into the container:**

- **A. Container Apps secret references with Managed Identity (recommended).**
  The Job's secret list references Key Vault URIs; the platform fetches at start.
  No secrets in env files, no client code changes.
- **B. Manual `az containerapp job update --secrets …`** — ok for personal
  Azure, brittle in production.
- **C. Bake into the image** — never. Don't.

**Definition of done:**

- `az keyvault secret list --vault-name <kv>` shows every name in the table
- The Container Apps Job spec (Bicep) references Key Vault URIs, not literal values
- Test run: container starts, fetches a secret, logs `[ENV] secrets loaded`

---

### Step 4 — Deploy the scraper Job

**Goal:** The nightly scrape runs unattended on a cron trigger.

**Options:**

- **A. Container Apps Job, schedule-triggered (recommended).** Built-in cron.
  Container is ephemeral — spun up at the trigger, killed after run. No
  always-on cost. Verified working from North Europe.
- **B. Azure Functions (Python).** Cheaper but Chrome is hard to get running
  reliably; rejected during PoC.
- **C. Azure VM with cron + Xvfb.** The original plan, still works, but
  ~€30/month always-on cost vs ~€2–4/month for Container Apps Jobs.
  Use only if Container Apps Jobs are blocked by CGI policy.

**Job configuration:**

| Setting | Value | Why |
|---|---|---|
| `cpu` / `memory` | **2.0 / 4.0Gi minimum** | B1s (1 GB) crashes Chrome under load — verified 2026-04-23 |
| `replicaTimeout` | 1200 s (20 min) | Typical run is 7–15 min; 20 min gives headroom |
| `triggerType` | Schedule | Cron |
| `cronExpression` | `0 6 * * *` (Container Apps uses UTC) | 06:00 UTC = 09:00 EEST in summer / 08:00 EET winter |
| `parallelism` | 1, `replicaCompletionCount` 1 | This is a singleton run, not a fan-out |
| `replicaRetryLimit` | 1 | Re-trying a failed scrape against tarjouspalvelu within minutes can compound rate-limit issues; let alerting handle it |
| `volumes` | (none) | DB writes go to Azure SQL via `DATABASE_URL`; no volume needed. Local dev uses SQLite under `data/` |

**Cron timing tradeoffs:** earlier than 06:00 EEST risks Hilma not having
yesterday's notices indexed. Later than 09:00 EEST means the digest arrives
mid-morning, which is too late for procurement teams to react same-day.
06:00 EEST is the documented sweet spot.

**Definition of done:**

- `az containerapp job execution list -n scraper-job` shows successful executions
- Test execution logs end with `[run-summary] tenders_found=N duration_s=X status=ok`
- The Azure SQL DB has new rows for the current day's tenders (`SELECT COUNT(*) FROM tenders WHERE first_seen >= CAST(GETDATE() AS DATE)`)

---

### Step 5 — Wire up SharePoint upload

**Goal:** Tender ZIPs land in the configured SharePoint staging library
and the digest email links to them.

This is the most variable step because there are **three auth modes** the
existing `app/sharepoint.py` already supports. Pick one based on what CGI
provisions. Walkthrough: [`docs/sharepoint_setup.md`](../docs/sharepoint_setup.md).

**Options:**

| Mode | Use case | Auth | Pros | Cons |
|---|---|---|---|---|
| **1. Personal OneDrive** | Phase 1a personal-Azure simulation | Device-code (delegated) | Zero CGI involvement, instant setup | Not production |
| **2. CGI delegated (user)** | Pilot phase if app-only is delayed | Device-code (delegated, CGI tenant) | Works under user identity | Token refresh needed for unattended runs; brittle |
| **3. CGI app-only (recommended for prod)** | Production | Client credentials (`GRAPH_CLIENT_SECRET`) | Fully unattended, scoped to one site | Requires Entra admin consent + Sites.ReadWrite.All |

**Env vars** (set in Key Vault, surfaced as Container Apps secrets):

```
GRAPH_TENANT_ID=<cgi-tenant-guid>
GRAPH_CLIENT_ID=<app-registration-client-id>
GRAPH_CLIENT_SECRET=<secret>          # presence triggers app-only mode
SHAREPOINT_SITE_HOST=cgi.sharepoint.com
SHAREPOINT_SITE_PATH=/sites/TenderAgent
SHAREPOINT_FOLDER=Tender-Staging
ENABLE_SHAREPOINT_UPLOAD=1
```

**Definition of done:**

- A test ZIP uploaded via `python -m app.sharepoint <local.zip>` lands in the
  expected SP library
- `webUrl` returned by the upload is included in the digest email body
  (look for "SharePoint:" line in the rendered preview)
- The Job's Managed Identity / app registration can ONLY read/write the
  configured site (Application Access Policy, not tenant-wide)

---

### Step 6 — Service mailbox + reply tracker

**Goal:** Outbound digests come from a clearly-non-human mailbox; replies
to those digests update tender claim state.

**Provisioning (CGI side — see pre-flight #3, #4):**

- A **shared mailbox** in CGI M365 (free, no license). Naming candidates: `tarjousagentti@cgi.com`, `tender-agent@cgi.com`.
- Same Entra App Registration as Step 5, with `Mail.Send`, `Mail.Read`, `Mail.ReadWrite` scoped to this mailbox via Application Access Policy.

**Outbound send — options:**

- **A. SMTP relay (`smtp.office365.com:587`)** — simplest, password auth (App Password if MFA on).
- **B. Microsoft Graph `/users/{mailbox}/sendMail` (recommended for production)** — token-based, no password, audit trail.

The current `app/notify.py` uses SMTP. Swapping to Graph is a ~half-day swap.

**Inbound polling — `app/reply_tracker.py`:**

The module is currently a stub with the intended shape documented inline.
Implementation plan (matches [`docs/project_spec.md`](../docs/project_spec.md) § 3.4):

1. Second Container Apps Job, `cronExpression: "0 7-17/2 * * 1-5"` (every 2 h, 07:00–17:00 EEST, weekdays)
2. Polls `GET /users/{mailbox}/messages?$filter=isRead eq false`
3. For each: parse `[TENDER-<tp_id>]` from subject; resolve sender; skip if auto-reply (`Auto-Submitted: auto-replied` header, OOO subject markers)
4. Write claim state to Azure SQL via `DATABASE_URL` (same connection pattern as the scraper Job; Azure SQL handles concurrent writes natively, so no Blob round-trip needed)
5. Mark message read
6. Trigger dashboard re-render (Step 7)

**Definition of done:**

- A test reply to a digest email updates the tender's row in Azure SQL (`SELECT status, claimed_by, claimed_at FROM tenders WHERE tp_id = …`)
- An OOO auto-reply does NOT update state
- Reply tracker Job execution succeeds on schedule

---

### Step 7 — Stand up the koontinäkymä

**Goal:** A single read-only HTML page that anyone in CGI can open to see
today's tenders, awaiting-action list, claimed list, and deadline countdown.
Regenerated at the end of each scraper Job run + each reply-tracker Job run.

**Options:**

- **A. Azure Storage static website (cheapest)** — `index.html` blob in a
  `$web` container, public URL. Add Front Door or App Gateway in front for auth
  if needed.
- **B. Azure Static Web App (recommended)** — has Entra ID app-level auth
  built-in (`staticwebapp.config.json`). Slightly more cost but zero auth
  code. Free tier may be sufficient.
- **C. Behind App Service + a tiny Flask app** — overkill for read-only HTML;
  consider only if you also need the F5 dashboard later.

The current `app/dashboard.py` is a stub. Implementation:

- Jinja template `templates/dashboard.html`
- Read from Azure SQL via `DATABASE_URL`, group by tier / department / claim state
- Render to `data/dashboard/index.html` locally
- Upload to `<storage>.blob.core.windows.net/$web/index.html` in production with `Cache-Control: max-age=300`

**Definition of done:**

- Browsing to the dashboard URL (signed in as a CGI user if Option B) shows
  today's tenders and counts that match what the digest email said
- Page is regenerated after every scrape and every reply-tracker run
- Stale pages are evicted on next run (cache headers respected)

---

### Step 8 — Enable Defender for Storage on the staging container

**Goal:** Every ZIP that arrives in `staging/` is scanned for malware before
it ever reaches SharePoint.

**Recommended:** Microsoft Defender for Storage. Native, no extra
infrastructure, ~€0.15 per 1,000 transactions. Step-by-step runbook:
[`docs/defender_runbook.md`](../docs/defender_runbook.md) — 6 steps, takes
about an hour the first time.

**Alternatives:**

- ClamAV in the container — simpler infrastructurally, no central alerting; not recommended.
- "Trust the source portal" — explicitly **not recommended**; attachments are attacker-controlled in a supply-chain sense.

**Definition of done:**

- Defender enabled at subscription scope (or just Storage scope)
- Action Group sends malware alerts to the SecOps inbox
- An EICAR test file uploaded to the staging container is detected, quarantined, and an alert fires
- A real, clean tender ZIP uploaded to staging passes scanning and gets the
  `Microsoft.Security/scanResults` "No threats found" tag

---

### Step 9 — Alerting and runbooks

**Goal:** Real failures page someone within minutes; transient noise
doesn't.

**Alert rules to create:**

| Signal | Threshold | Action | Why |
|---|---|---|---|
| Scraper Job execution failure | Any `Failed` status | Email Action Group | Run won't self-heal |
| Scraper Job runtime | > 20 minutes | Email | Either Cloudflare changed or Cloudia is slow; investigate before next run |
| Tender count anomaly | < 50% of trailing 7-day average | Email | Possible site change, login broken, or filter misconfigured |
| Defender for Storage detection | Any malware detection | Page SecOps | Containment matters here |
| Key Vault access failure | Any `AccessDenied` | Email | MI / RBAC drift |
| Reply tracker Job failure | Any `Failed` status | Email (lower priority) | Not blocking the scrape |
| OpenAI spend | > €X/month projected | Email | Cap the bleed |

All alerts via **Action Group** → email distribution list. Use a single
Action Group; per-alert email is harder to operate. SMS / Teams webhooks are
overkill at this volume.

**Definition of done:**

- Each rule above exists in Azure Monitor with a verified Action Group
- Test alert fired (force a Job failure) — email received by on-call inbox

---

### Step 10 — CI/CD pipeline

**Goal:** A push to `main` (or merge of a PR) results in a new image in
ACR, ready for the next scheduled run.

**Options:**

- **A. GitHub Actions (recommended).** Skeleton at [`pipelines/build-and-push.yml`](pipelines/build-and-push.yml).
  Auth via OIDC federation, no long-lived AZURE_CREDENTIALS secret.
- **B. Azure DevOps Pipelines.** Use only if CGI standardises on it.

**Recommended pipeline shape:**

```
on push to main:
  - lint (ruff)
  - smoke test (run --mode=offline against fixture data)
  - docker build -f deploy/Dockerfile
  - az acr login + docker push (latest + sha-<commit>)
  - az containerapp job start  (immediate validation run; optional)
on PR:
  - lint + smoke test only (no build, no push)
```

**Image versioning:** never deploy `latest` to production. The Container
Apps Job spec in Bicep should pin to `sha-<commit>` and bump on deploy.
This makes rollback a one-line Bicep parameter change.

**Definition of done:**

- A trivial PR (e.g. README typo) runs CI and shows green
- A merge to main produces a new image tag in ACR
- Manual `az containerapp job update --image …:sha-<commit>` rolls forward
- Reverting to the previous tag rolls back

---

### Step 11 — Smoke test in staging

**Goal:** Prove the full pipeline works end-to-end against real (non-CGI)
endpoints before pointing it at production data.

**The "staging" environment** during personal-Azure simulation = personal
Azure subscription pointing at:
- Personal OneDrive (instead of CGI SharePoint)
- Gmail SMTP (instead of CGI M365)
- Ville's tarjouspalvelu account (instead of CGI service account)
- Personal OpenAI key

**Test sequence:**

1. Trigger a manual Job execution (`az containerapp job start`)
2. Watch Log Analytics for the structured `[run-summary]` line
3. Verify a digest email arrives in the test inbox
4. Verify ZIPs land in the configured upload target
5. Verify Defender for Storage scanned them ("Microsoft.Security/scanResults" property)
6. Verify the koontinäkymä static page is regenerated
7. Reply to the digest from a different test address; verify reply-tracker Job picks it up on next run

**Definition of done:** all 7 above succeed in 3 consecutive scheduled runs without manual intervention.

---

### Step 12 — Cut over to CGI Public + start pilot

**Goal:** Production runs against CGI infrastructure with the reviewer-gate
mode active.

**Cutover steps:**

1. `az deployment group create -g rg-tender-int-prod --template-file deploy/infra/main.bicep --parameters @deploy/infra/prod.bicepparam`
2. Re-paste secrets from personal Key Vault to CGI Key Vault
3. Push the production image tag (or pull-through from the staging registry)
4. Set `REVIEWER_MODE=1` and `REVIEWER_EMAIL=<reviewer>@cgi.com`
5. Set `ENABLE_SHAREPOINT_UPLOAD=1` after Step 5 verified
6. Manual smoke test (Step 11 sequence) against CGI endpoints
7. Enable the cron schedule

**Pilot duration:** 4 weeks shadow use. Per-week focus per spec § 10:

| Week | What | Outcome |
|---|---|---|
| 1 | Daily digests reviewed by reviewer; routing tuned | Updated `config/routing_config.xlsx` |
| 2 | Keyword + CPV refinements | Routing accuracy meets reviewer's bar |
| 3 | Add 2–3 BU-leader inboxes (willing early adopters) | Real-world feedback |
| 4 | Full routing on, monitor deliverability + relevance | **Go/no-go decision** with stakeholder |

If go: remove `REVIEWER_MODE=1`, route digests directly to BU leaders.

---

## Configuration reference

All env vars consumed by the application. Mark as **secret** for Key Vault.

### Application gates

| Var | Default | Production setting | What it does |
|---|---|---|---|
| `ENABLE_EMAIL` | `0` | `1` | Send real emails (vs HTML preview) |
| `ENABLE_SUMMARIZATION` | `1` | `1` | OpenAI summary per tender |
| `ENABLE_ANALYSIS` | `1` | `1` | Award winner / price / competitor extraction |
| `ENABLE_DETAIL_SCRAPE` | `0` | `1` | Per-tender detail page tabs (slower, richer data) |
| `ENABLE_METADATA_EXTRACTION` | `0` | `1` | Scoring / contract / reservations extraction |
| `ENABLE_SHAREPOINT_UPLOAD` | `0` | `1` | Graph upload of ZIPs |
| `ENABLE_DOWNLOAD_ATTACHMENTS` | `1` | `1` | ZIP download from tarjouspalvelu |
| `REVIEWER_MODE` | `0` | `1` (pilot) → `0` (post-pilot) | Route ALL digests to one reviewer |

### Limits

| Var | Default | Notes |
|---|---|---|
| `SUMMARIZE_COUNT` | `10` | Max summaries per run |
| `ANALYSIS_COUNT` | `20` | Max award analyses per run |
| `DETAIL_SCRAPE_COUNT` | `0` (= all) | Cap detail scrapes if cost is a concern |
| `MAX_EMAILS` | `0` (= all) | Cap on number of department digests sent |
| `OPENAI_MODEL` | `gpt-4.1-nano` | Use `gpt-4o-mini` for production quality |
| `HEADLESS` | `1` | Always 1 in containers (no display) |
| `HILMA_DAYS` | `1` | Look-back window for Hilma queries |
| `DATABASE_URL` | (unset → `sqlite:///data/tenders.db`) | Connection string. Production: `mssql+pyodbc://USER:PASS@SERVER.database.windows.net:1433/DBNAME?driver=ODBC+Driver+18+for+SQL+Server` |

### Credentials (all **secret** — Key Vault in production)

| Var | Source |
|---|---|
| `TARJOUSPALVELU_EMAIL` / `TARJOUSPALVELU_PASSWORD` | CGI service account |
| `HILMA_API_KEY` | Free, self-service at developer portal |
| `OPENAI_API_KEY` | OpenAI / Azure OpenAI |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | CGI M365 SMTP relay |
| `GRAPH_TENANT_ID` / `GRAPH_CLIENT_ID` / `GRAPH_CLIENT_SECRET` | Entra App Registration |
| `SHAREPOINT_SITE_HOST` / `SHAREPOINT_SITE_PATH` / `SHAREPOINT_FOLDER` | CGI SharePoint admin |
| `REVIEWER_EMAIL` | Stakeholder choice (pilot only) |
| **`DATABASE_URL`** | **CGI Azure SQL admin — connection string for the production database. Use Managed Identity authentication where possible (`Authentication=ActiveDirectoryMsi`) instead of SQL auth password.** |

Authoritative file with comments: [`.env.example`](../.env.example).

---

## Operations

### What an on-call engineer needs to know

**Where logs live:**
- Container Apps Job execution logs → Log Analytics (`ContainerAppConsoleLogs_CL`)
- Application structured logs → same; look for `[run-summary]`, `[hilma]`, `[tarjouspalvelu]`, `[ai]`, `[sharepoint]`, `[smtp]` prefixes
- Failure replay: clone the failed execution and re-run with `DEMO_PAUSE=1` env var (won't actually pause in headless, but enables verbose mode)

**Common failure modes:**

| Symptom | Likely cause | First action |
|---|---|---|
| Job runs > 20 min | Cloudia detail-page UI changed, scraper looping on a missing element | Check log for stuck `WebDriverWait`; re-test the affected selector |
| Cloudflare challenge appears | Chrome version drift OR datacenter IP reputation degraded | Update `undetected-chromedriver`; if persistent, contact CGI to whitelist |
| All Hilma queries return 0 | API key revoked / SSL intercept change | Re-test API key from local with `verify=False` toggled |
| Email sends fail | SMTP password rotated / Graph token expired | Check Key Vault; rotate; redeploy |
| OpenAI 429s | Rate limit / spend cap | Check OpenAI usage console; lower `SUMMARIZE_COUNT` for one run |
| SharePoint upload 401 | App registration secret expired | Renew secret in Entra; update Key Vault; redeploy |

**Manual one-off run:**
```bash
az containerapp job start \
  --resource-group rg-tender-int-prod \
  --name scraper-job
```

**Pause the schedule** (e.g. for maintenance):
```bash
az containerapp job update \
  --resource-group rg-tender-int-prod \
  --name scraper-job \
  --trigger-type Manual
```

**Resume:**
```bash
az containerapp job update \
  --resource-group rg-tender-int-prod \
  --name scraper-job \
  --trigger-type Schedule \
  --cron-expression "0 6 * * *"
```

---

## Cost expectations

Per spec § 5.1, at expected production scale (~300 tenders/day, full pipeline):

| Item | Monthly cost |
|---|---|
| Container Apps Job execution (scraper + reply tracker) | ~€3–5 |
| ACR Basic | ~€4 |
| Key Vault | ~€0.50 |
| Blob Storage (50 GB growth) | ~€1 |
| **Azure SQL Database (Serverless GP, auto-pause)** | **~€15–40** (idle most of the day) |
| Log Analytics (within free quota) | €0 |
| Defender for Storage | ~€0.50 |
| Static Web App | €0–9 |
| **Azure subtotal** | **~€25–60** |
| OpenAI (gpt-4o-mini, ~300 tenders/day) | ~€20–30 |
| Hilma API | free |
| **All-in monthly** | **~€45–90** |

Phase 1a personal-Azure simulation cost: ~€40–65/month, covered by Azure's
€200 first-month free credit for the first ~3–4 weeks.

**Why Azure SQL is in MVP and not deferred:** see [`docs/project_spec.md`](../docs/project_spec.md) § 17.4. Short version: analytics readiness (Power BI, ad-hoc T-SQL, F5–F7 features) requires a queryable multi-reader store from day one; migrating off SQLite later is more painful than starting on Azure SQL now. Cost delta is small relative to the budget.

---

## Migration: personal Azure → CGI Public

If phase 1a was used, migration is essentially a Bicep redeploy with new
parameters + secrets re-paste + endpoint swap. Estimated 0.5–1 day:

1. `az deployment group create … --parameters @prod.bicepparam` (creates CGI-side resources)
2. For each Key Vault secret in personal: `az keyvault secret show` → `az keyvault secret set` in CGI vault
3. Update SharePoint env vars to point at the CGI staging library
4. Update SMTP env vars to point at CGI M365
5. Swap `tarjouspalvelu-email` / `password` to the CGI service account
6. Push the same image tag from personal ACR into CGI ACR (or rebuild from main)
7. Smoke test (Step 11)
8. Enable schedule

The application code does not change at all — every endpoint difference is
absorbed by environment variables.

---

## Open decisions awaiting CGI input

These do **not** block deployment work — `prod.bicepparam` placeholders
let you proceed — but they need answers before the cutover (Step 12).

See [`docs/project_spec.md`](../docs/project_spec.md) § 14 for the full list.
The deployment-relevant subset:

1. **Authoritative CPV list?** (developer-assumed prefixes 72/48/64/79/80/85 are placeholder)
2. **OpenAI direct or Azure OpenAI?** (affects Bicep + the OpenAI client constructor)
3. **CI/CD tool standard — GitHub Actions or Azure DevOps?**
4. **IaC standard — Bicep or Terraform?**
5. **Region — North Europe (verified) or West Europe / Sweden Central?**
6. **SharePoint target site + library?**
7. **Service mailbox final address?**
8. **Reviewer mailbox + reviewer person?**

---

## Appendix — pointers to other docs

- **Authoritative spec:** [`docs/project_spec.md`](../docs/project_spec.md) — read this for "what to build"
  - § 10.2 — pilot acceptance criteria (10 measurable gates)
  - § 12.4–12.7 — comprehensive work estimate with workstream breakdown + risks
  - § 14 — open decisions awaiting CGI input
  - § 16 — glossary of Finnish procurement terms
  - § 17 — key technical decisions log (the *why* of each major choice)
- **MVP checklist:** [`docs/tasks.md`](../docs/tasks.md) — close items as they land
- **Verbatim CGI requirements:** [`docs/mvp_requirements_stakeholder.md`](../docs/mvp_requirements_stakeholder.md) — Finnish, do not edit
- **SharePoint setup walkthrough:** [`docs/sharepoint_setup.md`](../docs/sharepoint_setup.md)
- **Defender for Storage runbook:** [`docs/defender_runbook.md`](../docs/defender_runbook.md)
- **Architecture / cost diagrams (HTML):** `docs/Tender_Intelligence_Architecture.html`, `…_Process_Flow.html`, `…_Production.html`, `…_Azure_Costs.html`, `…_Future_Agents.html`
- **Application internals reference:** [`.claude/CLAUDE.md`](../.claude/CLAUDE.md) — selectors, auth flow, API quirks

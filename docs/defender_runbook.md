# Microsoft Defender for Storage — enablement runbook

Deploy runbook for the Azure team. Enables antivirus scanning on the Blob
container where tender attachment ZIPs land before being uploaded to
SharePoint, addressing the stakeholder open question: *"Onko riskiä, että
liitetiedostojen mukana tulee haittaohjelmia, miten voitaisiin tehdä
virustarkistus?"*

This is the answer: let Azure's native malware scanner do it. No extra
container images, no ClamAV daemons, no custom virus-signature
management.

---

## Where this fits in the pipeline

```
┌──────────────────┐
│  Scraper         │
│  (Container Apps │
│   Job)           │
└────────┬─────────┘
         │ PUT zip
         ▼
┌──────────────────────┐      ┌─────────────────────────┐
│  Azure Blob          │◀─────┤  Microsoft Defender     │
│  container           │      │  for Storage             │
│  "tender-staging"    │──────▶  (Malware Scanning)      │
└────────┬─────────────┘      └─────────┬───────────────┘
         │                              │
         │  clean                       │ malware detected
         ▼                              ▼
┌──────────────────┐         ┌──────────────────────────┐
│  SharePoint      │         │  Defender for Cloud      │
│  upload          │         │  alert → Action Group    │
└──────────────────┘         │  → email / Teams webhook │
                             │  (AV-response runbook)   │
                             └──────────────────────────┘
```

Blob container serves as a **quarantine-by-default staging area**: every
object is scanned on write; only clean blobs proceed to SharePoint. The
scraper checks the blob's `Malware Scanning scan result` index tag after
upload and only passes the URL along when the result is `No threats
found`.

---

## Prerequisites

- Subscription with Defender for Cloud enabled
- Storage Account containing the tender-staging container (Standard
  general-purpose v2 recommended)
- Action Group configured to receive security alerts (email or Teams
  webhook)
- Owner or Storage Account Contributor role on the storage account
- Security Admin role on the subscription (to enable Defender plans)

---

## Step 1 — Enable Defender for Storage on the subscription

**Portal:**

1. Open **Microsoft Defender for Cloud → Environment settings**
2. Select the subscription hosting the tender-staging storage account
3. Under **Defender plans**, set **Storage** to **On**
4. Click **Settings** next to Storage and confirm:
   - **Pricing tier**: *Per Storage Account* (simpler billing) or
     *Per Transaction* (better for high-volume — our volume is low)
   - **Malware Scanning**: **On**
   - **Sensitive data threat detection**: On (optional, negligible cost)
5. Save

**CLI equivalent:**

```bash
az security pricing create \
  --name StorageAccounts \
  --tier Standard \
  --subplan PerStorageAccount
```

## Step 2 — Enable Malware Scanning for the specific storage account

Malware Scanning is the per-file-scan feature; it must be explicitly
enabled either at subscription level (Step 1) or per-account:

**Portal:**

1. Open the storage account → **Microsoft Defender for Cloud** blade
2. **Settings** → **Malware Scanning** → **On**
3. Cap monthly scans (optional): set a limit that matches your expected
   volume × headroom (e.g. 100 GB/month for our ~50 MB/day baseline)
4. Save

**CLI equivalent:**

```bash
az security defender-for-storage update \
  --resource-group "<rg>" \
  --account-name "<storage-account>" \
  --is-enabled true \
  --malware-scanning-on-upload-is-enabled true \
  --malware-scanning-on-upload-cap-gb-per-month 100
```

## Step 3 — Configure alert routing (what happens when malware is found)

**Create an Action Group:**

1. **Monitor → Alerts → Action groups → Create**
2. Name: `TenderAgent-SecurityAlerts`
3. Actions:
   - **Email**: `securityops@cgi.com` (or equivalent distribution)
   - (optional) **Webhook**: Teams channel for real-time ping
4. Save

**Create an alert rule:**

1. **Defender for Cloud → Security alerts → Alert rules → Create**
2. Signal: `Microsoft Defender for Storage — Malware Scanning`
3. Condition: severity ≥ Medium (detections are Medium by default)
4. Action: select the `TenderAgent-SecurityAlerts` group
5. Save

## Step 4 — Verify with an EICAR test file

The EICAR test string is a harmless signature all AV engines recognize
as malware. Safest way to prove the scanner is active.

```bash
# Create an EICAR test file (this string is the EU-ICAR test signature)
cat > /tmp/eicar.com <<'EOF'
X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*
EOF

# Upload to the tender-staging container
az storage blob upload \
  --account-name "<storage-account>" \
  --container-name "tender-staging" \
  --file /tmp/eicar.com \
  --name "eicar-test.com" \
  --auth-mode login
```

Expected outcomes (within ~60 seconds):

1. Blob index tag `Malware Scanning scan result` = **`Malicious`**
2. Security alert emitted with severity **Medium**
3. Email to the Action Group's recipient(s)

Clean up afterwards:

```bash
az storage blob delete \
  --account-name "<storage-account>" \
  --container-name "tender-staging" \
  --name "eicar-test.com" \
  --auth-mode login
```

## Step 5 — Verify a clean file passes

Upload any ordinary ZIP. Within ~60s the index tag should read
`No threats found`. The scraper reads this tag and only proceeds with
SharePoint upload when it's clean.

## Step 6 — How the scraper reads the scan result

Proposed logic (to be implemented when the SharePoint upload path is
live):

```python
def wait_for_scan_and_get_result(blob_client, timeout_s=120):
    """Poll the blob's scan-result index tag until set or timeout."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        tags = blob_client.get_blob_tags()
        result = tags.get("Malware Scanning scan result")
        if result:
            return result    # 'No threats found' | 'Malicious' | 'Scan failed'
        time.sleep(5)
    return None  # timed out — treat as suspect
```

Policy:
- `No threats found` → proceed with SharePoint upload
- `Malicious` → skip upload, log critical, mark tender with
  `attachment_scan=malicious` so the dashboard can flag it
- `Scan failed` / timeout → skip upload, log warning, revisit nightly
  (Defender sometimes retries)

## Cost expectations

- **Defender for Storage (plan)**: ~€0.02 / 10,000 transactions or
  ~€10/storage account/month on flat rate — choose the cheaper of the
  two based on volume
- **Malware Scanning**: ~€0.15 per GB scanned
- At MVP scale (~50 MB/day average, occasional 20 MB ZIP spikes) =
  roughly ~€0.30/month in scan charges. Well under €15/mo all-in.

## Troubleshooting

- **No scan result after 5 minutes** — confirm Malware Scanning is
  enabled on this specific storage account (Step 2). Subscription-level
  enablement doesn't auto-apply to newly created accounts.
- **No alerts reaching the Action Group** — Security alert rules have a
  deduplication window; re-upload EICAR with a new filename to retrigger.
- **Scans pause partway through the month** — monthly scan cap hit
  (Step 2). Raise the cap or switch to unlimited.
- **False positives on ZIPs** — rare, but report via Defender for Cloud
  UI if needed. Procurement documents from public portals are
  exceptionally unlikely to trigger this.

## Responsibilities

- **CGI Azure team** (deploy): Steps 1–3 during initial deployment
- **CGI SecOps**: receives and triages alerts from Step 3
- **Scraper owner** (developer): Step 6 implementation in production
  build

## Related

- Spec: `docs/project_spec.md` § 7.2.1 *Attachment antivirus scanning*
- Spec: `docs/project_spec.md` § 3.8 item 18
- Stakeholder open question: `docs/mvp_requirements_stakeholder.md` — *"Onko
  riskiä, että liitetiedostojen mukana tulee haittaohjelmia"*

# Graph API upload setup

How to point `sharepoint.py` at a real storage backend. Two paths:

1. **Personal OneDrive (PoC mock)** — fastest, zero governance overhead. Use this for development and to prove the pipeline works.
2. **CGI SharePoint (production)** — handled by the Azure team when production deployment starts. Requires a proper app registration + admin consent in CGI Entra ID. Not for the developer to set up solo.

For the MVP phase we use path 1.

---

## Path 1 — Personal OneDrive (recommended for PoC)

### Step 1. Make sure you have a personal Microsoft account

Not a CGI account. A free consumer Microsoft account — if you have a Hotmail, Outlook.com, MSN, Xbox, or Skype login, you already have one. You can also create one instantly at [account.microsoft.com](https://account.microsoft.com) using your Gmail.

### Step 2. Register an app in your own Entra (personal account)

1. Go to [portal.azure.com](https://portal.azure.com) and sign in **with your personal Microsoft account** (not your CGI one).
2. Open **Entra ID → App registrations → New registration**.
3. Name: `CGI Tender Agent — PoC`.
4. **Supported account types:** *Accounts in any organizational directory and personal Microsoft accounts (Multitenant + personal)*.
5. Redirect URI: leave blank.
6. Click Register.

After registration:

- Copy the **Application (client) ID**. This becomes `GRAPH_CLIENT_ID` in `.env`.
- **Authentication → Advanced settings → Allow public client flows:** toggle **Yes**, Save.
- **API permissions → Add → Microsoft Graph → Delegated permissions → `Files.ReadWrite`** → Add permission. (Just `Files.ReadWrite`. You do NOT need the `.All` variant for personal OneDrive.)

### Step 3. Wire `.env`

```
# Personal MSA → tenant is literally the string 'consumers'
GRAPH_TENANT_ID=consumers
GRAPH_CLIENT_ID=<paste your Application (client) ID>

# Leave these BLANK to target /me/drive (personal OneDrive)
SHAREPOINT_SITE_HOST=
SHAREPOINT_SITE_PATH=
SHAREPOINT_FOLDER=Tender-Staging

# Enable the upload hook
ENABLE_SHAREPOINT_UPLOAD=1
```

### Step 4. First-run sign-in

```
cd ~/projects/rfq-management && source venv/bin/activate
echo "hello tender agent" > /tmp/hello.txt
python sharepoint.py /tmp/hello.txt
```

You'll see something like:

```
  [graph] --- First-run authentication required ---
  [graph] To sign in, use a web browser to open https://microsoft.com/devicelogin
          and enter the code ABCDEFGH to authenticate.
  [graph] --- Waiting for you to sign in ---
```

Open the URL in a browser, enter the code, sign in with your **personal**
Microsoft account. The terminal resumes automatically. Token cached to
`.graph_token_cache.bin` (gitignored) — no prompt next time.

On success:

```
  [sharepoint] Uploaded to OneDrive: hello.txt  →  https://onedrive.live.com/...
```

Open the returned URL to confirm the file landed in your OneDrive under
the `Tender-Staging` folder.

---

## Path 2 — CGI SharePoint (production / Azure team)

The PoC phase **does not** use this path. Summarized here so the eventual
migration is documented.

- CGI's Azure team (not the developer) creates an app registration in the
  CGI Entra tenant with either delegated or app-only permissions.
- Grant `Files.ReadWrite.All` + `Sites.ReadWrite.All` — requires admin
  consent.
- For unattended automation, the production deployment should use
  **Managed Identity** via `DefaultAzureCredential` (a small code change
  in `sharepoint.py`'s `_acquire_token`). This eliminates secrets entirely.
- `.env` for production:

```
GRAPH_TENANT_ID=<cgi tenant GUID>
GRAPH_CLIENT_ID=<cgi app registration client ID>
GRAPH_CLIENT_SECRET=<if using client-credentials>
SHAREPOINT_SITE_HOST=cgi.sharepoint.com
SHAREPOINT_SITE_PATH=/sites/TenderAgent
SHAREPOINT_FOLDER=Tender-Staging
ENABLE_SHAREPOINT_UPLOAD=1
```

Code detects the mode automatically:
- `SHAREPOINT_SITE_HOST` + `_PATH` set → SharePoint flow
- `GRAPH_CLIENT_SECRET` set → app-only (client credentials) auth
- Otherwise → device-code delegated auth (PoC)

---

## Troubleshooting (both paths)

- **`AADSTS50020` / wrong account type** — you signed in with a CGI
  account when the app was registered for personal accounts, or vice
  versa. Use matching accounts, or re-register the app with "Multitenant
  + personal" as account type.
- **`invalid_client`** — `GRAPH_CLIENT_ID` or `GRAPH_TENANT_ID` is
  wrong. Copy-paste again from the app registration Overview.
- **`Forbidden`/`AccessDenied` on `/me/drive`** — delegated scope
  missing. Re-check API permissions, delete `.graph_token_cache.bin`,
  re-run to force a fresh sign-in.
- **Large files fail mid-way** — chunked upload sessions stay open on
  Microsoft's side for ~24 h; just re-run, it'll continue.

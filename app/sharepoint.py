"""Graph API upload for tender attachments.

Works in THREE modes depending on env config:

  1. Personal OneDrive (PoC mock)
     - GRAPH_TENANT_ID=consumers
     - GRAPH_CLIENT_ID=<your personal-MSA app registration>
     - SHAREPOINT_SITE_HOST / SHAREPOINT_SITE_PATH left blank
     - Uploads go to /me/drive
     - Scopes: Files.ReadWrite
     - Zero CGI tenant involvement — clean governance for PoC testing

  2. Personal CGI OneDrive-for-Business or personal site
     - GRAPH_TENANT_ID=<cgi tenant GUID>
     - SHAREPOINT_SITE_HOST=cgi-my.sharepoint.com
     - SHAREPOINT_SITE_PATH=/personal/ville_pajala_cgi_com
     - Requires a CGI app registration (consult CGI IT first)

  3. Production CGI staging SharePoint site
     - GRAPH_TENANT_ID=<cgi tenant GUID>
     - GRAPH_CLIENT_SECRET=<secret>  (switches to app-only auth)
     - SHAREPOINT_SITE_HOST=cgi.sharepoint.com
     - SHAREPOINT_SITE_PATH=/sites/TenderAgent

Mode selection is implicit:
  - SHAREPOINT_SITE_HOST + SITE_PATH blank → mode 1 (personal OneDrive)
  - Both set → mode 2 or 3 (SharePoint / OneDrive-for-Business)
  - GRAPH_CLIENT_SECRET set → app-only auth path
  - Otherwise → device-code delegated auth (first run prompts, token cached)

Handles both small uploads (direct PUT, ≤ 4 MB) and large files via
upload sessions (chunked, up to 60 GB). Our ZIPs have been up to 18 MB
so chunked is the common path, not a corner case.
"""
import os
import json
import time
from typing import Optional

import requests
from dotenv import load_dotenv

from .paths import ENV_PATH, GRAPH_TOKEN_CACHE

load_dotenv(ENV_PATH)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
# Scopes for personal OneDrive (mode 1). Sites.ReadWrite.All doesn't apply
# to personal Microsoft accounts — it's a work/school account scope.
SCOPES_ONEDRIVE_PERSONAL = ["Files.ReadWrite"]
# Scopes for SharePoint sites / OneDrive-for-Business (modes 2+3).
SCOPES_SHAREPOINT = ["Files.ReadWrite.All", "Sites.ReadWrite.All"]
SCOPES_APP_ONLY = ["https://graph.microsoft.com/.default"]
TOKEN_CACHE_PATH = str(GRAPH_TOKEN_CACHE)
SIMPLE_UPLOAD_LIMIT = 4 * 1024 * 1024  # Graph hard limit for single-PUT is 4 MB
CHUNK_SIZE = 5 * 1024 * 1024           # must be multiple of 320 KiB; 5 MiB qualifies


def _is_personal_onedrive_mode() -> bool:
    """True when we're targeting personal OneDrive (mode 1).

    Signal: neither SharePoint site host nor site path is configured.
    """
    return not (os.getenv("SHAREPOINT_SITE_HOST", "").strip()
                and os.getenv("SHAREPOINT_SITE_PATH", "").strip())


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _get_msal_apps():
    """Lazy import MSAL so we don't force the dependency on users who never
    call sharepoint.upload_file. Returns (PublicClientApplication, ConfidentialClientApplication, SerializableTokenCache)."""
    import msal  # noqa: WPS433 (intentional lazy import)
    return msal.PublicClientApplication, msal.ConfidentialClientApplication, msal.SerializableTokenCache


def _load_token_cache():
    _, _, SerializableTokenCache = _get_msal_apps()
    cache = SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_PATH):
        try:
            cache.deserialize(open(TOKEN_CACHE_PATH, "r").read())
        except Exception:
            pass
    return cache


def _save_token_cache(cache):
    if cache.has_state_changed:
        try:
            with open(TOKEN_CACHE_PATH, "w") as f:
                f.write(cache.serialize())
        except Exception as e:
            print(f"  [graph] Could not persist token cache: {e}")


def _acquire_token() -> str:
    """Return a valid Graph access token; interactively sign in on first run."""
    tenant = os.getenv("GRAPH_TENANT_ID", "").strip()
    client_id = os.getenv("GRAPH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GRAPH_CLIENT_SECRET", "").strip()
    if not tenant or not client_id:
        raise RuntimeError(
            "GRAPH_TENANT_ID and GRAPH_CLIENT_ID must be set in .env "
            "before SharePoint upload can work."
        )
    authority = f"https://login.microsoftonline.com/{tenant}"
    PublicApp, ConfidentialApp, _ = _get_msal_apps()

    # App-only (client credentials) when a secret is present — production path
    if client_secret:
        app = ConfidentialApp(client_id, client_credential=client_secret, authority=authority)
        result = app.acquire_token_for_client(scopes=SCOPES_APP_ONLY)
        if "access_token" not in result:
            raise RuntimeError(f"Graph client-credentials failed: {result}")
        return result["access_token"]

    # Delegated (device code) — PoC path. Token cache avoids re-prompting.
    # Scope set depends on target: personal OneDrive vs. SharePoint.
    delegated_scopes = (
        SCOPES_ONEDRIVE_PERSONAL if _is_personal_onedrive_mode() else SCOPES_SHAREPOINT
    )

    cache = _load_token_cache()
    app = PublicApp(client_id, authority=authority, token_cache=cache)

    # Try silent first (from cache)
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(delegated_scopes, account=accounts[0])
        if result and "access_token" in result:
            _save_token_cache(cache)
            return result["access_token"]

    # Interactive device-code flow
    flow = app.initiate_device_flow(scopes=delegated_scopes)
    if "user_code" not in flow:
        raise RuntimeError(f"Device flow failed to start: {flow}")
    print()
    print("  [graph] --- First-run authentication required ---")
    print(f"  [graph] {flow['message']}")
    print("  [graph] --- Waiting for you to sign in ---")
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(f"Device flow did not complete: {result}")
    _save_token_cache(cache)
    return result["access_token"]


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {_acquire_token()}"}


# ---------------------------------------------------------------------------
# Site / drive resolution
# ---------------------------------------------------------------------------

def resolve_drive_id(site_host: str, site_path: str) -> str:
    """Resolve the default document library's drive_id for a SharePoint site."""
    path = site_path.lstrip("/")
    url = f"{GRAPH_BASE}/sites/{site_host}:/{path}?$select=id"
    r = requests.get(url, headers=_auth_headers(), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(
            f"Could not resolve site '{site_host}{site_path}': "
            f"HTTP {r.status_code} {r.text[:200]}"
        )
    site_id = r.json()["id"]

    r = requests.get(f"{GRAPH_BASE}/sites/{site_id}/drive?$select=id",
                     headers=_auth_headers(), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(
            f"Could not read default drive for site {site_id}: "
            f"HTTP {r.status_code} {r.text[:200]}"
        )
    return r.json()["id"]


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def _drive_base(drive_id: str | None) -> str:
    """Return the drive-relative URL prefix for either personal OneDrive or
    a specific SharePoint drive. drive_id=None → /me/drive."""
    if drive_id is None:
        return f"{GRAPH_BASE}/me/drive"
    return f"{GRAPH_BASE}/drives/{drive_id}"


def upload_file(local_path: str, drive_id: str | None, target_path: str,
                conflict_behavior: str = "rename") -> dict:
    """Upload a local file to `target_path` inside the given drive.

    drive_id: the Graph drive ID for a SharePoint site, OR None to target
              the signed-in user's personal OneDrive (/me/drive).
    target_path: path relative to drive root, e.g. 'Tender-Staging/609121.zip'
    conflict_behavior: one of 'rename' | 'replace' | 'fail'

    Returns the DriveItem JSON (includes `webUrl` — the shareable link).
    """
    if not os.path.exists(local_path):
        raise FileNotFoundError(local_path)
    size = os.path.getsize(local_path)
    target_path = target_path.lstrip("/")

    if size < SIMPLE_UPLOAD_LIMIT:
        return _simple_upload(local_path, drive_id, target_path, conflict_behavior)
    return _chunked_upload(local_path, drive_id, target_path, conflict_behavior)


def _simple_upload(local_path, drive_id, target_path, conflict_behavior) -> dict:
    url = (f"{_drive_base(drive_id)}/root:/{target_path}:"
           f"/content?@microsoft.graph.conflictBehavior={conflict_behavior}")
    with open(local_path, "rb") as f:
        r = requests.put(url, headers=_auth_headers(), data=f.read(), timeout=120)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Simple upload failed: HTTP {r.status_code} {r.text[:200]}")
    return r.json()


def _chunked_upload(local_path, drive_id, target_path, conflict_behavior) -> dict:
    # 1. Create an upload session
    url = f"{_drive_base(drive_id)}/root:/{target_path}:/createUploadSession"
    body = {"item": {"@microsoft.graph.conflictBehavior": conflict_behavior}}
    r = requests.post(url, headers={**_auth_headers(), "Content-Type": "application/json"},
                      json=body, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"createUploadSession failed: HTTP {r.status_code} {r.text[:200]}")
    upload_url = r.json()["uploadUrl"]

    size = os.path.getsize(local_path)
    with open(local_path, "rb") as f:
        offset = 0
        while offset < size:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            end = offset + len(chunk) - 1
            headers = {
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {offset}-{end}/{size}",
            }
            r = requests.put(upload_url, headers=headers, data=chunk, timeout=600)
            if r.status_code == 202:   # intermediate ack
                offset = end + 1
                continue
            if r.status_code in (200, 201):   # final chunk — got the DriveItem back
                return r.json()
            raise RuntimeError(
                f"Chunk upload failed at byte {offset}: HTTP {r.status_code} {r.text[:200]}"
            )
    raise RuntimeError("Chunked upload finished without receiving a final DriveItem response")


# ---------------------------------------------------------------------------
# High-level convenience
# ---------------------------------------------------------------------------

def upload_tender_zip(local_zip_path: str, tender: dict) -> Optional[str]:
    """Upload a tender's ZIP to the configured OneDrive or SharePoint target.

    Reads SHAREPOINT_SITE_HOST / SHAREPOINT_SITE_PATH / SHAREPOINT_FOLDER
    from env. When the site vars are blank → personal OneDrive (/me/drive).
    Returns the shareable URL on success, None on any failure (failures
    are logged; the scraper continues).
    """
    folder = os.getenv("SHAREPOINT_FOLDER", "Tender-Staging").strip().strip("/")
    personal = _is_personal_onedrive_mode()

    if personal:
        drive_id = None   # /me/drive
        target_label = "OneDrive"
    else:
        site_host = os.getenv("SHAREPOINT_SITE_HOST", "").strip()
        site_path = os.getenv("SHAREPOINT_SITE_PATH", "").strip()
        try:
            drive_id = resolve_drive_id(site_host, site_path)
        except Exception as e:
            print(f"  [sharepoint] Could not resolve drive: {e}")
            return None
        target_label = f"{site_host}{site_path}"

    filename = os.path.basename(local_zip_path)
    target = f"{folder}/{filename}" if folder else filename
    try:
        item = upload_file(local_zip_path, drive_id, target)
    except Exception as e:
        print(f"  [sharepoint] Upload failed for {filename}: {e}")
        return None

    web_url = item.get("webUrl", "")
    print(f"  [sharepoint] Uploaded to {target_label}: {filename}  →  {web_url}")
    return web_url


if __name__ == "__main__":
    # CLI: `python sharepoint.py <local_file>` — one-shot upload test
    import sys
    if len(sys.argv) < 2:
        print("usage: python sharepoint.py <local_file>")
        sys.exit(1)
    url = upload_tender_zip(sys.argv[1], tender={})
    print(f"Result: {url}")

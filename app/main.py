"""
Demo: Scrape public procurement notices from tarjouspalvelu.fi.

Uses undetected-chromedriver to bypass Cloudflare Turnstile bot detection.
Navigates to the publications listing and extracts procurement notices.
"""

import json
import os
import sys
import time
from datetime import datetime

import undetected_chromedriver as uc
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException

from .paths import ENV_PATH, CHROME_PROFILE, DOWNLOADS, DEMO_RESULTS

# Load credentials from .env (never hardcoded, never sent to cloud)
load_dotenv(ENV_PATH)

PROFILE_DIR = str(CHROME_PROFILE)
DOWNLOADS_DIR = str(DOWNLOADS)

# Known organization IDs on tarjouspalvelu.fi (used only when an explicit
# org argument is passed, e.g. for dev/testing against a single org).
# Production / default scraping uses /Default/Index which returns tenders
# from ALL Finnish organisations.
ORGANIZATIONS = {
    "helsinki": "13",
    "espoo": "8",
    "vantaa": "30",
    "tampere": "25",
    "oulu": "19",
    "turku": "28",
}

# Sentinel value meaning "all of Finland via /Default/Index global search"
GLOBAL_ORG = "global"


from .logger import log_to_file, clear_log


def log(msg: str):
    """Print a timestamped log message and write to log file."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] {msg}")
    log_to_file(msg)


def log_step(step: int, msg: str):
    """Print a major step header."""
    ts = datetime.now().strftime("%H:%M:%S")
    header = f"STEP {step}: {msg}"
    print(f"\n{'='*60}")
    print(f"  {header}")
    print(f"  Time: {ts}")
    print(f"{'='*60}")
    log_to_file(f"\n{'='*50}")
    log_to_file(header)
    log_to_file(f"{'='*50}")


def create_driver() -> uc.Chrome:
    headless = os.getenv("HEADLESS", "0") == "1"
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=fi-FI")
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
    # Set download directory for ZIP attachments
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    prefs = {"download.default_directory": DOWNLOADS_DIR, "download.prompt_for_download": False}
    options.add_experimental_option("prefs", prefs)
    profile_dir = os.getenv("CHROME_PROFILE_DIR", PROFILE_DIR)
    if headless and profile_dir == PROFILE_DIR:
        # Avoid collision with the visible profile when both run in sequence
        profile_dir = PROFILE_DIR + "_headless"
    log(f"Chrome mode: {'HEADLESS=new' if headless else 'VISIBLE'} | profile: {os.path.basename(profile_dir)}")
    return uc.Chrome(options=options, user_data_dir=profile_dir)


def wait_for_cloudflare(driver, timeout=60) -> bool:
    """Wait for Cloudflare Turnstile to auto-resolve."""
    log("Checking for Cloudflare bot protection...")
    for i in range(timeout // 2):
        page_source = driver.page_source
        if "Tarkistetaan suojausta" not in page_source and "challenge-platform" not in page_source:
            log("Cloudflare challenge resolved — access granted.")
            return True
        if i == 0:
            log("Cloudflare Turnstile detected — waiting for auto-resolve...")
        if i > 0 and i % 5 == 0:
            log(f"Still waiting for Cloudflare... ({i*2}s elapsed)")
        time.sleep(2)
    log("ERROR: Cloudflare did not resolve within timeout.")
    return False


def dismiss_cookie_popup(driver):
    """Dismiss the Usercentrics cookie consent popup (renders in Shadow DOM)."""
    log("Looking for cookie consent popup (Usercentrics Shadow DOM)...")
    time.sleep(2)  # Give the popup time to render
    try:
        result = driver.execute_script("""
            const host = document.getElementById('usercentrics-cmp-ui');
            if (!host) return 'no-host-element';
            if (!host.shadowRoot) return 'no-shadow-root';

            const buttons = host.shadowRoot.querySelectorAll('button');
            for (const btn of buttons) {
                const text = btn.textContent.trim().toLowerCase();
                if (text === 'deny' || text === 'hylkää') {
                    btn.click();
                    return 'denied';
                }
            }

            const links = host.shadowRoot.querySelectorAll('a, button, [role="button"]');
            for (const el of links) {
                const text = el.textContent.trim().toLowerCase();
                if (text.includes('continue without') || text.includes('jatka hyväksymättä')) {
                    el.click();
                    return 'continued';
                }
            }

            return 'button-not-found';
        """)
        if result == "denied":
            log("Cookie popup dismissed — clicked 'Deny'.")
        elif result == "continued":
            log("Cookie popup dismissed — clicked 'Continue without accepting'.")
        elif result == "no-host-element":
            log("No cookie popup detected (already dismissed or not present).")
        elif result == "no-shadow-root":
            log("Cookie popup host found but Shadow DOM not ready — retrying...")
            time.sleep(2)
            dismiss_cookie_popup(driver)
        else:
            log(f"Cookie popup: could not find dismiss button ({result}).")
        time.sleep(1)
    except Exception as e:
        log(f"Cookie popup handling error: {e}")


def login(driver) -> bool:
    """Log in to tarjouspalvelu.fi via Cloudia Services redirect.

    Flow:
    1. Enter email in top-right field on tarjouspalvelu.fi → click Login
    2. Redirects to Cloudia Services login page
    3. Enter username + password → click Kirjaudu sisään
    4. Redirects back to tarjouspalvelu.fi logged in
    """
    email = os.getenv("TARJOUSPALVELU_EMAIL")
    password = os.getenv("TARJOUSPALVELU_PASSWORD")

    if not email or not password or email.startswith("FILL_IN"):
        log("No credentials found in .env — skipping login (limited data access).")
        return False

    masked = email[:3] + "***" + (email[email.index("@"):] if "@" in email else "")
    log(f"Logging in as {masked}")

    try:
        # Step 1: Navigate to global portal and enter email
        log("Step 1: Navigating to global portal for login...")
        driver.get("https://tarjouspalvelu.fi/Default/Index")
        time.sleep(8)

        # Handle Cloudflare if needed
        if "Tarkistetaan" in driver.page_source:
            log("Cloudflare challenge on login page...")
            for _ in range(15):
                time.sleep(2)
                if "Tarkistetaan" not in driver.page_source:
                    break

        log("Entering email on global portal...")
        user_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "user"))
        )
        user_field.clear()
        user_field.send_keys(email)
        log("Email entered.")

        # Click the #continue button (NOT #oldlogin!) — this triggers SSO redirect to Cloudia Services
        continue_btn = driver.find_element(By.ID, "continue")
        driver.execute_script("arguments[0].click();", continue_btn)
        log("'Log in' (SSO) clicked — waiting for redirect to Cloudia Services...")

        # Smart wait: poll for either the Cloudia URL + the #username form field
        # to appear, or timeout. Better than a fixed 10s sleep because Vaadin
        # apps can take 5-25s to render depending on network/load.
        sso_deadline = time.time() + 45
        sso_last_heartbeat = time.time()
        cloudia_ready = False
        while time.time() < sso_deadline:
            url_now = driver.current_url
            on_cloudia = "login.cloudia.net" in url_now or "cloudia" in url_now.lower()
            if on_cloudia and driver.find_elements(By.ID, "username"):
                cloudia_ready = True
                break
            if time.time() - sso_last_heartbeat >= 10:
                remaining = int(sso_deadline - time.time())
                has_username = bool(driver.find_elements(By.ID, "username"))
                log(f"  ...waiting for Cloudia login page ({remaining}s remaining). URL: {url_now}, username-field: {has_username}")
                sso_last_heartbeat = time.time()
            time.sleep(0.5)

        # Step 2: Should now be on Cloudia Services login page
        log(f"Step 2: Redirected to: {driver.current_url}")
        driver.save_screenshot("screenshot_cloudia_login.png")

        if cloudia_ready:
            log("On Cloudia Services login page (Vaadin app) — entering credentials...")

            # Username: input#username (Vaadin text field) — may be pre-filled from URL
            username_field = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            current_val = username_field.get_attribute("value") or ""
            if current_val.strip() == email.strip():
                log("Username already pre-filled correctly.")
            else:
                username_field.clear()
                time.sleep(0.5)
                # Triple-clear to handle Vaadin
                driver.execute_script("arguments[0].value = '';", username_field)
                username_field.send_keys(email)
                log("Username entered (input#username).")

            # Password: nested inside div#password > ... > input[type=password]
            time.sleep(1)
            pw_field = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#password input[type='password']"))
            )
            # Clear properly — Vaadin fields can be tricky
            driver.execute_script("arguments[0].value = '';", pw_field)
            pw_field.click()
            time.sleep(0.5)
            pw_field.send_keys(password)
            log("Password entered.")

            # Click the green "Log In" button — Vaadin div#login-btn
            # Use Selenium's native click (not JS) to trigger Vaadin's event handling
            login_div = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "login-btn"))
            )
            ActionChains(driver).move_to_element(login_div).click().perform()
            log("Clicked 'Log In' button (native click on div#login-btn).")



            log("Waiting for redirect back to tarjouspalvelu.fi/Default/Index...")
            # Manual poll loop so we emit a heartbeat log every ~10s, instead
            # of sitting silently inside WebDriverWait for up to 45s.
            redirect_deadline = time.time() + 45
            redirect_completed = False
            last_heartbeat = time.time()
            while time.time() < redirect_deadline:
                if "/Default/Index" in driver.current_url:
                    redirect_completed = True
                    log(f"Redirect chain completed. URL: {driver.current_url}")
                    break
                if time.time() - last_heartbeat >= 10:
                    remaining = int(redirect_deadline - time.time())
                    log(f"  ...still waiting for redirect ({remaining}s remaining). Current URL: {driver.current_url}")
                    last_heartbeat = time.time()
                time.sleep(0.5)

            if not redirect_completed:
                # Redirect didn't happen client-side. Two possibilities:
                #   (a) Auth succeeded server-side but the final redirect JS didn't fire (common headless issue)
                #   (b) Auth is genuinely failing (server waiting on a check we didn't pass)
                # Dump diagnostics, then try force-navigating to /Default/Index to find out which.
                log(f"Timeout at: {driver.current_url}")
                try:
                    cookies = driver.get_cookies()
                    cookie_names = sorted(c.get("name", "") for c in cookies)
                    log(f"Cookies ({len(cookies)}): {cookie_names}")
                    with open("page_source_login_stuck.html", "w", encoding="utf-8") as f:
                        f.write(driver.page_source or "")
                    log(f"Stuck page source size: {len(driver.page_source or '')} bytes "
                        "(saved to page_source_login_stuck.html)")
                except Exception as e:
                    log(f"Could not collect diagnostics: {e}")
                log("Attempting force-navigate to /Default/Index to see if session carries...")
                try:
                    driver.get("https://tarjouspalvelu.fi/Default/Index")
                    WebDriverWait(driver, 20).until(
                        lambda d: "/Default/Index" in d.current_url
                    )
                    log(f"Force-navigate landed on: {driver.current_url}")
                except TimeoutException:
                    log(f"Force-navigate also failed. URL: {driver.current_url}")
        else:
            log("Did not reach Cloudia Services login page.")
            driver.save_screenshot("screenshot_login_unexpected.png")

        # Step 3: Check if we're logged in
        driver.save_screenshot("screenshot_after_login.png")
        log(f"Final URL: {driver.current_url}")

        page_text = driver.find_element(By.TAG_NAME, "body").text[:500]
        with open("page_text_after_login.txt", "w", encoding="utf-8") as f:
            f.write(driver.find_element(By.TAG_NAME, "body").text)

        if any(kw in page_text for kw in ["Log out", "Kirjaudu ulos", "My tenders", "Omat tarjoukset"]):
            log("Login successful!")
            return True
        elif any(kw in page_text.lower() for kw in ["error", "virhe", "wrong", "check the username"]):
            log("Login failed — check credentials.")
            return False
        else:
            # Could be logged in but on a different page
            log("Login state unclear — check screenshot_after_login.png")
            return "tarjouspalvelu.fi" in driver.current_url

    except Exception as e:
        log(f"Login error: {e}")
        driver.save_screenshot("screenshot_login_error.png")
        return False


# Notice type filter values for the search page
# These map to the ilmoitustyypit-multiselect dropdown options
NOTICE_TYPES_OPEN = [
    "57",   # Competition (eForms)
    "56",   # Planning (eForms)
    "61",   # Dynamic purchasing system (eForms)
    "1",    # National procurement notification
    "26",   # Request for information
    "35",   # National Dynamic Procurement notification
]

NOTICE_TYPES_RESULTS = [
    "58",   # Results (eForms)
    "59",   # Direct award preannouncement (eForms)
    "42",   # Contract award notice (EU)
    "45",   # Social services contract award notice (EU)
]


def apply_search_filters(driver, mode: str):
    """Apply notice type filters on the global search page before searching.

    mode='tenders' — only open/biddable tenders (for daily notifications)
    mode='analytics' — only results/awards (for price/competitor analysis)
    mode='all' — no filtering
    """
    if mode == "all":
        log("No search filters applied — scraping all tender types.")
        return

    notice_types = NOTICE_TYPES_OPEN if mode == "tenders" else NOTICE_TYPES_RESULTS
    type_label = "open tenders" if mode == "tenders" else "award results"

    log(f"Applying notice type filter: {type_label}...")
    try:
        # Enable the notice type filter checkbox
        driver.execute_script("""
            var cb = document.getElementById('ilmoituksen-tyyppi-cb');
            if (cb && !cb.checked) {
                cb.checked = true;
                cb.dispatchEvent(new Event('change'));
            }
        """)
        time.sleep(1)

        # Select the notice types using Select2 multiselect
        types_js = ",".join(f'"{t}"' for t in notice_types)
        driver.execute_script(f"""
            var select = $('#ilmoitustyypit-multiselect');
            select.val([{types_js}]).trigger('change');
        """)
        time.sleep(1)
        log(f"Selected {len(notice_types)} notice types for {type_label}.")
    except Exception as e:
        log(f"Warning: could not apply notice type filter: {e}")


def navigate_to_publications(driver, org_id: str, mode: str = "tenders") -> bool:
    """Navigate to the tender listings page and apply filters.

    mode='tenders' — open tenders only (Competition, Planning, DPS)
    mode='analytics' — results/awards only (for price/competitor analysis)
    mode='all' — everything
    """
    current_url = driver.current_url

    if "Default/Index" in current_url:
        # On global search after login
        log("On global search page (all Finnish tenders).")

        # Apply notice type filters
        apply_search_filters(driver, mode)

        # Pause for demo after filters are visible (skipped in headless)
        if os.getenv("DEMO_PAUSE", "0") == "1" and os.getenv("HEADLESS", "0") != "1":
            input("\n  ⏸  DEMO PAUSE — Filters applied. Press Enter to search...\n")

        # Set 50 results per page and search
        try:
            driver.execute_script("""
                var select = document.getElementById('ilmoituksiaPerSivu');
                if (select) { select.value = '50'; }
            """)
            driver.execute_script("HaeSivu(1);")
            log("Set 50 per page, searching...")
            time.sleep(8)
        except Exception as e:
            log(f"Could not change page size: {e}")

        total = get_total_tender_count(driver)
        if total:
            log(f"Search returned {total} tenders (filtered by {mode} mode).")

        return True

    # Not on /Default/Index. Decide path by org_id:
    #   "global" (default)     -> force-navigate to /Default/Index anonymously
    #                             (anonymous can browse listings, just no detail tabs)
    #   explicit org id        -> org-specific listing page (dev/testing)
    if org_id == GLOBAL_ORG:
        log("Not on global search page — navigating to /Default/Index (anonymous if login failed).")
        try:
            driver.get("https://tarjouspalvelu.fi/Default/Index")
            time.sleep(5)
            if not wait_for_cloudflare(driver):
                return False
            apply_search_filters(driver, mode)
            try:
                driver.execute_script("var s=document.getElementById('ilmoituksiaPerSivu'); if(s){s.value='50';}")
                driver.execute_script("HaeSivu(1);")
                time.sleep(8)
            except Exception as e:
                log(f"Could not configure search: {e}")
            total = get_total_tender_count(driver)
            if total:
                log(f"Search returned {total} tenders across all of Finland.")
            return True
        except Exception as e:
            log(f"Failed to navigate to /Default/Index: {e}")
            return False

    log(f"Not logged in — using org-specific page (org_id={org_id}, no search filters).")
    try:
        pub_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-test-key='julkaisutNavLink']"))
        )
        pub_link.click()
        time.sleep(5)
    except Exception:
        driver.get(f"https://tarjouspalvelu.fi/UX/TP/TarjouspyyntoListaus?p={org_id}")
        time.sleep(5)
        if not wait_for_cloudflare(driver):
            return False
    log(f"Current URL: {driver.current_url}")
    return True


def get_total_tender_count(driver) -> int:
    """Get total tender count from pagination info (e.g. 'Showing 1 - 50 / 5215')."""
    try:
        text = driver.find_element(By.CSS_SELECTOR, ".pagination-wrapper").text
        import re
        match = re.search(r'/\s*(\d+)', text)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return 0


def extract_page_notices(driver) -> list[dict]:
    """Extract tenders from the current page using JavaScript."""
    notices = driver.execute_script("""
        const rows = document.querySelectorAll('a.tp-list__row');
        const results = [];

        for (const row of rows) {
            const notice = {};

            // URL and tender ID
            const href = row.getAttribute('href') || '';
            notice.url = href.startsWith('http') ? href : 'https://tarjouspalvelu.fi' + href;
            const tpMatch = href.match(/tpId=(\\d+)/);
            if (tpMatch) notice.tp_id = tpMatch[1];

            // Organisation — strip sr-only spans and label text
            const orgEl = row.querySelector('.tp-list__column--hy');
            if (orgEl) {
                let orgText = orgEl.textContent;
                // Remove sr-only and label text
                orgText = orgText.replace('Open the call for tenders:', '');
                orgText = orgText.replace('Organisation', '');
                notice.organisation = orgText.trim();
            }

            // Name
            const nameEl = row.querySelector('.tp-list__column--name .text-bold');
            if (nameEl) notice.name = nameEl.textContent.trim();

            // Type
            const typeEl = row.querySelector('.tp-list__column--name .font-075-rem');
            if (typeEl) notice.type = typeEl.textContent.trim();

            // Description (full text in span title)
            const descSpan = row.querySelector('span[title]');
            if (descSpan) {
                notice.description = descSpan.getAttribute('title').trim();
                notice.description_short = descSpan.textContent.trim();
            }

            // Date columns — find all columns with label-xl-aria inside the row
            const allCols = row.querySelectorAll('.tp-list__column');
            for (const col of allCols) {
                const label = col.querySelector('.label-xl-aria');
                if (!label) continue;
                const labelText = label.textContent.trim().toLowerCase();
                const spans = col.querySelectorAll('span');
                const dateText = Array.from(spans).map(s => s.textContent.trim()).filter(Boolean).join(' ');

                if (labelText.includes('publication') || labelText.includes('julkaisu')) {
                    notice.published = dateText;
                } else if (labelText.includes('deadline') || labelText.includes('määräaika')) {
                    notice.deadline = dateText;
                }
            }

            if (notice.name) results.push(notice);
        }

        return results;
    """)

    return notices


DETAIL_TABS = [
    ("sidebar2", "Summary", "Tiivistelma"),
    ("sidebar3", "Publication documents", "KokoTarjousPyyntoJaLiitteet"),
    ("sidebar4", "Questions and answers", "KysymyksetJaVastaukset"),
    ("sidebar5", "Other terms and conditions", "SoveltuvuusVaatimukset"),
    ("sidebar6", "Procurement object", "KohteenTiedot"),
    ("sidebar0", "Persons in charge", "VastuuhenkilotJaOikeudet"),
]


def _extract_question_deadline(summary_text: str) -> str | None:
    """Extract the question-submission deadline from a tender's Summary tab.

    The Summary tab renders label/value pairs as consecutive lines, e.g.:
        Kysymysten jätön määräaika
        29.4.2026 16.00 (UTC+03:00)
    We accept both Finnish and English labels so the extractor keeps working
    if the browser UI language flips.
    """
    if not summary_text:
        return None
    lines = [ln.strip() for ln in summary_text.splitlines() if ln.strip()]
    labels = {
        "Kysymysten jätön määräaika",
        "Deadline for submitting questions",
    }
    for i, line in enumerate(lines):
        if line in labels and i + 1 < len(lines):
            return lines[i + 1]
    return None


def _return_to_listings(driver, listings_url: str):
    """Reliably return to the listings page after a detail scrape.

    Cloudia's detail flow uses JS-driven navigation, so driver.back() leaves
    us on intermediate redirect URLs rather than the listings. Direct
    navigation + wait for tp-list__row rows is deterministic.
    """
    try:
        driver.get(listings_url)
        try:
            WebDriverWait(driver, 15).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, "a.tp-list__row")
            )
        except TimeoutException:
            log(f"    Listings did not reload within 15s. URL: {driver.current_url}")
    except Exception as e:
        log(f"    _return_to_listings error: {type(e).__name__}: {e}")


def scrape_detail_page(driver, tender: dict) -> bool:
    """Scrape a single detail page by clicking its row from the current listings page.

    Clicks the tender link (preserving session), collects text from each tab,
    then navigates back. Returns True if successful.
    """
    tp_id = tender.get("tp_id", "")
    if not tp_id:
        return False

    # NOTE: Opening a tender while logged in creates a draft response/offer
    # in Cloudia by design. This is intentional supplier-tracking behavior
    # confirmed by Riku Turkia (2026-04-21). We accept the drafts and plan
    # separate hygiene later (manual cleanup during debug; programmatic
    # UI-click "Poista tarjous" after bid/no-bid decision in production).
    try:
        # Remember the listings URL so we can reliably return after the detail
        # scrape. driver.back() is flaky with Cloudia's JS-driven navigation
        # (history stack doesn't match visual navigation).
        listings_url = driver.current_url
        log(f"  → scrape_detail_page(tp_id={tp_id}) starting. URL: {listings_url}")

        # Step 1: Find and click the tender row
        rows = driver.find_elements(By.CSS_SELECTOR, "a.tp-list__row")
        clicked = False
        for row in rows:
            href = row.get_attribute("href") or ""
            if f"tpId={tp_id}" in href:
                ActionChains(driver).move_to_element(row).click().perform()
                clicked = True
                break

        if not clicked:
            log(f"  Row for tp_id={tp_id} not found on current page.")
            return False

        # Step 2: Wait for navigation away from the listings
        listings_url = driver.current_url
        try:
            WebDriverWait(driver, 20).until(
                lambda d: "Default/Index" not in d.current_url or "tpId=" in d.current_url
            )
        except TimeoutException:
            pass
        time.sleep(2)
        log(f"  After row click, URL: {driver.current_url}")

        # Step 3: If we landed on the response/offer list intermediate page,
        # click into the existing draft to reach EditoiTarjousta. The page
        # shows a single draft row (the one just created) plus a "Tee uusi
        # tarjous/vastaus" button we must NOT click (that creates ANOTHER draft).
        page_text = ""
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text
        except Exception:
            pass

        on_response_list = (
            "EditoiTarjousta" not in driver.current_url
            and ("Tee uusi tarjous" in page_text or "Tee uusi vastaus" in page_text
                 or "Create new tender" in page_text or "Create new response" in page_text)
        )

        if on_response_list:
            log("  Landed on response-list page. Opening auto-created draft...")
            # Save HTML once per session for diagnosis if we get stuck
            if not os.path.exists("page_html_response_list.html"):
                try:
                    with open("page_html_response_list.html", "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    log("  Saved page source: page_html_response_list.html")
                except Exception:
                    pass

            # Step 1: Open the dropdown menu ("Avaa tarjouksen valikko" toggle)
            toggled = driver.execute_script("""
                const els = Array.from(document.querySelectorAll('a, button, [role=button], [onclick]'));
                const toggle = els.find(el => {
                    const t = (el.textContent || '').trim().toLowerCase();
                    return t.includes('avaa tarjouksen valikko') || t.includes('open the tender menu');
                });
                if (toggle) { toggle.click(); return toggle.textContent.trim(); }
                return null;
            """)
            log(f"  Menu toggle clicked: {toggled!r}")
            time.sleep(1)

            # Step 2: Click the "Avaa" (Open) item inside the now-open dropdown.
            # Explicitly exclude "Tee uusi" (creates new), "Poista" (delete),
            # "Takaisin" (back), "Avaa PDF" (downloads PDF, stays on same URL).
            opened = driver.execute_script("""
                const els = Array.from(document.querySelectorAll('a, button, li, [role=menuitem], [onclick]'));
                const safe = els.filter(el => {
                    // only visible elements
                    const rect = el.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) return false;
                    const t = (el.textContent || '').trim().toLowerCase();
                    if (!t) return false;
                    if (t.includes('tee uusi') || t.includes('create new')) return false;
                    if (t.includes('poista') || t.includes('remove') || t.includes('delete')) return false;
                    if (t.includes('takaisin') || t.includes('back')) return false;
                    if (t.includes('pdf')) return false;           // Avaa PDF — not what we want
                    if (t.includes('valikko') || t.includes('tender menu')) return false;  // the toggle itself
                    return t === 'avaa' || t === 'open' || t === 'avaa tarjous' || t === 'open tender';
                });
                if (safe.length > 0) {
                    safe[0].click();
                    return safe[0].textContent.trim();
                }
                return null;
            """)
            log(f"  Menu item clicked: {opened!r}")

            try:
                WebDriverWait(driver, 20).until(
                    lambda d: "EditoiTarjousta" in d.current_url
                )
            except TimeoutException:
                pass
            time.sleep(2)
            log(f"  After draft-open, URL: {driver.current_url}")

        # Step 4: Check if we now have full access
        is_edit = "EditoiTarjousta" in driver.current_url
        tender["detail_full_access"] = is_edit
        log(f"  detail_full_access = {is_edit}")

        if not is_edit:
            # Couldn't reach the full view. Capture whatever is visible.
            try:
                tender["detail_text"] = driver.find_element(By.TAG_NAME, "body").text
            except Exception:
                tender["detail_text"] = ""
            tender["detail_tabs"] = {}
            log(f"  Captured public/response-list body: {len(tender['detail_text'])} chars")
            _return_to_listings(driver, listings_url)
            return True

        # Full access — click through each tab and collect content
        tab_texts = {}
        captured_zip_href = None  # grabbed opportunistically when Publication docs tab is active

        for sidebar_id, tab_name, vaihe_name in DETAIL_TABS:
            try:
                tab_btn = driver.find_elements(By.ID, sidebar_id)
                if not tab_btn:
                    continue

                # Check if tab is disabled
                classes = tab_btn[0].get_attribute("class") or ""
                if "disabled" in classes:
                    continue

                ActionChains(driver).move_to_element(tab_btn[0]).click().perform()
                time.sleep(2)

                # Get the content area text
                content_divs = driver.find_elements(By.CSS_SELECTOR, "div.content")
                if content_divs:
                    tab_texts[tab_name] = content_divs[0].text
                else:
                    tab_texts[tab_name] = driver.find_element(By.TAG_NAME, "body").text

                # While we're on the Publication documents tab, snapshot the ZIP
                # link's href before switching tabs unloads it from the DOM.
                if tab_name == "Publication documents" and captured_zip_href is None:
                    try:
                        zip_el = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/Zip/"]')
                        if zip_el:
                            captured_zip_href = zip_el[0].get_attribute("href")
                            log(f"    Captured ZIP href during tab scrape: {captured_zip_href}")
                    except Exception:
                        pass

            except Exception as e:
                log(f"    Tab '{tab_name}' error: {e}")

        tender["detail_tabs"] = tab_texts

        # Combine all tab text into a single detail_text for AI consumption
        combined = []
        for tab_name, text in tab_texts.items():
            combined.append(f"=== {tab_name} ===\n{text}")
        tender["detail_text"] = "\n\n".join(combined)

        # Extract the question deadline from the Summary tab as a structured field.
        q_deadline = _extract_question_deadline(tab_texts.get("Summary", ""))
        if q_deadline:
            tender["question_deadline"] = q_deadline
            log(f"  Question deadline: {q_deadline}")

        # Optional: AI extraction of scoring + contract + reservations fields.
        # Opt-in via env flag so we don't spend OpenAI credits on metadata
        # extraction during baseline runs. Single OpenAI call covers all
        # three stakeholder-requested checks (see extract.py).
        if os.getenv("ENABLE_METADATA_EXTRACTION", "0") == "1":
            try:
                from .extract import apply_metadata
                apply_metadata(tender)
                log(f"  Scoring: quality={tender.get('quality_weight')} "
                    f"price={tender.get('price_weight')} "
                    f"basis={tender.get('scoring_basis')}")
                log(f"  Contract included: {tender.get('contract_included')}  "
                    f"Reservations allowed: {tender.get('reservations_allowed')}")
            except Exception as e:
                log(f"  Metadata extraction error: {type(e).__name__}: {e}")

        # Download all attachments as ZIP if enabled
        if os.getenv("ENABLE_DOWNLOAD_ATTACHMENTS", "0") == "1":
            try:
                zip_href = captured_zip_href

                # Fallback: if we didn't grab the href during tab scrape, try again now
                if not zip_href:
                    pub_tab = driver.find_elements(By.ID, "sidebar3")
                    if pub_tab:
                        ActionChains(driver).move_to_element(pub_tab[0]).click().perform()
                        try:
                            el = WebDriverWait(driver, 15).until(
                                lambda d: d.find_element(By.CSS_SELECTOR, 'a[href*="/Zip/"]')
                            )
                            zip_href = el.get_attribute("href")
                        except TimeoutException:
                            pass

                if not zip_href:
                    log("    No ZIP link found in Publication Documents tab.")
                else:
                    log(f"    ZIP href: {zip_href}")
                    # Download via `requests` using Selenium's session cookies.
                    # Headless Chrome's download handler is unreliable; a direct
                    # HTTP GET with the session cookie is simpler and deterministic.
                    import re as _re
                    import requests
                    cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
                    user_agent = driver.execute_script("return navigator.userAgent") or ""
                    headers = {"User-Agent": user_agent, "Referer": driver.current_url}
                    try:
                        r = requests.get(
                            zip_href, cookies=cookies, headers=headers,
                            stream=True, timeout=120, verify=False,
                        )
                        if r.status_code != 200:
                            log(f"    ZIP GET failed: HTTP {r.status_code}")
                        else:
                            cd = r.headers.get("Content-Disposition", "")
                            m = _re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
                            filename = m.group(1) if m else f"{tp_id}_attachments.zip"
                            filepath = os.path.join(DOWNLOADS_DIR, filename)
                            bytes_written = 0
                            with open(filepath, "wb") as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                                        bytes_written += len(chunk)
                            tender["attachments_zip"] = filepath
                            size_kb = bytes_written // 1024
                            log(f"    Attachments downloaded: {filename} ({size_kb} KB)")

                            # Optional: upload to SharePoint staging workspace.
                            # Off by default; flip ENABLE_SHAREPOINT_UPLOAD=1
                            # once GRAPH_* + SHAREPOINT_* env vars are set.
                            if os.getenv("ENABLE_SHAREPOINT_UPLOAD", "0") == "1":
                                try:
                                    from .sharepoint import upload_tender_zip
                                    share_url = upload_tender_zip(filepath, tender)
                                    if share_url:
                                        tender["sharepoint_url"] = share_url
                                except Exception as e:
                                    log(f"    SharePoint upload error: {type(e).__name__}: {e}")
                    except Exception as e:
                        log(f"    ZIP download via requests failed: {type(e).__name__}: {e}")
            except Exception as e:
                log(f"    Attachment download error: {type(e).__name__}: {e}")

        # Pause for demo if requested (skipped in headless)
        if os.getenv("DEMO_PAUSE", "0") == "1" and os.getenv("HEADLESS", "0") != "1":
            tabs_found = list(tab_texts.keys())
            log(f"  Detail page scraped: {tender.get('name', '')[:60]}")
            log(f"  Tabs collected: {', '.join(tabs_found)}")
            if tender.get("attachments_zip"):
                log(f"  Attachments: {os.path.basename(tender['attachments_zip'])}")
            input("\n  ⏸  DEMO PAUSE — Review the detail page. Press Enter to go back...\n")

        _return_to_listings(driver, listings_url)
        return True

    except Exception as e:
        log(f"  Detail error on tpId={tp_id}: {e}")
        try:
            _return_to_listings(driver, listings_url)
        except Exception:
            pass
        return False


def scrape_page_details(driver, page_notices: list[dict], max_details: int = 0) -> int:
    """Scrape detail pages for tenders on the CURRENT listings page.

    Must be called before navigating to the next page.
    Returns count of successfully enriched tenders.
    """
    to_scrape = page_notices if max_details == 0 else page_notices[:max_details]
    enriched = 0

    for tender in to_scrape:
        if scrape_detail_page(driver, tender):
            enriched += 1
            if enriched % 5 == 0:
                log(f"    ...{enriched} detail pages scraped on this page")

    return enriched


def extract_notices(driver, org_slug: str, max_pages: int = 5,
                    scrape_details: bool = False, max_details_per_page: int = 0,
                    max_details_total: int = 0) -> list[dict]:
    """Extract tenders with pagination support. Optionally scrapes detail pages per-page.

    scrape_details: if True, click into each tender's detail page on the current
                    listings page before moving to the next page
    max_details_per_page: max tenders to detail-scrape per page (0 = all on that page)
    max_details_total: max detail pages across all pages (0 = unlimited)
    """

    total = get_total_tender_count(driver)
    if total:
        log(f"Total tenders available: {total}")

    all_notices = []
    total_details = 0

    for page_num in range(1, max_pages + 1):
        log(f"Scraping page {page_num}...")
        page_notices = extract_page_notices(driver)
        log(f"  Page {page_num}: {len(page_notices)} tenders extracted")

        if not page_notices:
            log("  No tenders found on this page — stopping pagination.")
            break

        # Add source org
        for n in page_notices:
            n["source_org"] = org_slug

        # Detail scrape BEFORE leaving this page
        if scrape_details and (max_details_total == 0 or total_details < max_details_total):
            remaining = max_details_total - total_details if max_details_total > 0 else max_details_per_page
            page_limit = min(max_details_per_page, remaining) if max_details_per_page > 0 else remaining
            log(f"  Scraping detail pages on page {page_num}...")
            enriched = scrape_page_details(driver, page_notices, page_limit if page_limit > 0 else 0)
            total_details += enriched
            full = sum(1 for t in page_notices if t.get("detail_full_access"))
            log(f"  Page {page_num} details: {enriched} enriched, {full} with full access")

        all_notices.extend(page_notices)

        # Navigate to next page if there are more
        if page_num < max_pages:
            try:
                has_next = driver.execute_script(f"""
                    try {{ HaeSivu({page_num + 1}); return true; }}
                    catch(e) {{ return false; }}
                """)
                if has_next:
                    time.sleep(5)
                else:
                    break
            except Exception:
                log("  No more pages.")
                break

    log(f"Extraction complete — {len(all_notices)} tenders across {page_num} page(s).")
    with_deadline = sum(1 for n in all_notices if n.get("deadline"))
    with_published = sum(1 for n in all_notices if n.get("published"))
    log(f"  Deadlines found: {with_deadline}/{len(all_notices)}")
    log(f"  Publication dates found: {with_published}/{len(all_notices)}")
    if scrape_details:
        log(f"  Detail pages scraped: {total_details}/{len(all_notices)}")

    # Zero-results health check. A run that completes successfully but yields
    # zero tenders almost always means a silent login failure, a Cloudflare
    # soft block, or a selector drift — never a genuine "nothing was published
    # today" outcome given that 100+ notices get filed every weekday.
    # Surface this loudly so the reviewer noticing an empty inbox knows why.
    if len(all_notices) == 0:
        log("⚠️  ZERO TENDERS EXTRACTED — likely silent login failure, Cloudflare "
            "block, or UI selector drift. Investigate before trusting the run.")
        try:
            from .notify import send_email
            alert_to = os.getenv("REVIEWER_EMAIL") or os.getenv("SMTP_USER")
            if alert_to:
                send_email(
                    alert_to,
                    "[ALERT] CGI Tender Agent run produced 0 tenders",
                    "<html><body><h2>Nightly run produced zero tenders</h2>"
                    "<p>The scraper completed without error but extracted no tenders. "
                    "This is almost always a silent failure — login, Cloudflare, "
                    "or a UI change. Check scraper.log.</p></body></html>",
                )
        except Exception as e:
            log(f"  (Could not send zero-results alert: {type(e).__name__}: {e})")

    return all_notices


def scrape_notices(org_slug: str = GLOBAL_ORG, mode: str = "tenders") -> list[dict]:
    """Full scraping flow for tarjouspalvelu.fi.

    org_slug='global' (default) — scrape ALL of Finland via /Default/Index
    org_slug='helsinki' / 'espoo' / ... — scrape one organisation only
                                          (intended for dev / testing)

    mode='tenders' — open tenders only (for daily notifications)
    mode='analytics' — results/awards only (for price/competitor analysis)
    mode='all' — everything
    """
    if not org_slug or org_slug == GLOBAL_ORG:
        org_slug = GLOBAL_ORG
        org_id = GLOBAL_ORG
        url = "https://tarjouspalvelu.fi/Default/Index"
    else:
        org_id = ORGANIZATIONS.get(org_slug, org_slug)
        url = f"https://tarjouspalvelu.fi/{org_slug}"

    log_step(1, "LAUNCHING BROWSER")
    log("Starting undetected Chrome (bypasses Cloudflare bot detection)...")
    log(f"Using persistent profile: {PROFILE_DIR}")
    driver = create_driver()
    log("Browser launched successfully.")

    try:
        log_step(2, "NAVIGATING TO TARJOUSPALVELU.FI")
        log(f"Target URL: {url}")
        driver.get(url)
        log(f"Page title: {driver.title}")

        if not wait_for_cloudflare(driver):
            driver.save_screenshot(f"screenshot_{org_slug}_blocked.png")
            log("Saving screenshot of blocked page.")
            return []

        log_step(3, "HANDLING COOKIE CONSENT")
        dismiss_cookie_popup(driver)

        log_step(4, "AUTHENTICATING")
        max_login_attempts = 3
        logged_in = False
        for attempt in range(1, max_login_attempts + 1):
            log(f"Login attempt {attempt}/{max_login_attempts}...")
            logged_in = login(driver)
            if logged_in:
                log("Authenticated — full tender data will be available.")
                break
            else:
                log(f"Login attempt {attempt} failed.")
                driver.save_screenshot(f"screenshot_login_failed_attempt{attempt}.png")
                if attempt < max_login_attempts:
                    log("Retrying login...")
                    # Navigate back to start fresh
                    driver.get("https://tarjouspalvelu.fi/Default/Index")
                    time.sleep(5)
        if not logged_in:
            log("ALL LOGIN ATTEMPTS FAILED — continuing with public data only.")
            driver.save_screenshot("screenshot_login_failed.png")

        # Switch UI to Finnish (logged-in only)
        if logged_in:
            try:
                # Open the language dropdown first, then click Finnish
                toggle = driver.find_elements(By.CSS_SELECTOR, "[data-test-key='languageDropdown']")
                if toggle:
                    toggle[0].click()
                    time.sleep(1)
                fi_btn = driver.find_elements(By.CSS_SELECTOR, "[data-test-key='languageDropdown.finnish']")
                if fi_btn:
                    fi_btn[0].click()
                    time.sleep(3)
                    log("UI language switched to Finnish.")
            except Exception as e:
                log(f"Language switch skipped: {e}")

        log_step(5, f"NAVIGATING TO TENDER LISTINGS (mode={mode})")
        if not navigate_to_publications(driver, org_id, mode):
            return []

        # Check for another Cloudflare challenge after navigation
        if "Tarkistetaan suojausta" in driver.page_source:
            log("Cloudflare challenge appeared after navigation...")
            if not wait_for_cloudflare(driver):
                return []

        # Wait for listings to render
        log("Waiting for listings to fully render...")
        time.sleep(3)

        # Dismiss cookie popup again if it reappeared
        dismiss_cookie_popup(driver)
        time.sleep(1)

        log_step(6, "EXTRACTING OPEN TENDERS")
        log(f"Page URL: {driver.current_url}")
        driver.save_screenshot(f"screenshot_{org_slug}_listings.png")
        log(f"Screenshot saved: screenshot_{org_slug}_listings.png")

        # Detail scraping is now integrated into extraction (per-page)
        enable_detail = os.getenv("ENABLE_DETAIL_SCRAPE", "0") == "1"
        max_details_total = int(os.getenv("DETAIL_SCRAPE_COUNT", "0"))

        if enable_detail:
            log(f"Detail page scraping: ENABLED (max {max_details_total if max_details_total > 0 else 'all'} total, with tab clicking)")
        else:
            log("Detail page scraping: DISABLED (set ENABLE_DETAIL_SCRAPE=1)")

        notices = extract_notices(
            driver, org_slug,
            scrape_details=enable_detail,
            max_details_total=max_details_total,
        )

        log_step(7, "SAVING RESULTS")
        return notices

    finally:
        log("Closing browser...")
        driver.quit()
        log("Browser closed.")


def main():
    from .storage import store_tenders, get_stats, classify_tender, mark_notified
    from .routing import route_all_tenders, CONFIG_PATH
    from .summarize import summarize_tenders
    from .analyze import analyze_results, print_competitor_report, print_price_report

    clear_log()

    # Parse mode from args: --mode=tenders (default), --mode=analytics, --mode=all, --mode=offline
    mode = "tenders"
    for arg in sys.argv:
        if arg.startswith("--mode="):
            mode = arg.split("=")[1]

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║   TARJOUSPALVELU.FI — PUBLIC TENDER SCRAPER            ║")
    print("║   Tender Intelligence Demo for CGI                     ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Offline mode: replay from saved demo_results.json (no browser needed)
    if mode == "offline":
        results_file = str(DEMO_RESULTS)
        if not os.path.exists(results_file):
            print(f"\n  ERROR: No saved results at {results_file}")
            print(f"  Run a live scrape first (--mode=tenders) to generate demo_results.json")
            return
        print(f"  Mode: OFFLINE DEMO (replaying from saved results)")
        print(f"  Source: demo_results.json")
        print()
        with open(results_file, "r", encoding="utf-8") as f:
            notices = json.load(f)
        elapsed = 0.0
        log(f"Loaded {len(notices)} tenders from demo_results.json")
        # Clear any stale AI summaries so they get regenerated fresh
        for n in notices:
            n.pop("ai_summary", None)
            n.pop("_routing", None)

    elif mode == "combined":
        # Combined mode: Hilma API + tarjouspalvelu.fi scraping + merge
        from .hilma import search_cgi_relevant
        from .merge import merge_sources

        hilma_days = int(os.getenv("HILMA_DAYS", "7"))
        print(f"  Mode: COMBINED (Hilma API + tarjouspalvelu.fi)")
        print(f"  Hilma: last {hilma_days} days")
        print()

        start_time = time.time()

        # Phase 1: Hilma API (fast, structured)
        log_step(1, "FETCHING FROM HILMA API")
        log("Querying Hilma for CGI-relevant tenders...")
        hilma_tenders = search_cgi_relevant(days=hilma_days, top=200)
        log(f"Hilma returned {len(hilma_tenders)} tenders")

        # Phase 2: tarjouspalvelu.fi scraping
        log_step(2, "SCRAPING TARJOUSPALVELU.FI")
        # Default: scrape all Finland via /Default/Index. Pass an org name
        # as an arg (e.g. `python -m app.main --mode=combined helsinki`) to
        # restrict to one organisation — useful for dev/testing only.
        org = GLOBAL_ORG
        for arg in sys.argv[1:]:
            if not arg.startswith("-"):
                org = arg
                break
        tp_tenders = scrape_notices(org, mode="tenders")
        log(f"Tarjouspalvelu returned {len(tp_tenders)} tenders")

        # Phase 3: Merge and deduplicate
        log_step(3, "MERGING SOURCES")
        notices = merge_sources(hilma_tenders, tp_tenders)
        elapsed = time.time() - start_time

        if not notices:
            print(f"\n  No tenders from either source.")
            print(f"  Elapsed: {elapsed:.1f} seconds")
            return

    else:
        # Default: scrape all Finland. Optional positional arg restricts to one org.
        org = GLOBAL_ORG
        for arg in sys.argv[1:]:
            if not arg.startswith("-"):
                org = arg
                break
        is_global = (org == GLOBAL_ORG)
        org_name = "All Finland" if is_global else org.capitalize()
        org_id = GLOBAL_ORG if is_global else ORGANIZATIONS.get(org, org)
        target_url = "https://tarjouspalvelu.fi/Default/Index" if is_global else f"https://tarjouspalvelu.fi/{org}"
        mode_labels = {"tenders": "Open Tenders (daily)", "analytics": "Award Results (analytics)", "all": "All Types"}
        print(f"  Mode: {mode_labels.get(mode, mode)}")
        print(f"  Organization: {org_name} (ID: {org_id})")
        print(f"  Target: {target_url}")
        print()

        start_time = time.time()
        notices = scrape_notices(org, mode=mode)
        elapsed = time.time() - start_time

        if not notices:
            print(f"\n  No tenders extracted — check screenshots for debugging.")
            print(f"  Elapsed: {elapsed:.1f} seconds")
            return

    org_name = "All Finland" if mode in ("offline", "combined") else org_name

    # Classify and store
    log_step(8, "CLASSIFYING & STORING TENDERS")
    for n in notices:
        classify_tender(n)

    result = store_tenders(notices)
    log(f"Database updated:")
    log(f"  New tenders:     {result['new']}")
    log(f"  Updated:         {result['updated']}")
    log(f"  Filtered (closed): {result['filtered_closed']}")
    log(f"  Total scraped:   {result['total']}")

    # Separate by category
    open_competitions = [n for n in notices if n.get("category") == "open_competition" and n.get("status") == "open"]
    dps = [n for n in notices if n.get("category") == "dynamic_purchasing" and n.get("status") == "open"]
    signals = [n for n in notices if n.get("category") == "early_signal"]
    direct = [n for n in notices if n.get("category") == "direct_award"]
    closed = [n for n in notices if n.get("status") == "closed"]

    print()
    print(f"{'='*70}")
    print(f"  RESULTS from {org_name} — completed in {elapsed:.1f}s")
    print(f"{'='*70}")
    print()
    print(f"  Total scraped:          {len(notices)}")
    print(f"  ├─ Open competitions:   {len(open_competitions)}  ← CGI can bid on these")
    print(f"  ├─ Dynamic purchasing:  {len(dps)}  ← ongoing DPS frameworks")
    print(f"  ├─ Early signals:       {len(signals)}  ← upcoming tenders / market dialogues")
    print(f"  ├─ Direct awards:       {len(direct)}  ← not open for bidding")
    print(f"  └─ Closed/results:      {len(closed)}  ← filtered out")

    # Show open competitions (the main target for CGI)
    if open_competitions:
        print()
        print(f"  {'─'*68}")
        print(f"  OPEN COMPETITIONS ({len(open_competitions)} tenders CGI can bid on)")
        print(f"  {'─'*68}")
        for i, n in enumerate(open_competitions[:15], 1):
            name = n.get("name", "N/A")[:65]
            deadline = n.get("deadline", "no deadline")[:22]
            print(f"  {i:>3}. {name}")
            print(f"       Deadline: {deadline}  |  Org: {n.get('organisation', 'N/A')[:30]}")

        if len(open_competitions) > 15:
            print(f"\n  ... and {len(open_competitions) - 15} more open competitions")

    # Show early signals
    if signals:
        print()
        print(f"  {'─'*68}")
        print(f"  EARLY SIGNALS ({len(signals)} upcoming tenders / market dialogues)")
        print(f"  {'─'*68}")
        for i, n in enumerate(signals[:10], 1):
            name = n.get("name", "N/A")[:65]
            print(f"  {i:>3}. {name}")

    # Save full results
    print()
    output_json = os.getenv("OUTPUT_JSON", str(DEMO_RESULTS))
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(notices, f, ensure_ascii=False, indent=2)
    log(f"Full results saved to {output_json}")

    # Database stats
    stats = get_stats()
    print()
    log("Database summary:")
    log(f"  Total tenders tracked: {stats['total']}")
    log(f"  Open:                  {stats['open']}")
    log(f"  Closed:                {stats['closed']}")
    log(f"  Awaiting notification: {stats['unnotified']}")
    if stats.get("by_category"):
        log("  By category:")
        for cat, count in stats["by_category"].items():
            log(f"    {cat}: {count}")

    # Step 10: AI Summarization
    open_tenders = [n for n in notices if n.get("status") == "open"]
    if open_tenders:
        if os.getenv("ENABLE_SUMMARIZATION", "1") != "0":
            log_step(9, "AI SUMMARIZATION")
            sample_size = int(os.getenv("SUMMARIZE_COUNT", "10"))
            sample_size = min(sample_size, len(open_tenders))
            log(f"Summarizing {sample_size} tenders with gpt-4o-mini...")
            summarize_tenders(open_tenders, max_count=sample_size)
            summarized = sum(1 for t in open_tenders if t.get("ai_summary"))
            log(f"Summaries generated: {summarized}/{len(open_tenders)}")
        else:
            log("AI Summarization: DISABLED")

    # Step 11: Three-tier routing
    if open_tenders:
        log_step(10, "THREE-TIER ROUTING")
        routing = route_all_tenders(open_tenders)
        rs = routing["stats"]
        log(f"Routing results:")
        log(f"  Tier 1A (CGI own product):  {rs['tier1a']}  ← CRITICAL")
        log(f"  Tier 1B (partner platform): {rs['tier1b']}  ← HIGH")
        log(f"  Tier 2 (department match):  {rs['tier2']}  ← email digest")
        log(f"  Tier 3 (no match):          {rs['tier3']}  ← dashboard only")
        log(f"  Competitor mentions:         {rs['with_competitors']}")

        # Show Tier 1 alerts
        if routing["tier1_alerts"]:
            print()
            log("TIER 1 ALERTS:")
            for tender, result in routing["tier1_alerts"]:
                products = ", ".join(m["name"] for m in result["product_matches"])
                tier_label = "CGI PRODUCT" if result["tier"] == "1a" else "PARTNER PLATFORM"
                log(f"  [{tier_label}] {tender.get('name', '')[:60]}")
                log(f"    Matched: {products}")
                if result["competitor_matches"]:
                    comps = ", ".join(m["name"] for m in result["competitor_matches"])
                    log(f"    Competitors mentioned: {comps}")

        # Send emails if enabled
        if os.getenv("ENABLE_EMAIL", "0") == "1":
            log_step(11, "SENDING NOTIFICATIONS")
            from .notify import send_notifications
            max_emails = int(os.getenv("MAX_EMAILS", "0"))
            log("Sending Tier 2 department digest emails...")
            if max_emails > 0:
                log(f"Limiting to {max_emails} department emails (largest first)...")
            result = send_notifications(routing["by_department"], max_emails=max_emails)
            log(f"Departments: {result['departments']}")
            log(f"Emails sent: {result['sent']}, previewed: {result['previewed']}, failed: {result['failed']}")

            # Only mark as notified the tenders whose digest actually got
            # delivered (or previewed to disk when SMTP is off). Tenders whose
            # email failed stay `notified=0` and get another chance next run.
            delivered = result.get("delivered_tp_ids") or set()
            # In preview mode (no SMTP configured), emails are written to disk
            # instead of sent; still safe to mark those delivered so we don't
            # re-preview the same batch forever.
            if result["sent"] == 0 and result["previewed"] > 0:
                delivered = {n["tp_id"] for n in open_tenders if n.get("tp_id")}
            if delivered:
                mark_notified(list(delivered))
                log(f"Marked {len(delivered)} tenders as notified "
                    f"(of {len(open_tenders)} open).")
            else:
                log("No tenders marked notified — no email was delivered.")
        else:
            log("Email sending: DISABLED (set ENABLE_EMAIL=1 to enable)")

    # Step 12: Analyze award results (extract prices, winners, competitors)
    closed_results = [n for n in notices if n.get("category") == "result"]
    if closed_results and os.getenv("ENABLE_ANALYSIS", "1") != "0":
        log_step(12, "AWARD RESULTS ANALYSIS")
        log(f"{len(closed_results)} results tenders found — analyzing for price and competitor intelligence...")
        max_analysis = int(os.getenv("ANALYSIS_COUNT", "20"))
        analysis_stats = analyze_results(max_count=max_analysis)

        if analysis_stats.get("analyzed", 0) > 0:
            log_step(13, "INTELLIGENCE REPORTS")
            print_competitor_report()
            print_price_report()


if __name__ == "__main__":
    main()

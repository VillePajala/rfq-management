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

# Load credentials from .env (never hardcoded, never sent to cloud)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_profile")

# Known organization IDs on tarjouspalvelu.fi
ORGANIZATIONS = {
    "helsinki": "13",
    "espoo": "8",
    "vantaa": "30",
    "tampere": "25",
    "oulu": "19",
    "turku": "28",
}


from logger import log_to_file, clear_log


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
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=fi-FI")
    return uc.Chrome(options=options, user_data_dir=PROFILE_DIR)


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
        time.sleep(10)

        # Step 2: Should now be on Cloudia Services login page
        log(f"Step 2: Redirected to: {driver.current_url}")
        driver.save_screenshot("screenshot_cloudia_login.png")
        page_source = driver.page_source

        if "Cloudia" in page_source and ("Login to" in page_source or "Salasana" in page_source):
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



            log("Waiting for redirect back to tarjouspalvelu.fi...")
            time.sleep(10)
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

    # Not logged in — use org-specific page (no pre-filtering available)
    log("Not logged in — using org-specific page (no search filters).")
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
            const tpMatch = href.match(/tpId=(\d+)/);
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


def extract_notices(driver, org_slug: str, max_pages: int = 5) -> list[dict]:
    """Extract tenders with pagination support. Scrapes up to max_pages pages."""

    total = get_total_tender_count(driver)
    if total:
        log(f"Total tenders available: {total}")

    all_notices = []

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

    return all_notices


def scrape_notices(org_slug: str, mode: str = "tenders") -> list[dict]:
    """Full scraping flow for tarjouspalvelu.fi.

    mode='tenders' — open tenders only (for daily notifications)
    mode='analytics' — results/awards only (for price/competitor analysis)
    mode='all' — everything
    """

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

        notices = extract_notices(driver, org_slug)

        # Enrich with detail page data (off by default for fast dev iterations)
        # Must be done BEFORE pagination moves to next page — click from current page
        enable_detail = os.getenv("ENABLE_DETAIL_SCRAPE", "0") == "1"
        max_details = int(os.getenv("DETAIL_SCRAPE_COUNT", "0"))
        if enable_detail and notices:
            log_step(7, "SCRAPING DETAIL PAGES")
            to_scrape = notices if max_details == 0 else notices[:max_details]
            log(f"Scraping detail pages for {len(to_scrape)} tenders...")
            log("Method: click link → scrape → back (preserves login session)")

            # We need to be on the listings page. Go to page 1.
            try:
                driver.execute_script("HaeSivu(1);")
                time.sleep(5)
            except Exception:
                pass

            detail_count = 0
            for i, tender in enumerate(to_scrape):
                tp_id = tender.get("tp_id", "")
                if not tp_id:
                    continue

                try:
                    # Find the row on current page and click it
                    rows = driver.find_elements(By.CSS_SELECTOR, "a.tp-list__row")
                    clicked = False
                    for row in rows:
                        href = row.get_attribute("href") or ""
                        if f"tpId={tp_id}" in href:
                            ActionChains(driver).move_to_element(row).click().perform()
                            clicked = True
                            break

                    if not clicked:
                        # Tender might be on a different page — skip for now
                        continue

                    time.sleep(5)

                    is_edit = "EditoiTarjousta" in driver.current_url
                    body_text = driver.find_element(By.TAG_NAME, "body").text
                    tender["detail_text"] = body_text
                    tender["detail_full_access"] = is_edit

                    detail_data = driver.execute_script("""
                        const data = {};
                        const tabs = [];
                        document.querySelectorAll('a, button, li').forEach(el => {
                            const text = el.textContent.trim();
                            if (['PUBLICATION DOCUMENTS', 'QUESTIONS AND ANSWERS',
                                 'GENERAL CRITERIA', 'TENDER ATTACHMENTS',
                                 'PROCUREMENT OBJECT', 'PERSONS IN CHARGE'].includes(text)) {
                                tabs.push(text);
                            }
                        });
                        data.available_tabs = [...new Set(tabs)];
                        return data;
                    """)
                    tender["detail_data"] = detail_data
                    detail_count += 1

                    if detail_count % 5 == 0:
                        log(f"  ...{detail_count} detail pages scraped (full_access={is_edit})")

                    driver.back()
                    time.sleep(3)

                except Exception as e:
                    log(f"  Error on tpId={tp_id}: {e}")
                    try:
                        driver.back()
                        time.sleep(3)
                    except Exception:
                        pass

            full_access = sum(1 for t in to_scrape if t.get("detail_full_access"))
            log(f"Detail scraping complete. {detail_count} enriched, {full_access} with full access.")
        else:
            if notices:
                log("Detail page scraping: DISABLED (set ENABLE_DETAIL_SCRAPE=1)")

        log_step(8, "SAVING RESULTS")
        return notices

    finally:
        log("Closing browser...")
        driver.quit()
        log("Browser closed.")


def main():
    from storage import store_tenders, get_stats, classify_tender, mark_notified
    from routing import route_all_tenders, CONFIG_PATH
    from summarize import summarize_tenders
    from analyze import analyze_results, print_competitor_report, print_price_report

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
        results_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_results.json")
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
    else:
        org = "helsinki"
        for arg in sys.argv[1:]:
            if not arg.startswith("-"):
                org = arg
                break
        org_name = org.capitalize()
        org_id = ORGANIZATIONS.get(org, org)
        mode_labels = {"tenders": "Open Tenders (daily)", "analytics": "Award Results (analytics)", "all": "All Types"}
        print(f"  Mode: {mode_labels.get(mode, mode)}")
        print(f"  Organization: {org_name} (ID: {org_id})")
        print(f"  Target: https://tarjouspalvelu.fi/{org}")
        print()

        start_time = time.time()
        notices = scrape_notices(org, mode=mode)
        elapsed = time.time() - start_time

        if not notices:
            print(f"\n  No tenders extracted — check screenshots for debugging.")
            print(f"  Elapsed: {elapsed:.1f} seconds")
            return

    org_name = "All Finland" if mode == "offline" else org_name

    # Classify and store
    log_step(9, "CLASSIFYING & STORING TENDERS")
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
    with open("demo_results.json", "w", encoding="utf-8") as f:
        json.dump(notices, f, ensure_ascii=False, indent=2)
    log(f"Full results saved to demo_results.json")

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
            log_step(10, "AI SUMMARIZATION")
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
        log_step(11, "THREE-TIER ROUTING")
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
            log_step(12, "SENDING NOTIFICATIONS")
            from notify import send_notifications
            log("Sending Tier 2 department digest emails...")
            result = send_notifications(routing["by_department"])
            log(f"Departments: {result['departments']}")
            log(f"Emails sent: {result['sent']}, previewed: {result['previewed']}, failed: {result['failed']}")

            # Mark as notified
            notified_ids = [n["tp_id"] for n in open_tenders if n.get("tp_id")]
            mark_notified(notified_ids)
            log(f"Marked {len(notified_ids)} tenders as notified.")
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

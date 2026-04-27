"""
Test whether tender details are accessible WITHOUT logging in.

Key context (from Riku Turkia, 2026-04-21):
  "Drafts are created every time a logged-in user opens a tender request.
   It's used to track which suppliers have reviewed the tender."

So: if we view the tender page in a FRESH browser with no session cookies,
no draft should be created. The only question is how much of the tender
detail is actually visible to an anonymous visitor.

This test:
  1. Launches headless Chrome with a throwaway profile dir (no prior cookies)
  2. Goes to the global search page
  3. Picks the first open-competition tender
  4. Clicks into it and reports what's visible:
        - Does the tender's name/description appear?
        - Do publication documents appear?
        - Can we reach the ZIP download endpoint?
  5. Does NOT log in. Does NOT submit credentials. Fully anonymous.
"""
import os
import shutil
import sys
import tempfile
import time

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

LISTING_URL = "https://tarjouspalvelu.fi/Default/Index"


def make_anon_driver():
    """Fresh Chrome, no persisted profile — guaranteed anonymous."""
    tmp_profile = tempfile.mkdtemp(prefix="anon_chrome_")
    opts = uc.ChromeOptions()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=fi-FI")
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    driver = uc.Chrome(options=opts, user_data_dir=tmp_profile)
    return driver, tmp_profile


def main():
    driver, tmp_profile = make_anon_driver()
    findings = {}
    try:
        # Step 1: confirm we're anonymous (no "Log out" / no email in header)
        print(">>> Step 1: Load listings as anonymous visitor")
        driver.get(LISTING_URL)
        try:
            WebDriverWait(driver, 30).until(
                lambda d: "tp-list__row" in d.page_source or "user" in d.page_source.lower()
            )
        except TimeoutException:
            print("  TIMEOUT waiting for listings to load.")

        page = driver.page_source
        anon_indicators = {
            "has_login_field": 'id="user"' in page,
            "has_logout_text": "Kirjaudu ulos" in page or "Log out" in page,
            "has_ville_email": "ville.pajala" in page,
            "tender_row_count": page.count('class="tp-list__row"'),
        }
        findings["anonymous_landing"] = anon_indicators
        print(f"  Indicators: {anon_indicators}")

        # Step 2: find the first tender row and capture its tpId + href
        print("\n>>> Step 2: Pick first tender from listings")
        rows = driver.find_elements(By.CSS_SELECTOR, "a.tp-list__row")
        if not rows:
            print("  No tender rows found on anonymous listings!")
            findings["detail_test"] = "skipped — no rows"
            return findings
        first_row = rows[0]
        href = first_row.get_attribute("href") or ""
        name_el = first_row.find_elements(By.CSS_SELECTOR, ".tp-list__column--name .text-bold")
        name = name_el[0].text if name_el else "(no name)"
        print(f"  Picked: {name[:70]}")
        print(f"  href:   {href}")
        # Extract tpId for later URL experiments
        import re
        tp_id_match = re.search(r"tpId=(\d+)", href)
        tp_id = tp_id_match.group(1) if tp_id_match else None
        findings["target_tender"] = {"name": name, "href": href, "tp_id": tp_id}

        # Step 3: navigate directly to the tender URL (no click → no onclick draft path)
        print("\n>>> Step 3: Navigate to tender URL directly (no click)")
        driver.get(href)
        try:
            WebDriverWait(driver, 30).until(
                lambda d: d.current_url != LISTING_URL
            )
        except TimeoutException:
            pass
        final_url = driver.current_url
        print(f"  Landed on: {final_url}")

        body = ""
        try:
            body = driver.find_element(By.TAG_NAME, "body").text
        except Exception:
            pass
        detail_indicators = {
            "final_url": final_url,
            "body_length": len(body),
            "says_login_required": any(
                s in body.lower() for s in ["kirjaudu", "log in", "sign in", "login required"]
            ),
            "has_tender_name": (name[:30] in body) if name else False,
            "has_deadline_word": "määräaika" in body.lower() or "deadline" in body.lower(),
            "has_publication_docs": "julkaisun asiakirjat" in body.lower() or "publication document" in body.lower(),
            "has_lataa_or_download": "lataa" in body.lower() or "download" in body.lower(),
            "has_zip_link": "zip" in body.lower() or "TarjousPyynnonLiitteet" in driver.page_source,
            "has_response_list": "tee uusi vastaus" in body.lower() or "tee uusi tarjous" in body.lower(),
            "has_ville_email_leaked": "ville.pajala" in body.lower(),
        }
        findings["detail_page"] = detail_indicators
        print("  Detail page indicators:")
        for k, v in detail_indicators.items():
            print(f"    {k}: {v}")

        # Save body + page source for offline inspection
        with open("/tmp/anon_detail_body.txt", "w", encoding="utf-8") as f:
            f.write(body)
        with open("/tmp/anon_detail_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("  Saved: /tmp/anon_detail_body.txt  +  /tmp/anon_detail_source.html")

        # Step 4: screenshot for visual confirmation
        driver.save_screenshot("/tmp/anon_detail_screenshot.png")
        print("  Screenshot: /tmp/anon_detail_screenshot.png")

        # Step 5: print a short sample of what we got
        print("\n>>> Step 5: First 600 chars of anonymous detail body:")
        print("  " + body[:600].replace("\n", " / "))
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        shutil.rmtree(tmp_profile, ignore_errors=True)

    print("\n>>> SUMMARY")
    import json
    print(json.dumps(findings, indent=2, ensure_ascii=False))
    return findings


if __name__ == "__main__":
    main()

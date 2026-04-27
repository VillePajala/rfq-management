"""
Headless viability test for tarjouspalvelu.fi.

Tries to reach the global search page using undetected-chromedriver with
Chrome's modern `--headless=new` mode. Reports whether Cloudflare Turnstile
auto-resolves (= headless viable) or blocks us (= VM + Xvfb still required).

Verification is stricter than before: we look for real landing-page markers,
not just the absence of challenge strings.
"""
import sys
import time
import undetected_chromedriver as uc

URL = "https://tarjouspalvelu.fi/Default/Index"
TIMEOUT_S = 45

REAL_PAGE_MARKERS = [
    'input#user',        # login email field
    'id="user"',
    'button#continue',
    'id="continue"',
    "tp-list",           # tender listing grid
    "HaeSivu",           # pagination JS fn
    "ilmoitustyypit",    # notice type filter
]

CHALLENGE_MARKERS = [
    "Tarkistetaan suojausta",
    "challenge-platform",
    "cf-challenge",
    "Just a moment",
]


def run(headless: bool) -> dict:
    label = "HEADLESS=new" if headless else "VISIBLE"
    print(f"\n{'='*60}\n{label}\n{'='*60}")

    opts = uc.ChromeOptions()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=fi-FI")
    if headless:
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")

    driver = uc.Chrome(options=opts)
    result = {"mode": label, "passed": False, "reason": "", "title": "",
              "url": "", "page_len": 0, "markers_hit": [], "challenge_hit": [], "elapsed_s": 0.0}
    start = time.time()
    try:
        driver.get(URL)
        for i in range(TIMEOUT_S // 2):
            src = driver.page_source
            challenge_hit = [m for m in CHALLENGE_MARKERS if m in src]
            markers_hit = [m for m in REAL_PAGE_MARKERS if m in src]
            if not challenge_hit and markers_hit:
                result["passed"] = True
                result["reason"] = f"Real page detected (hit {len(markers_hit)} markers)"
                result["markers_hit"] = markers_hit
                break
            if i == 0:
                print(f"  First poll: page_len={len(src)} challenge={challenge_hit} markers={markers_hit}")
            time.sleep(2)
        else:
            result["reason"] = "Timed out — no real-page markers found"

        result["title"] = driver.title
        result["url"] = driver.current_url
        result["page_len"] = len(driver.page_source)
        result["challenge_hit"] = [m for m in CHALLENGE_MARKERS if m in driver.page_source]
        result["elapsed_s"] = round(time.time() - start, 1)

        screenshot_path = f"/tmp/headless_test_{'hl' if headless else 'vis'}.png"
        try:
            driver.save_screenshot(screenshot_path)
            result["screenshot"] = screenshot_path
        except Exception:
            pass
    finally:
        driver.quit()
    return result


if __name__ == "__main__":
    modes = sys.argv[1:] or ["headless"]
    results = []
    for mode in modes:
        try:
            results.append(run(headless=(mode == "headless")))
        except Exception as e:
            results.append({"mode": mode, "passed": False, "reason": f"EXCEPTION: {type(e).__name__}: {e}"})

    print(f"\n{'='*60}\nRESULTS\n{'='*60}")
    for r in results:
        status = "PASS" if r.get("passed") else "FAIL"
        print(f"[{status}] {r.get('mode'):<14}  elapsed={r.get('elapsed_s','?')}s")
        print(f"         url:     {r.get('url','')}")
        print(f"         title:   {r.get('title','')!r}")
        print(f"         page_len: {r.get('page_len', 0)}")
        print(f"         markers: {r.get('markers_hit', [])}")
        print(f"         challenge: {r.get('challenge_hit', [])}")
        print(f"         reason:  {r.get('reason','')}")

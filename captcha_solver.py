import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ================================================================
#  CAPTCHA & CLOUDFLARE DETECTION & STEALTH BYPASS ENGINE
# ================================================================

def detect_captcha(driver):
    """
    Detects presence of Cloudflare Turnstile/Under Attack Mode,
    Google reCAPTCHA v2/v3, and hCaptcha.
    """
    try:
        title = driver.title.lower() if driver.title else ""
        page_source = driver.page_source.lower() if driver.page_source else ""

        # 1. Cloudflare Under Attack Mode / Just a moment...
        if "just a moment..." in title or "checking your browser" in title or "attention required! | cloudflare" in title:
            return {"detected": True, "type": "cloudflare_challenge", "details": "Cloudflare 'Just a moment...' Challenge Screen"}

        # 2. Cloudflare Turnstile Widget
        turnstile_elems = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com'], .cf-turnstile, div[data-sitekey]")
        if turnstile_elems:
            for elem in turnstile_elems:
                if elem.is_displayed():
                    return {"detected": True, "type": "cloudflare_turnstile", "details": "Cloudflare Turnstile Interactive Widget"}

        # 3. Google reCAPTCHA
        recaptcha_elems = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='google.com/recaptcha'], iframe[src*='recaptcha.net'], .g-recaptcha")
        if recaptcha_elems:
            for elem in recaptcha_elems:
                if elem.is_displayed():
                    return {"detected": True, "type": "recaptcha", "details": "Google reCAPTCHA Protected Form"}

        # 4. hCaptcha
        hcaptcha_elems = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='hcaptcha.com'], .h-captcha")
        if hcaptcha_elems:
            for elem in hcaptcha_elems:
                if elem.is_displayed():
                    return {"detected": True, "type": "hcaptcha", "details": "hCaptcha Interactive Widget"}

        # 5. Generic bot verification keywords
        if "verify you are human" in page_source or "confirm you are not a robot" in page_source:
            return {"detected": True, "type": "generic_verification", "details": "Human Verification Security Checkpoint"}

    except Exception:
        pass

    return {"detected": False, "type": None, "details": ""}


def try_solve_turnstile(driver):
    """
    Attempts automated stealth interaction for Cloudflare Turnstile checkbox.
    """
    try:
        iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']")
        for frame in iframes:
            try:
                driver.switch_to.frame(frame)
                time.sleep(0.6)
                checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'], span.mark, .ctp-checkbox-label")
                for cb in checkboxes:
                    if cb.is_displayed():
                        cb.click()
                        time.sleep(1.5)
                        driver.switch_to.default_content()
                        return True
                driver.switch_to.default_content()
            except Exception:
                driver.switch_to.default_content()
    except Exception:
        try:
            driver.switch_to.default_content()
        except:
            pass
    return False


def handle_security_challenge(driver, wait_seconds=12, show_browser=True, worker_tag="", update_status_cb=None, user_id=None):
    """
    Unified challenge handler: detects, attempts automated bypass, and waits for resolution.
    """
    check = detect_captcha(driver)
    if not check["detected"]:
        return {"resolved": True, "type": None, "message": "No challenge detected"}

    tag_str = f"[{worker_tag}] " if worker_tag else ""
    log_msg = f"{tag_str}🛡️ Security Challenge Detected: {check['details']} ({check['type']})"
    if update_status_cb and user_id:
        update_status_cb(user_id, log=log_msg)

    # 1. Attempt automated turnstile stealth bypass
    if "cloudflare" in check["type"]:
        try_solve_turnstile(driver)

    # 2. Polling loop with grace period
    start_time = time.time()
    while time.time() - start_time < wait_seconds:
        time.sleep(1.2)
        current_check = detect_captcha(driver)
        if not current_check["detected"]:
            success_msg = f"{tag_str}✅ Security challenge cleared successfully ({check['type']})!"
            if update_status_cb and user_id:
                update_status_cb(user_id, log=success_msg)
            return {"resolved": True, "type": check["type"], "message": success_msg}

    # If still not resolved
    if show_browser:
        fail_msg = f"{tag_str}⚠️ Security challenge active (timed out after {wait_seconds}s)."
    else:
        fail_msg = f"{tag_str}❌ Security challenge active in Headless mode (skipped)."

    return {"resolved": False, "type": check["type"], "message": fail_msg}

import sys
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except:
    pass

import time
import random
import re
import csv
import os
import json
import urllib.parse
import sqlite3
import threading
import queue
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains

from form_filler_engine import UniversalFormFiller, find_universal_contact_page
from ai_personalizer import generate_ai_personalized_message, extract_store_context
from captcha_solver import handle_security_challenge, detect_captcha
from proxy_manager import ProxyManager

# ================================================================
#  GEO DICTIONARIES (States & Abbreviations)
# ================================================================
US_STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO",
    "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
    "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY"
}

CA_PROVINCES = {
    "Ontario": "ON", "Quebec": "QC", "British Columbia": "BC", "Alberta": "AB",
    "Manitoba": "MB", "Saskatchewan": "SK", "Nova Scotia": "NS", "New Brunswick": "NB",
    "Newfoundland and Labrador": "NL", "Prince Edward Island": "PE"
}

AU_STATES = {
    "New South Wales": "NSW", "Victoria": "VIC", "Queensland": "QLD",
    "Western Australia": "WA", "South Australia": "SA", "Tasmania": "TAS"
}

MAJOR_STATE_CITIES = {
    "California": ["Los Angeles", "San Francisco", "San Diego", "San Jose", "Sacramento", "Orange County", "Beverly Hills", "Irvine"],
    "Texas": ["Houston", "Dallas", "Austin", "San Antonio", "Fort Worth", "Arlington", "Plano"],
    "Florida": ["Miami", "Orlando", "Tampa", "Jacksonville", "Fort Lauderdale", "St. Petersburg"],
    "New York": ["New York City", "Brooklyn", "Buffalo", "Rochester", "Albany", "Manhattan", "Queens"],
    "Illinois": ["Chicago", "Naperville", "Rockford"],
    "Georgia": ["Atlanta", "Savannah", "Augusta"],
    "North Carolina": ["Charlotte", "Raleigh", "Greensboro"],
    "Washington": ["Seattle", "Bellevue", "Tacoma", "Spokane"],
    "Arizona": ["Phoenix", "Scottsdale", "Tucson"],
    "Colorado": ["Denver", "Boulder", "Colorado Springs"],
    "Massachusetts": ["Boston", "Cambridge", "Worcester"],
    "Ontario": ["Toronto", "Ottawa", "Mississauga", "Hamilton"],
    "British Columbia": ["Vancouver", "Victoria", "Surrey"],
    "Quebec": ["Montreal", "Quebec City", "Laval"],
    "New South Wales": ["Sydney", "Newcastle", "Wollongong"],
    "Victoria": ["Melbourne", "Geelong", "Ballarat"],
    "Queensland": ["Brisbane", "Gold Coast", "Sunshine Coast"],
    "England": ["London", "Manchester", "Birmingham", "Leeds", "Liverpool"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur"],
    "Delhi": ["New Delhi", "Noida", "Gurugram"],
    "Karnataka": ["Bangalore", "Mysore"],
    "Punjab": ["Lahore", "Faisalabad", "Rawalpindi", "Multan"],
    "Sindh": ["Karachi", "Hyderabad"],
    "Dubai": ["Downtown Dubai", "Deira", "Jumeirah", "Marina"]
}

def normalize_state_name(state_raw):
    """
    Extracts (clean_name, code) from input like:
    'California (CA)' -> ('California', 'CA')
    'New York (NY)'   -> ('New York', 'NY')
    'CA'              -> ('California', 'CA')
    'California'      -> ('California', 'CA')
    """
    if not state_raw:
        return "", ""
    s = str(state_raw).strip()
    code = ""
    m = re.search(r'\(([A-Za-z0-9\s\-]+)\)', s)
    if m:
        code = m.group(1).strip()
    clean_name = re.sub(r'\(.*?\)', '', s).strip()

    # Match in geo dicts
    for d in (US_STATES, CA_PROVINCES, AU_STATES):
        if clean_name in d:
            code = code or d[clean_name]
            return clean_name, code
        for full_name, abbr in d.items():
            if clean_name.upper() == abbr.upper() or s.upper() == abbr.upper() or clean_name.lower() == full_name.lower():
                return full_name, abbr
    return clean_name, code

# ================================================================
#  USER SETTINGS loaded from database at runtime
# ================================================================
DEFAULT_TEMPLATE = "Hi {brand} team,\n\nI came across your {niche} store and really love what you're building.\nWe're a custom manufacturer and work with brands just like yours.\n\nBest regards,\n{sender_name}\n{company_name}"

# ================================================================
#  GLOBAL PROGRESS TRACKER FOR UI (Thread-Safe)
# ================================================================
#  GLOBAL PROGRESS TRACKER & STOP CONTROLLER (Thread-Safe)
# ================================================================
SCRAPER_STATUS = {}
SCRAPER_STOP_EVENTS = {}
_status_lock = threading.Lock()

def stop_scraper_for_user(user_id):
    """Signals active scraper and all parallel workers for this user to stop immediately."""
    with _status_lock:
        ev = SCRAPER_STOP_EVENTS.get(user_id)
        if ev and not ev.is_set():
            ev.set()
            update_status(user_id, status="stopping", message="Stopping scraper...", log="🛑 [Stop Request] Stopping scraper. Gracefully closing active browser workers...")
            return True
        elif user_id in SCRAPER_STATUS and SCRAPER_STATUS[user_id].get("status") in ["running", "starting"]:
            update_status(user_id, status="stopped", message="Scraper stopped", log="🛑 Scraper stopped.")
            return True
    return False

def update_status(user_id, status=None, progress=None, total=None, message=None, log=None):
    with _status_lock:
        if user_id not in SCRAPER_STATUS:
            SCRAPER_STATUS[user_id] = {"status": "starting", "progress": 0, "total": 0, "message": "", "logs": []}
        
        if status is not None: SCRAPER_STATUS[user_id]["status"] = status
        if progress is not None: SCRAPER_STATUS[user_id]["progress"] = progress
        if total is not None: SCRAPER_STATUS[user_id]["total"] = total
        if message is not None: SCRAPER_STATUS[user_id]["message"] = message
        if log is not None:
            SCRAPER_STATUS[user_id]["logs"].append(log)
            if len(SCRAPER_STATUS[user_id]["logs"]) > 100:
                SCRAPER_STATUS[user_id]["logs"].pop(0)

# ================================================================
#  DRIVER — VISIBLE WINDOW & STEALTH MODE
# ================================================================
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

def patch_winapi_for_default_desktop():
    """Forces Windows to spawn child processes (like chromedriver and chrome)
    directly onto the user's interactive desktop (WinSta0\\Default) so Chrome
    is fully visible on the physical screen even if Flask was started in a background session."""
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        from ctypes import wintypes
        import _winapi

        user32 = ctypes.windll.user32
        h_default = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_default:
            user32.SetThreadDesktop(h_default)

        if getattr(_winapi, '_patched_for_default_desktop', False):
            return

        class STARTUPINFOW(ctypes.Structure):
            _fields_ = [
                ('cb', wintypes.DWORD),
                ('lpReserved', wintypes.LPWSTR),
                ('lpDesktop', wintypes.LPWSTR),
                ('lpTitle', wintypes.LPWSTR),
                ('dwX', wintypes.DWORD),
                ('dwY', wintypes.DWORD),
                ('dwXSize', wintypes.DWORD),
                ('dwYSize', wintypes.DWORD),
                ('dwXCountChars', wintypes.DWORD),
                ('dwYCountChars', wintypes.DWORD),
                ('dwFillAttribute', wintypes.DWORD),
                ('dwFlags', wintypes.DWORD),
                ('wShowWindow', wintypes.WORD),
                ('cbReserved2', wintypes.WORD),
                ('lpReserved2', ctypes.c_char_p),
                ('hStdInput', wintypes.HANDLE),
                ('hStdOutput', wintypes.HANDLE),
                ('hStdError', wintypes.HANDLE),
            ]

        class PROCESS_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('hProcess', wintypes.HANDLE),
                ('hThread', wintypes.HANDLE),
                ('dwProcessId', wintypes.DWORD),
                ('dwThreadId', wintypes.DWORD),
            ]

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateProcessW.argtypes = [
            wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
            wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
            ctypes.c_void_p, ctypes.c_void_p
        ]

        _orig = _winapi.CreateProcess

        def patched_create_process(appName, cmdLine, procSecAttrs, threadSecAttrs,
                                   inheritHandles, creationFlags, env, currentDir, startupInfo):
            try:
                si = STARTUPINFOW()
                si.cb = ctypes.sizeof(STARTUPINFOW)
                si.lpDesktop = r"WinSta0\Default"

                if startupInfo is not None:
                    si.dwFlags = getattr(startupInfo, 'dwFlags', 0)
                    si.wShowWindow = getattr(startupInfo, 'wShowWindow', 0)
                    if getattr(startupInfo, 'hStdInput', None):
                        si.hStdInput = int(startupInfo.hStdInput)
                    if getattr(startupInfo, 'hStdOutput', None):
                        si.hStdOutput = int(startupInfo.hStdOutput)
                    if getattr(startupInfo, 'hStdError', None):
                        si.hStdError = int(startupInfo.hStdError)

                pi = PROCESS_INFORMATION()
                env_ptr = None
                flags = creationFlags
                if env is not None:
                    full_env = os.environ.copy()
                    full_env.update(env)
                    env_str = '\0'.join(f'{k}={v}' for k, v in full_env.items()) + '\0\0'
                    env_buf = ctypes.create_unicode_buffer(env_str)
                    env_ptr = ctypes.addressof(env_buf)
                    flags |= 0x00000400  # CREATE_UNICODE_ENVIRONMENT

                cmd_buf = ctypes.create_unicode_buffer(cmdLine)
                res = kernel32.CreateProcessW(
                    appName, cmd_buf, None, None, bool(inheritHandles),
                    flags, env_ptr, currentDir, ctypes.byref(si), ctypes.byref(pi)
                )
                if not res:
                    err = ctypes.GetLastError()
                    raise ctypes.WinError(err)
                return (pi.hProcess, pi.hThread, pi.dwProcessId, pi.dwThreadId)
            except Exception:
                return _orig(appName, cmdLine, procSecAttrs, threadSecAttrs,
                             inheritHandles, creationFlags, env, currentDir, startupInfo)

        _winapi.CreateProcess = patched_create_process
        _winapi._patched_for_default_desktop = True
    except Exception:
        pass

# Initialize patch immediately on load
patch_winapi_for_default_desktop()

def _force_chrome_to_foreground(driver):
    """Forces Windows OS to bring automated Chrome to the active foreground on the user's desktop."""
    if not driver:
        return
    try:
        driver.maximize_window()
        driver.switch_to.window(driver.current_window_handle)
        driver.execute_cdp_cmd("Page.bringToFront", {})
    except Exception:
        pass

    try:
        import ctypes
        user32 = ctypes.windll.user32

        # Bypass Windows ForegroundLockTimeout restriction
        user32.AllowSetForegroundWindow(-1)  # ASFW_ANY

        h_default = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_default:
            user32.SetThreadDesktop(h_default)

        found_hwnds = []
        def enum_cb(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                class_name = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, class_name, 256)
                length = user32.GetWindowTextLengthW(hwnd)
                # In Windows, Chrome windows always have the class Chrome_WidgetWin_1
                if class_name.value == "Chrome_WidgetWin_1" and length > 0:
                    found_hwnds.append(hwnd)
            return True

        EnumDesktopWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        if h_default:
            user32.EnumDesktopWindows(h_default, EnumDesktopWindowsProc(enum_cb), 0)
        else:
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            user32.EnumWindows(EnumWindowsProc(enum_cb), 0)

        for h in found_hwnds:
            try:
                user32.ShowWindow(h, 9)  # SW_RESTORE
                user32.ShowWindow(h, 3)  # SW_MAXIMIZE
                # Pin to TOPMOST then release to NOTOPMOST to force foreground elevation on Windows
                user32.SetWindowPos(h, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
                user32.SetWindowPos(h, -2, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
                user32.BringWindowToTop(h)
                user32.SetForegroundWindow(h)
            except Exception:
                pass
    except Exception:
        pass

def create_driver(headless=False, proxy_url=None):
    patch_winapi_for_default_desktop()
    options = Options()

    # Create a unique temporary user profile so Chrome is GUARANTEED to spawn
    # an independent, dedicated visible window and never attaches to an existing background Chrome process!
    import tempfile
    profile_dir = tempfile.mkdtemp(prefix="chrome_lead_")
    print(f">> [create_driver] Spawning Chrome: headless={headless}, profile_dir={profile_dir}")
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--remote-debugging-port=0")

    # Apply Proxy if configured
    if proxy_url:
        ProxyManager.apply_proxy_to_options(options, proxy_url)

    # Explicit Chrome Binary Path on Windows
    chrome_binary = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if os.path.exists(chrome_binary):
        options.binary_location = chrome_binary

    options.add_argument(f"--user-agent={random.choice(_USER_AGENTS)}")
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
    else:
        options.add_argument("--new-window")
        options.add_argument("--window-size=1366,850")
        options.add_argument("--window-position=50,50")
        options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])

    # Use installed ChromeDriver or let Selenium Manager handle it
    driver_cache = r"C:\Users\HEX\.cache\selenium\chromedriver\win64\153.0.8010.52\chromedriver.exe"
    try:
        if os.path.exists(driver_cache):
            driver = webdriver.Chrome(service=Service(driver_cache), options=options)
        else:
            driver = webdriver.Chrome(options=options)
    except Exception as e:
        print(f"Driver init error: {e}, attempting default fallback...")
        driver = webdriver.Chrome(options=options)

    stealth_js = """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.chrome = { runtime: {} };
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
    """
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": stealth_js})
    except:
        pass

    if not headless:
        _force_chrome_to_foreground(driver)

    return driver

def get_db_path():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
        db_path = os.path.join(base_dir, 'database.db')
        if not os.path.exists(db_path):
            bundled_db = os.path.join(getattr(sys, '_MEIPASS', ''), 'database.db')
            if os.path.exists(bundled_db):
                import shutil
                try:
                    shutil.copy2(bundled_db, db_path)
                except:
                    pass
        return db_path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')

def create_db_connection():
    conn = sqlite3.connect(get_db_path(), timeout=60.0, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except:
        pass
    return conn

# ================================================================
#  HUMAN BEHAVIOUR SIMULATION
# ================================================================
def random_delay(a=2, b=4):
    time.sleep(random.uniform(a, b))

def human_type(element, text):
    try:
        element.clear()
    except:
        pass
    chars_since_pause = 0
    next_pause_at = random.randint(15, 30)
    for char in text:
        element.send_keys(char)
        chars_since_pause += 1
        if char == ' ':
            time.sleep(random.uniform(0.06, 0.15))
        elif char in '.,!?@':
            time.sleep(random.uniform(0.08, 0.2))
        else:
            time.sleep(random.uniform(0.02, 0.07))
        if chars_since_pause >= next_pause_at:
            time.sleep(random.uniform(0.2, 0.5))
            chars_since_pause = 0
            next_pause_at = random.randint(15, 30)

def human_scroll(driver):
    scrolls = random.randint(2, 3)
    for i in range(scrolls):
        if random.random() < 0.2:
            driver.execute_script(f"window.scrollBy(0, -{random.randint(50, 150)})")
        else:
            driver.execute_script(f"window.scrollBy(0, {random.randint(150, 450)})")
        time.sleep(random.uniform(0.2, 0.6))
    time.sleep(random.uniform(0.2, 0.4))

def human_move_to(driver, element):
    try:
        action = ActionChains(driver)
        action.move_to_element(element)
        action.pause(random.uniform(0.1, 0.3))
        action.click()
        action.perform()
    except Exception:
        element.click()

def maybe_pause():
    if random.random() < 0.2:
        time.sleep(random.uniform(0.8, 1.8))

def warm_up_page(driver):
    human_scroll(driver)
    maybe_pause()

# ================================================================
# ================================================================
#  PROFESSIONAL EXTRACTION & DATA CLEANING HELPERS
# ================================================================
def clean_url(url):
    """Returns clean canonical homepage URL."""
    try:
        p = urlparse(url)
        scheme = p.scheme or "https"
        netloc = p.netloc.lower()
        if netloc.startswith("www."):
            pass
        return f"{scheme}://{netloc}/"
    except:
        return url

def extract_emails(html):
    """
    Extracts, deduplicates, and filters valid business emails.
    Strips out tracking pixels, framework artifacts, and junk.
    """
    if not html:
        return ""
    
    # Strict email regex
    raw_matches = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", html)
    
    junk_patterns = [
        "example", "sentry", "wix", "shopify", "bootstrap", "schema",
        "domain.com", "email.com", "yourdomain", "test.com", "cloudflare",
        "googletagmanager", "sentry.io", "wixpress", "static", "wp-content",
        "noreply", "no-reply", "donotreply", ".png", ".jpg", ".jpeg", ".gif",
        ".svg", ".webp", ".css", ".js", "2x"
    ]
    
    valid_emails = []
    seen = set()
    
    for email in raw_matches:
        e = email.strip().lower()
        # Filter invalid extension / junk
        if any(j in e for j in junk_patterns):
            continue
        if e.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".js", ".css")):
            continue
        if len(e) < 6 or len(e) > 55:
            continue
        if e not in seen:
            seen.add(e)
            valid_emails.append(e)
            
    # Sort priority business emails to the front (info@, contact@, sales@, support@, hello@)
    priority_prefixes = ("info@", "contact@", "sales@", "support@", "hello@", "orders@", "help@", "team@")
    valid_emails.sort(key=lambda x: 0 if x.startswith(priority_prefixes) else 1)
    
    return ", ".join(valid_emails[:3])

def extract_phone(driver, html):
    """Extracts clean formatted phone number from tel: links or DOM."""
    try:
        # Check tel: links first
        for a in driver.find_elements(By.CSS_SELECTOR, "a[href^='tel:']"):
            href = a.get_attribute("href") or ""
            phone = href.replace("tel:", "").strip()
            if len(phone) >= 7:
                return phone
    except:
        pass
        
    # Regex fallback in footer or contact section
    match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', html or '')
    if match:
        p = match.group(0).strip()
        if len(p) >= 10:
            return p
    return ""

def extract_social_links(driver, html):
    """Extracts clean Instagram and Facebook social handles."""
    socials = {}
    try:
        for a in driver.find_elements(By.TAG_NAME, "a"):
            href = (a.get_attribute("href") or "").strip()
            if "instagram.com/" in href and not any(x in href for x in ["/p/", "/explore/", "/share", "/reels/"]):
                clean_ig = href.split("?")[0].rstrip("/")
                socials["instagram"] = clean_ig
            elif "facebook.com/" in href and not any(x in href for x in ["/sharer", "/share", "/groups/"]):
                clean_fb = href.split("?")[0].rstrip("/")
                socials["facebook"] = clean_fb
    except:
        pass
    
    parts = []
    if "instagram" in socials:
        parts.append(socials["instagram"])
    if "facebook" in socials:
        parts.append(socials["facebook"])
    return " | ".join(parts)

def clean_extracted_address(addr):
    """Cleans up raw extracted address text."""
    if not addr:
        return ""
    addr = re.sub(r'\s+', ' ', addr).strip(" ,.-|")
    addr = re.sub(r'^(?i)(address|our address|location|our location|office|visit us|headquarters)\s*:\s*', '', addr).strip()
    if len(addr) < 6 or len(addr) > 180:
        return ""
    if any(junk in addr.lower() for junk in ["all rights reserved", "copyright", "subscribe to our", "privacy policy", "terms of service"]):
        return ""
    return addr

def extract_address(driver, html):
    """
    Extracts physical business address from:
    1. Schema JSON-LD (PostalAddress, streetAddress, addressLocality, addressRegion, postalCode)
    2. HTML <address> tags
    3. Dedicated Address CSS containers (.contact-address, .store-address, .location, [itemprop='address'])
    4. Google Maps embed / query links (maps.google.com/?q=...)
    5. Regex text heuristics on contact page & footer (Street/Ave/Blvd/Suite + City, State Zip)
    """
    if not html:
        return ""
        
    # 1. Check JSON-LD Schema
    try:
        scripts = driver.find_elements(By.CSS_SELECTOR, "script[type='application/ld+json']")
        for s in scripts:
            raw = s.get_attribute("innerHTML") or ""
            if "address" in raw.lower() or "postaladdress" in raw.lower():
                try:
                    data = json.loads(raw)
                    def find_postal_address(obj):
                        if isinstance(obj, dict):
                            if obj.get("@type") == "PostalAddress" or "streetAddress" in obj:
                                parts = [
                                    obj.get("streetAddress", ""),
                                    obj.get("addressLocality", ""),
                                    obj.get("addressRegion", ""),
                                    obj.get("postalCode", ""),
                                    obj.get("addressCountry", "")
                                ]
                                clean_parts = [str(p).strip() for p in parts if p and str(p).strip()]
                                if clean_parts:
                                    return ", ".join(clean_parts)
                            for v in obj.values():
                                res = find_postal_address(v)
                                if res:
                                    return res
                        elif isinstance(obj, list):
                            for item in obj:
                                res = find_postal_address(item)
                                if res:
                                    return res
                        return ""
                    addr = find_postal_address(data)
                    clean = clean_extracted_address(addr)
                    if clean:
                        return clean
                except:
                    pass
    except:
        pass

    # 2. Check HTML <address> tags
    try:
        address_tags = driver.find_elements(By.TAG_NAME, "address")
        for tag in address_tags:
            text = tag.text.strip()
            if text and 8 < len(text) < 180:
                lines = [l.strip() for l in text.splitlines() if l.strip() and "@" not in l and not l.lower().startswith("tel:")]
                if lines:
                    clean = clean_extracted_address(", ".join(lines))
                    if clean:
                        return clean
    except:
        pass

    # 3. Check Common Address CSS Selectors
    address_selectors = [
        ".contact-address", ".store-address", ".office-address", ".footer-address",
        ".business-address", ".location-address", ".address", "[itemprop='address']",
        ".contact__address", ".footer__address", ".site-footer__address", ".contact-info__address"
    ]
    try:
        for selector in address_selectors:
            elems = driver.find_elements(By.CSS_SELECTOR, selector)
            for elem in elems:
                text = elem.text.strip()
                if text and 10 < len(text) < 180 and ("@" not in text or len(text.splitlines()) > 1):
                    lines = [l.strip() for l in text.splitlines() if l.strip() and "@" not in l]
                    if lines:
                        cand = ", ".join(lines)
                        if any(w in cand.lower() for w in ["st", "street", "ave", "avenue", "rd", "road", "blvd", "boulevard", "suite", "ste", "dr", "drive", "way", "highway", "hwy", "box", "po box", "floor", "unit"]):
                            clean = clean_extracted_address(cand)
                            if clean:
                                return clean
    except:
        pass

    # 4. Check Google Maps iframe / links
    try:
        for a in driver.find_elements(By.CSS_SELECTOR, "a[href*='maps.google.com'], a[href*='google.com/maps'], iframe[src*='google.com/maps']"):
            href = a.get_attribute("href") or a.get_attribute("src") or ""
            if "q=" in href:
                query = href.split("q=")[1].split("&")[0]
                query = urllib.parse.unquote_plus(query)
                if query and not query.startswith("loc:") and 8 < len(query) < 150:
                    clean = clean_extracted_address(query)
                    if clean:
                        return clean
            elif "place/" in href:
                place = href.split("place/")[1].split("/")[0]
                place = urllib.parse.unquote_plus(place).replace("+", " ")
                if place and 8 < len(place) < 150:
                    clean = clean_extracted_address(place)
                    if clean:
                        return clean
    except:
        pass

    # 5. Regex Heuristic on HTML
    street_types = r"(?:Street|St\.?|Avenue|Ave\.?|Boulevard|Blvd\.?|Road|Rd\.?|Drive|Dr\.?|Lane|Ln\.?|Highway|Hwy\.?|Way|Suite|Ste\.?|Unit|Floor|Building|Bldg\.?|PO Box|P\.O\. Box)"
    addr_pattern = rf"\b\d{{1,6}}\s+[A-Za-z0-9\s.,#-]+{street_types}[A-Za-z0-9\s.,#-]+(?:,\s*[A-Za-z\s]+)?\s+[A-Z]{{2}}\s+\d{{5}}(?:-\d{{4}})?"
    match = re.search(addr_pattern, html or "", re.IGNORECASE)
    if match:
        cand = match.group(0).strip()
        clean = clean_extracted_address(cand)
        if clean:
            return clean

    return ""

def extract_brand_name(driver, url=""):
    """
    Extracts a clean, exact brand name.
    Eliminates SEO noise, slogan fluff, and page titles like 'Home | Store'.
    """
    # 1. Check OpenGraph site_name meta tag
    try:
        og_name = driver.find_element(By.CSS_SELECTOR, "meta[property='og:site_name']").get_attribute("content")
        if og_name and len(og_name.strip()) > 1 and len(og_name.strip()) < 40:
            return og_name.strip()
    except:
        pass

    # 2. Check application-name meta tag
    try:
        app_name = driver.find_element(By.CSS_SELECTOR, "meta[name='application-name']").get_attribute("content")
        if app_name and len(app_name.strip()) > 1 and len(app_name.strip()) < 40:
            return app_name.strip()
    except:
        pass

    # 3. Check JSON-LD Schema Organization Name
    try:
        scripts = driver.find_elements(By.CSS_SELECTOR, "script[type='application/ld+json']")
        for s in scripts:
            content = s.get_attribute("innerHTML") or ""
            if '"name"' in content:
                match = re.search(r'"name"\s*:\s*"([^"]+)"', content)
                if match:
                    name_cand = match.group(1).strip()
                    if name_cand and len(name_cand) < 40 and not any(w in name_cand.lower() for w in ["homepage", "index", "store", "http"]):
                        return name_cand
    except:
        pass

    # 4. Parse Title tag with Stopword and Separator Cleanup
    try:
        title = driver.title or ""
        # Remove separators
        for sep in ["|", "–", "—", "-", "•", ":", "·"]:
            if sep in title:
                parts = title.split(sep)
                # Usually brand is first or last part
                first = parts[0].strip()
                last = parts[-1].strip()
                
                # Check if first part is generic
                generic_words = ["home", "welcome", "buy", "shop", "official", "store", "online", "collection", "cart"]
                if not any(g == first.lower() for g in generic_words) and len(first) > 1:
                    title = first
                elif len(last) > 1 and not any(g == last.lower() for g in generic_words):
                    title = last
                else:
                    title = first
                break
                
        # Remove trailing slogans
        slogans = [
            "official site", "official store", "online store", "free shipping",
            "powered by shopify", "shopify store", "online shopping", "buy online"
        ]
        for sl in slogans:
            title = re.sub(rf"(?i){re.escape(sl)}", "", title).strip()
            
        title = title.strip(" -|:•–—")
        if title and len(title) >= 2 and len(title) < 45 and title.lower() not in ["home", "welcome", "index"]:
            return title.title() if title.islower() or title.isupper() else title
    except:
        pass

    # 5. Clean Domain Fallback
    try:
        p = urlparse(url or driver.current_url)
        domain = p.netloc.lower().replace("www.", "")
        domain_name = domain.split(".")[0]
        domain_clean = re.sub(r'[-_]', ' ', domain_name).title()
        if domain_clean and domain_clean.lower() not in ["myshopify", "wixsite", "squarespace"]:
            return domain_clean
    except:
        pass

    return "Brand Partner"

def detect_niche(html, keyword=""):
    """Returns standardized, clean capitalized niche category."""
    html_lower = (html or "").lower()
    kw_lower = (keyword or "").lower()
    
    if any(k in html_lower or k in kw_lower for k in ["hat", "cap", "headwear", "beanie", "snapback", "beret", "visor"]):
        return "Headwear & Accessories"
    if any(k in html_lower or k in kw_lower for k in ["streetwear", "hoodie", "apparel", "clothing", "fashion", "jacket", "shirt", "t-shirt"]):
        return "Apparel & Streetwear"
    if any(k in html_lower or k in kw_lower for k in ["fitness", "gym", "workout", "athletic", "activewear", "yoga", "sportswear"]):
        return "Fitness & Activewear"
    if any(k in html_lower or k in kw_lower for k in ["shoe", "sneaker", "boot", "sandals", "footwear"]):
        return "Footwear & Shoes"
    if any(k in html_lower or k in kw_lower for k in ["beauty", "skincare", "cosmetic", "makeup", "fragrance", "perfume", "serum"]):
        return "Beauty & Cosmetics"
    if any(k in html_lower or k in kw_lower for k in ["jewel", "necklace", "ring", "bracelet", "earring", "watch", "luxury"]):
        return "Jewelry & Luxury"
    if any(k in html_lower or k in kw_lower for k in ["furniture", "decor", "home", "kitchen", "living", "bedding"]):
        return "Home & Living"
    if any(k in html_lower or k in kw_lower for k in ["pet", "dog", "cat", "puppy"]):
        return "Pet Supplies"
    if any(k in html_lower or k in kw_lower for k in ["coffee", "tea", "snack", "food", "beverage", "drink", "organic"]):
        return "Food & Beverage"
        
    if keyword and len(keyword) > 2:
        return f"{keyword.strip().title()} Retail"
        
    return "E-Commerce / Retail"

def get_homepage(url):
    return clean_url(url)

def is_valid_store_url(url):
    url = url.lower()
    skip = [
        "blog", "news", "article", "guide", "top-", "best-", "review",
        "list", "directory", "reddit", "youtube", "facebook",
        "instagram", "linkedin", "wikipedia", "quora", "pinterest",
        "duckduckgo.com", "duck.ai", "duck.com", "about.duckduckgo",
        "google.com", "bing.com", "yahoo.com", "baidu.com",
        "twitter.com", "x.com", "tiktok.com", "amazon.", "ebay.",
        "walmart.", "etsy.", "aliexpress.", "alibaba.",
        "github.com", "stackoverflow.com", "medium.com",
    ]
    if any(s in url for s in skip):
        return False
    if url.count("/") > 4:
        return False
    return True

def detect_platform(driver):
    """Detects CMS/Platform from page DOM and scripts."""
    try:
        html = driver.page_source.lower()
    except:
        return "Custom / Independent"

    if any(i in html for i in ["cdn.shopify.com", "shopify-payment-button", "shopify-section", "shopify.com/s/files", "window.shopify"]):
        return "Shopify"
    if any(i in html for i in ["wp-content", "wp-includes", "woocommerce", "wp-json", "wpforms"]):
        return "WooCommerce"
    if any(i in html for i in ["wixsite.com", "static.wixstatic.com", "wix.com", "_wix"]):
        return "Wix"
    if any(i in html for i in ["squarespace.com", "static1.squarespace.com", "squarespace-cdn.com"]):
        return "Squarespace"
    if any(i in html for i in ["cdn11.bigcommerce.com", "bigcommerce.com", "mybigcommerce.com"]):
        return "BigCommerce"
    if any(i in html for i in ["cart", "checkout", "add-to-cart", "add to cart", "shop", "products", "price"]):
        return "Custom / Independent"
    return "Custom / Independent"

def verify_state(html, target_state, country):
    """
    Checks if page content or address matches the targeted state.
    Returns: (is_matched: bool, detected_state: str)
    """
    if not target_state or str(target_state).strip().upper() in ["", "ALL", "ANY", "ALL STATES", "ALL PROVINCES"]:
        return True, "All States"

    clean_name, code = normalize_state_name(target_state)
    html_lower = (html or "").lower()

    # 1. Look for clean full state name
    if clean_name and clean_name.lower() in html_lower:
        return True, clean_name

    # 2. Look for state code in address patterns or boundary
    if code:
        pattern = rf'(?:,\s*{re.escape(code)}\b|\b{re.escape(code)}\s+\d{{4,5}}|\b{re.escape(code)},\s*(?:USA|US|CA|AU)\b|\b{re.escape(code)}\b)'
        if re.search(pattern, html_lower, re.IGNORECASE):
            return True, clean_name or target_state

    # 3. Check schema.org structured data JSON-LD
    for term in [clean_name, code, target_state]:
        if term:
            schema_pattern = rf'"addressRegion"\s*:\s*"{re.escape(term)}"'
            if re.search(schema_pattern, html_lower, re.IGNORECASE):
                return True, clean_name or target_state

    # 4. Check city mentions for major states
    cities = MAJOR_STATE_CITIES.get(clean_name, [])
    for city in cities:
        if city.lower() in html_lower:
            return True, clean_name or target_state

    return False, ""

def generate_message(brand, niche, template, sender_name, company_name):
    return template.format(
        brand=brand,
        niche=niche,
        sender_name=sender_name,
        company_name=company_name
    )

# ================================================================
#  UNIVERSAL CONTACT PAGE DISCOVERY (35+ Variations & Smart Filter)
# ================================================================
def find_contact_page(driver):
    """
    Finds and verifies the contact page using the ContactPageDiscoveryEngine.
    """
    try:
        return find_universal_contact_page(driver)
    except Exception as e:
        print(f"Error finding contact page: {e}")
        return ""

def try_submit_form(driver):
    """
    Submits the contact form using the UniversalFormFiller engine.
    """
    try:
        engine = UniversalFormFiller(driver)
        return engine.try_submit()
    except Exception as e:
        print(f"Error submitting form: {e}")
        return False

def fill_form(driver, brand, niche, settings):
    """
    Fills all contact form fields using AI Personalization or Shuffled Templates.
    """
    sender_name  = settings.get("full_name")  or "Our Team"
    sender_email = settings.get("sender_email") or ""
    company_name = settings.get("company_name") or "Our Company"
    ai_enabled   = settings.get("ai_enabled", False)
    api_key      = settings.get("gemini_api_key", "")

    message = ""
    # 1. Try Gemini AI Personalization if enabled
    if ai_enabled and api_key:
        try:
            store_context = extract_store_context(driver)
            ai_ok, ai_text = generate_ai_personalized_message(
                brand=brand,
                niche=niche,
                context=store_context,
                sender_name=sender_name,
                company_name=company_name,
                api_key=api_key,
                tone=settings.get("ai_tone", "b2b_wholesale"),
                custom_instructions=settings.get("ai_custom_prompt", "")
            )
            if ai_ok:
                message = ai_text
                print(f"[Gemini AI] Personalized hook generated for {brand}")
        except Exception as e:
            print(f"[Gemini AI Fallback] {e}")

    # 2. Fallback to shuffled templates if AI is off or fails
    if not message:
        templates = settings.get("templates") or [DEFAULT_TEMPLATE]
        template  = random.choice(templates)
        message   = generate_message(brand, niche, template, sender_name, company_name)

    try:
        engine = UniversalFormFiller(driver)
        success, filled_fields = engine.fill_form_fields(brand, niche, settings, message)
        return success, message
    except Exception as e:
        print(f"UniversalFormFiller error: {e}")
        return False, message


# ================================================================
#  SEARCH QUERY BUILDER (State & Multi-Platform Dorks)
# ================================================================
def build_search_queries(keyword, country, state, platforms):
    # Clean parentheses e.g. "United States (USA)" -> "USA" or "United States"
    clean_country = re.sub(r'\(.*?\)', '', country or '').strip()
    clean_state = re.sub(r'\(.*?\)', '', state or '').strip()

    state_term = f'"{clean_state}"' if clean_state and clean_state.upper() not in ["ALL", "ANY", ""] else ""
    loc = f"{state_term} {clean_country}".strip()

    if not platforms:
        selected_platforms = ["Shopify", "WordPress", "Custom"]
    else:
        selected_platforms = platforms

    queries = []
    for p in selected_platforms:
        p_name = p.lower()
        if "shopify" in p_name:
            queries.extend([
                f'site:myshopify.com "{keyword}" {loc}',
                f'"{keyword}" "powered by shopify" {loc}',
                f'"{keyword}" shopify store {loc}',
            ])
        elif "wordpress" in p_name or "woocommerce" in p_name:
            queries.extend([
                f'"{keyword}" "powered by woocommerce" {loc}',
                f'"{keyword}" inurl:/wp-content/ {loc} ("shop" OR "cart")',
                f'"{keyword}" "woocommerce" store {loc}',
            ])
        elif "wix" in p_name:
            queries.extend([
                f'"{keyword}" site:wixsite.com {loc}',
                f'"{keyword}" "proudly created with wix" {loc}',
            ])
        elif "squarespace" in p_name:
            queries.extend([
                f'"{keyword}" "powered by squarespace" {loc}',
                f'site:squarespace.com "{keyword}" {loc}',
            ])
        elif "bigcommerce" in p_name:
            queries.extend([
                f'"{keyword}" "powered by bigcommerce" {loc}',
                f'site:mybigcommerce.com "{keyword}" {loc}',
            ])
        elif "custom" in p_name or "general" in p_name or "all" in p_name:
            queries.extend([
                f'"{keyword}" "online store" {loc} ("contact us" OR "about us") -site:amazon.* -site:ebay.* -site:walmart.* -site:etsy.*',
                f'"{keyword}" "brand" {loc} ("contact" OR "get in touch") ("shop" OR "store")',
            ])

    # City-level query expansion for deep candidate discovery in specific states
    if state and state in MAJOR_STATE_CITIES:
        for city in MAJOR_STATE_CITIES[state][:4]:
            city_loc = f'"{city}" {country}'.strip()
            for p in selected_platforms[:2]:
                if "shopify" in p.lower():
                    queries.append(f'site:myshopify.com "{keyword}" {city_loc}')
                elif "wordpress" in p.lower():
                    queries.append(f'"{keyword}" "powered by woocommerce" {city_loc}')
                else:
                    queries.append(f'"{keyword}" "online store" {city_loc}')

    if not queries:
        queries = [
            f'"{keyword}" store {loc}',
            f'site:myshopify.com "{keyword}" {loc}'
        ]

    return queries

# ================================================================
#  STEP 1 — COLLECT ALL CANDIDATE LINKS (WITH GEOFENCE BUFFER)
# ================================================================
def collect_all_links(driver, keyword, country, state, platforms, max_leads, user_id, strict_state=True, stop_event=None):
    all_links = set()
    queries = build_search_queries(keyword, country, state, platforms)

    # If strict geofencing is on, collect a 2.5x candidate buffer to guarantee target leads count
    candidate_target = int(max_leads * 2.5) if (strict_state and state and state.upper() not in ["ALL", "ANY", ""]) else max_leads
    candidate_target = max(candidate_target, max_leads)

    update_status(user_id, log=f"Targeting: {country} | State: {state or 'All'} | Target Buffer: {candidate_target} candidate stores | Platforms: {', '.join(platforms or ['All'])}")

    for q_idx, query in enumerate(queries):
        if stop_event and stop_event.is_set():
            update_status(user_id, log="🛑 Candidate discovery stopped by user.")
            break
        if len(all_links) >= candidate_target: break
        update_status(user_id, message=f"Searching ({q_idx+1}/{len(queries)})...", log=f"🔍 [{q_idx+1}/{len(queries)}] {query}")
        search_success = False
        for _retry in range(3):
            try:
                encoded_q = urllib.parse.quote_plus(query)
                driver.get(f"https://duckduckgo.com/?q={encoded_q}")
                _force_chrome_to_foreground(driver)
                time.sleep(random.uniform(3.0, 5.0))
                search_success = True
                break
            except Exception as e:
                err_str = str(e)
                if "ERR_CONNECTION_TIMED_OUT" in err_str or "ERR_CONNECTION_RESET" in err_str:
                    wait_secs = 8 * (_retry + 1)
                    update_status(user_id, log=f"⚠️ DDG rate-limit detected, waiting {wait_secs}s before retry...")
                    time.sleep(wait_secs)
                else:
                    update_status(user_id, log=f"Search query error: {e}")
                    break
        if not search_success:
            continue

        for _page in range(3):
            if len(all_links) >= candidate_target: break
            try:
                # DuckDuckGo result selectors — prioritize exact result title links
                anchors = driver.find_elements(By.CSS_SELECTOR, "a[data-testid='result-title-a']")
                if not anchors:
                    anchors = driver.find_elements(By.CSS_SELECTOR, "h2 a[href^='http']")
                if not anchors:
                    anchors = driver.find_elements(By.CSS_SELECTOR, "a.result__a")

                for r in anchors:
                    if len(all_links) >= candidate_target: break
                    try:
                        link = r.get_attribute("href") or ""
                        if not link or not link.startswith("http"):
                            continue
                        # Handle legacy DuckDuckGo redirect wrapping (if present)
                        if "uddg=" in link:
                            m = re.search(r'uddg=([^&]+)', link)
                            if m:
                                link = urllib.parse.unquote(m.group(1))
                        # Skip DuckDuckGo internal links
                        if "duckduckgo.com" in link:
                            continue
                        if is_valid_store_url(link):
                            hp = get_homepage(link)
                            if hp and len(hp) > 8:
                                all_links.add(hp)
                    except:
                        continue

                # Try clicking next page if we need more
                if len(all_links) < candidate_target:
                    try:
                        next_btn = driver.find_element(By.CSS_SELECTOR, "a[rel='next'], button#more-results")
                        driver.execute_script("arguments[0].click();", next_btn)
                        time.sleep(random.uniform(1.5, 2.0))
                    except:
                        break
                else:
                    break
            except:
                break

        update_status(user_id, log=f"Candidate pool: {len(all_links)} stores discovered...")
        if len(all_links) >= candidate_target:
            break
        time.sleep(1)

    final = list(all_links)
    update_status(user_id, message="Collection Done. Starting Verification...", log=f"🎯 {len(final)} candidates queued for on-page state verification & lead generation.", total=min(len(final), max_leads))
    return final

# ================================================================
#  STEP 2 — PROCESS EACH STORE
# ================================================================
# ================================================================
#  STEP 2 — PROCESS EACH STORE (Parallel Multi-Worker Engine)
# ================================================================
def process_single_store(driver, raw_url, cursor, conn, user_id, settings, country="USA", state="", platforms=None, strict_state=True, keyword="", worker_tag=""):
    url = clean_url(raw_url)
    tag_prefix = f"[{worker_tag}] " if worker_tag else ""
    update_status(user_id, message=f"{tag_prefix}Scanning {url}", log=f"{tag_prefix}🌐 Visiting {url}")
    
    brand = niche = email = contact_url = phone = socials = address = ""
    try:
        driver.get(url)
        _force_chrome_to_foreground(driver)
        random_delay(1.5, 2.5)
        warm_up_page(driver)

        # Check for Cloudflare / Captcha Challenge on landing
        sec_result = handle_security_challenge(
            driver, wait_seconds=8, show_browser=settings.get("show_browser", True),
            worker_tag=worker_tag, update_status_cb=update_status, user_id=user_id
        )
        if not sec_result["resolved"]:
            update_status(user_id, log=f"{tag_prefix}⚠️ {url}: Security challenge could not be bypassed — saving with blocked status")
            brand = extract_brand_name(driver, url)
            lead = row(url, brand, "General", "", "", "captcha_blocked", "", country, state or "General", "Unknown", "", "", "", "Low")
            save_to_database(cursor, conn, lead, user_id)
            return lead

        html = driver.page_source
        detected_platform = detect_platform(driver)

        # Check Platform Filter if user specified
        if platforms and "All" not in platforms:
            platform_match = any(p.lower() in detected_platform.lower() or detected_platform.lower() in p.lower() for p in platforms)
            if not platform_match:
                update_status(user_id, log=f"{tag_prefix}ℹ️ Platform mismatch ({detected_platform}) — skipping")
                return None

        # State Geo-Verification
        state_match, detected_state = verify_state(html, state, country)
        clean_state_name, _ = normalize_state_name(state)

        # Clean and Extract fields from Homepage
        email = extract_emails(html)
        phone = extract_phone(driver, html)
        address = extract_address(driver, html)
        socials = extract_social_links(driver, html)
        brand = extract_brand_name(driver, url)
        niche = detect_niche(html, keyword)

        # If not matched on homepage, check if extracted address contains the state
        if not state_match and address:
            addr_match, addr_det = verify_state(address, state, country)
            if addr_match:
                state_match = True
                detected_state = addr_det

        contact_url = find_contact_page(driver)

        # If strict_state is enabled and still not matched, check contact page if available
        if strict_state and state and clean_state_name and not state_match:
            if contact_url:
                try:
                    driver.get(contact_url)
                    random_delay(1.2, 1.8)
                    contact_html = driver.page_source
                    c_match, c_det = verify_state(contact_html, state, country)
                    if c_match:
                        state_match = True
                        detected_state = c_det
                except:
                    pass

            if not state_match:
                update_status(user_id, log=f"{tag_prefix}❌ Outside target state ({clean_state_name or state}) — skipping store")
                return None

        final_state = clean_state_name if state_match else (detected_state or clean_state_name or state or "General")

        # Lead Quality & Relevance Rating
        if email and (phone or address or socials):
            lead_category = "High"
        elif email or phone or address:
            lead_category = "Medium"
        else:
            lead_category = "Low"

        contact_url = find_contact_page(driver)
        if not contact_url:
            update_status(user_id, log=f"{tag_prefix}ℹ️ {brand}: No contact form found — saving lead details")
            lead = row(url, brand, niche, email, "", "no_contact_page", "", country, final_state, detected_platform, phone, socials, address, lead_category)
            save_to_database(cursor, conn, lead, user_id)
            return lead

        update_status(user_id, log=f"{tag_prefix}📋 {brand}: Contact Page found ({contact_url})")
        driver.get(contact_url)
        random_delay(1.2, 2.0)
        warm_up_page(driver)

        # Check for Cloudflare / Captcha Challenge on contact page
        contact_sec = handle_security_challenge(
            driver, wait_seconds=8, show_browser=settings.get("show_browser", True),
            worker_tag=worker_tag, update_status_cb=update_status, user_id=user_id
        )

        # Re-extract emails, phone, or address from contact page if missing
        contact_html = driver.page_source
        if not email:
            email = extract_emails(contact_html)
        if not phone:
            phone = extract_phone(driver, contact_html)
        if not address:
            address = extract_address(driver, contact_html)

        if email and (phone or address or socials):
            lead_category = "High"
        elif email or phone or address:
            lead_category = "Medium"

        success, message = fill_form(driver, brand, niche, settings)

        if not success:
            lead = row(url, brand, niche, email, contact_url, "form_not_filled", "", country, final_state, detected_platform, phone, socials, address, lead_category)
            save_to_database(cursor, conn, lead, user_id)
            update_status(user_id, log=f"{tag_prefix}ℹ️ {brand}: Form fields could not be matched — lead saved")
            return lead

        # Auto-submit
        random_delay(0.8, 1.4)
        submitted = try_submit_form(driver)
        random_delay(1.2, 2.0)

        if submitted:
            status = "submitted"
            update_status(user_id, log=f"{tag_prefix}🚀 {brand}: Form filled & submitted successfully!")
        else:
            status = "submit_failed"
            update_status(user_id, log=f"{tag_prefix}⚠️ {brand}: Form filled (ready for submission)")

        lead = row(url, brand, niche, email, contact_url, status, message, country, final_state, detected_platform, phone, socials, address, lead_category)
        save_to_database(cursor, conn, lead, user_id)
        return lead

    except Exception as e:
        update_status(user_id, log=f"{tag_prefix}❌ Error on {url}: {e}")
        return None

def process_stores_parallel(links, user_id, settings=None, country="USA", state="", platforms=None, strict_state=True, max_leads=50, keyword="", show_browser=True, num_workers=2, stop_event=None):
    if settings is None:
        settings = load_user_settings(user_id)

    num_workers = max(1, min(int(num_workers or 2), 5))
    num_workers = min(num_workers, max(1, len(links)))

    # Proxy manager setup
    proxy_mgr = None
    if settings.get("proxy_enabled") and settings.get("proxy_list"):
        proxy_mgr = ProxyManager(settings.get("proxy_list"))
        update_status(user_id, log=f"🌐 Rotating Proxies Active ({len(proxy_mgr.proxies)} proxies in pool).")

    update_status(user_id, message=f"Starting {num_workers} Parallel Scraper Workers...", log=f"⚡ Concurrency active: {num_workers} Parallel Worker Threads launched.")

    url_queue = queue.Queue()
    for idx, raw_url in enumerate(links):
        url_queue.put((idx + 1, raw_url))

    results = []
    results_lock = threading.Lock()
    if stop_event is None:
        stop_event = threading.Event()

    def worker_thread(worker_id):
        worker_tag = f"Worker #{worker_id}"
        driver = None
        conn = None
        try:
            conn = create_db_connection()
            cursor = conn.cursor()
            worker_proxy = proxy_mgr.get_proxy(worker_id) if proxy_mgr else None
            driver = create_driver(headless=not show_browser, proxy_url=worker_proxy)

            while not stop_event.is_set():
                try:
                    item = url_queue.get_nowait()
                except queue.Empty:
                    break

                idx, raw_url = item
                with results_lock:
                    if len(results) >= max_leads or stop_event.is_set():
                        stop_event.set()
                        url_queue.task_done()
                        break

                lead = process_single_store(
                    driver, raw_url, cursor, conn, user_id, settings,
                    country=country, state=state, platforms=platforms,
                    strict_state=strict_state, keyword=keyword, worker_tag=worker_tag
                )

                if lead:
                    with results_lock:
                        results.append(lead)
                        count = len(results)
                        update_status(user_id, progress=count, total=max_leads, message=f"Verified {count}/{max_leads} leads ({worker_tag})", log=f"{worker_tag} ✅ Verified #{count}: {lead['brand']} ({lead['platform']}) | Quality: {lead['lead_category']}")
                        if count >= max_leads:
                            stop_event.set()
                            update_status(user_id, log=f"🎯 Target of {max_leads} verified leads reached! Stopping workers.")

                url_queue.task_done()

        except Exception as e:
            update_status(user_id, log=f"{worker_tag} Encountered thread error: {e}")
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            if conn:
                try:
                    cursor.close()
                    conn.close()
                except:
                    pass

    threads = []
    for w in range(1, num_workers + 1):
        t = threading.Thread(target=worker_thread, args=(w,))
        t.daemon = True
        threads.append(t)
        t.start()
        time.sleep(0.8)

    for t in threads:
        t.join(timeout=1800)

    return results

def process_stores(driver, links, cursor, conn, user_id, settings=None, country="USA", state="", platforms=None, strict_state=True, max_leads=50, keyword=""):
    return process_stores_parallel(links, user_id, settings, country, state, platforms, strict_state, max_leads, keyword, show_browser=True, num_workers=1)

def row(url, brand, niche, email, contact, status, message, country="USA", state="", platform="Shopify", phone="", socials="", address="", lead_category="Low"):
    short_msg = (message[:120] + "...") if len(message) > 120 else message
    return {
        "url": url, "brand": brand, "niche": niche,
        "email": email, "contact_page": contact,
        "status": status, "message_sent": short_msg,
        "country": country, "state": state, "platform": platform,
        "phone": phone, "social_links": socials, "address": address, "lead_category": lead_category
    }

def save_to_database(cursor, conn, lead, user_id):
    try:
        cursor.execute("""
            INSERT INTO buyers(
                brand_name, email, website, niche, contact_page, source_url, status, generated_by, country, state, platform, phone, address, social_links, lead_category, is_relevant
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            lead["brand"], lead["email"], lead["url"], lead["niche"],
            lead["contact_page"], lead["url"], lead["status"], user_id,
            lead["country"], lead["state"], lead["platform"],
            lead.get("phone", ""), lead.get("address", ""), lead.get("social_links", ""), lead.get("lead_category", "Low")
        ))
        conn.commit()
    except Exception as e:
        print("SQLite Error:", e)

# ================================================================
#  SETTINGS LOADER & MAIN ENTRY POINT
# ================================================================
def load_user_settings(user_id):
    try:
        conn = create_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT full_name, sender_email, company_name, gemini_api_key, COALESCE(ai_enabled, 0), ai_tone, ai_custom_prompt, COALESCE(proxy_enabled, 0), COALESCE(proxy_list, '') FROM users WHERE id = ?",
            (user_id,)
        )
        row = cursor.fetchone()

        cursor.execute(
            "SELECT template_text FROM message_templates WHERE user_id = ? ORDER BY id",
            (user_id,)
        )
        tmpl_rows = cursor.fetchall()
        conn.close()

        templates = [r[0] for r in tmpl_rows] if tmpl_rows else [DEFAULT_TEMPLATE]

        if row:
            return {
                "full_name":        row[0] or "Our Team",
                "sender_email":     row[1] or "",
                "company_name":     row[2] or "Our Company",
                "gemini_api_key":   row[3] or "",
                "ai_enabled":       bool(row[4]),
                "ai_tone":          row[5] or "b2b_wholesale",
                "ai_custom_prompt": row[6] or "",
                "proxy_enabled":    bool(row[7]),
                "proxy_list":       row[8] or "",
                "templates":        templates,
            }
    except Exception as e:
        print(f"Error loading user settings: {e}")

    return {
        "full_name":        "Our Team",
        "sender_email":     "",
        "company_name":     "Our Company",
        "gemini_api_key":   "",
        "ai_enabled":       False,
        "ai_tone":          "b2b_wholesale",
        "ai_custom_prompt": "",
        "proxy_enabled":    False,
        "proxy_list":       "",
        "templates":        [DEFAULT_TEMPLATE],
    }

def log_scraping_run(user_id, keyword, country, state, platforms, leads_count, status):
    try:
        conn = create_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        username = row[0] if row else "Unknown"
        platforms_str = ", ".join(platforms) if platforms else "All Platforms"
        
        cursor.execute("""
            INSERT INTO scraping_logs (user_id, username, keyword, country, state, platforms, leads_count, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, keyword, country, state or "All", platforms_str, leads_count, status))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging scraping activity: {e}")

def scrape(keyword, country="USA", state="", platforms=None, strict_state=True, max_leads=50, user_id=None, show_browser=True, num_workers=2):
    print(f">> [scrape] Invoked: keyword='{keyword}', country='{country}', state='{state}', show_browser={show_browser}, workers={num_workers}")
    stop_event = threading.Event()
    with _status_lock:
        SCRAPER_STOP_EVENTS[user_id] = stop_event

    browser_mode = f"Visible ({num_workers} Workers)" if show_browser else f"Headless Turbo ({num_workers} Workers)"
    update_status(user_id, status="running", progress=0, total=max_leads, message="Starting Lead Discovery...", log=f"🚀 Initializing universal lead scraper [{browser_mode}]...")
    settings = load_user_settings(user_id)
    update_status(user_id, log=f"Loaded sender: {settings.get('full_name')} ({settings.get('company_name')})")

    results = []
    collector_driver = None
    try:
        collector_driver = create_driver(headless=not show_browser)
        links = collect_all_links(collector_driver, keyword, country, state, platforms, max_leads, user_id, strict_state, stop_event=stop_event)
        try:
            collector_driver.quit()
            collector_driver = None
        except:
            pass

        if stop_event.is_set():
            update_status(user_id, status="stopped", message="Scraper Stopped by User", log="🛑 Link discovery halted by user.")
            log_scraping_run(user_id, keyword, country, state, platforms, 0, "stopped")
            return

        if not links:
            update_status(user_id, status="completed", message="No Stores Found", log="No stores matched the query parameters.")
            log_scraping_run(user_id, keyword, country, state, platforms, 0, "no_results")
            return

        results = process_stores_parallel(
            links, user_id, settings, country=country, state=state,
            platforms=platforms, strict_state=strict_state, max_leads=max_leads,
            keyword=keyword, show_browser=show_browser, num_workers=num_workers,
            stop_event=stop_event
        )
    except Exception as e:
        update_status(user_id, status="error", message="Critical Error Occurred", log=str(e))
        log_scraping_run(user_id, keyword, country, state, platforms, len(results), "error")
        return
    finally:
        with _status_lock:
            SCRAPER_STOP_EVENTS.pop(user_id, None)
        if collector_driver:
            try:
                collector_driver.quit()
            except:
                pass

    if stop_event.is_set():
        update_status(user_id, status="stopped", progress=len(results), message="Scraper Stopped by User", log=f"🛑 Scraping stopped by user. Total {len(results)} verified leads preserved in database.")
        log_scraping_run(user_id, keyword, country, state, platforms, len(results), "stopped")
    else:
        update_status(user_id, status="completed", progress=len(results), message="Scraping Completed Successfully!", log=f"🎉 Scraping finished. Total {len(results)} verified leads processed.")
        log_scraping_run(user_id, keyword, country, state, platforms, len(results), "completed")
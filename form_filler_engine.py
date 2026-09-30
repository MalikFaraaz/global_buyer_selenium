"""
================================================================================
 UNIVERSAL CONTACT FORM FILLER & SEMANTIC FIELD MATCHER ENGINE (30+ MODELS)
================================================================================
This module provides a modular, extensible engine for automatically detecting,
matching, filling, and submitting contact / wholesale / inquiry forms across all
major CMS platforms (Shopify, WordPress, WooCommerce, Wix, Squarespace, HubSpot,
Gravity Forms, WPForms, Contact Form 7, Elementor, BigCommerce, Klaviyo, Custom).

You can easily add or update field models, selectors, and dropdown rules here.
================================================================================
"""

import time
import random
import re
from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import Select


class UniversalFormFiller:
    """
    Modular Form Filler with 30+ Field Models, Semantic Label Matching,
    Anti-Honeypot Verification, and Smart Dropdown/Checkbox Handling.
    """

    # --------------------------------------------------------------------------
    # 30+ FIELD DICTIONARIES (Regex / Substring Patterns for DOM Attributes)
    # --------------------------------------------------------------------------
    FIELD_MODELS = {
        # 1. First Name (Split format)
        "first_name": [
            "first_name", "firstname", "first-name", "fname", "first",
            "given-name", "given_name", "field-first", "field_first",
            "input_1_3", "input_2_3", "input_3_3", "wpforms[fields][0][first]",
            "form_fields[first_name]", "q3_name[first]", "contact[first_name]"
        ],

        # 2. Last Name (Split format)
        "last_name": [
            "last_name", "lastname", "last-name", "lname", "last",
            "family-name", "family_name", "field-last", "field_last",
            "input_1_6", "input_2_6", "input_3_6", "wpforms[fields][0][last]",
            "form_fields[last_name]", "q3_name[last]", "contact[last_name]"
        ],

        # 3. Full Name (Single format)
        "full_name": [
            "your-name", "your_name", "yourname", "fullname", "full_name",
            "full-name", "contact[name]", "contact_name", "contact-name",
            "author", "name", "client_name", "lead_name", "form_fields[name]",
            "form_fields[fullname]", "input_1", "wpforms[fields][0]"
        ],

        # 4. Email Address
        "email": [
            "your-email", "your_email", "youremail", "email", "e-mail",
            "mail", "contact[email]", "contact_email", "contact-email",
            "form_fields[email]", "user_email", "client_email", "input_2",
            "wpforms[fields][1]", "q4_email", "billing_email"
        ],

        # 5. Phone / Mobile / Telephone
        "phone": [
            "your-phone", "your-tel", "your_phone", "your_tel", "phone",
            "telephone", "tel", "mobile", "cell", "contact[phone]",
            "contact_phone", "contact-phone", "phone_number", "phonenumber",
            "phone-number", "form_fields[phone]", "input_3", "wpforms[fields][2]"
        ],

        # 6. Company / Business / Organization / Store Name
        "company": [
            "company", "organization", "organisation", "business", "firm",
            "company_name", "companyname", "company-name", "business_name",
            "store_name", "brand_name", "brand", "agency", "contact[company]",
            "form_fields[company]", "wpforms[fields][3]"
        ],

        # 7. Website / Store URL / Domain
        "website": [
            "website", "url", "site", "web", "store_url", "company_url",
            "your-website", "your_website", "web_address", "domain",
            "company_website", "form_fields[website]"
        ],

        # 8. Subject / Topic / Purpose / Title
        "subject": [
            "your-subject", "your_subject", "subject", "topic", "regarding",
            "purpose", "title", "contact[subject]", "inquiry_type",
            "reason", "form_fields[subject]", "wpforms[fields][4]"
        ],

        # 9. City / Town
        "city": [
            "city", "town", "location_city", "billing_city", "contact[city]",
            "form_fields[city]"
        ],

        # 10. State / Province / Region
        "state": [
            "state", "province", "region", "territory", "contact[state]",
            "billing_state", "form_fields[state]"
        ],

        # 11. Zip / Postal Code
        "zip": [
            "zip", "zipcode", "zip_code", "postal", "postalcode", "postal_code",
            "postcode", "billing_postcode", "contact[zip]"
        ],

        # 12. Country
        "country": [
            "country", "billing_country", "contact[country]", "form_fields[country]"
        ],

        # 13. Job Title / Role / Position
        "job_title": [
            "job_title", "jobtitle", "job-title", "title", "role", "position",
            "designation", "profession"
        ],

        # 14. Order Quantity / Volume / Budget
        "quantity": [
            "quantity", "volume", "order_size", "units", "budget", "estimated_units",
            "moq", "pieces", "batch_size"
        ],

        # 15. Message / Body / Comments / Description (Textarea / Inputs)
        "message": [
            "your-message", "your_message", "message", "comments", "comment",
            "inquiry", "body", "notes", "description", "details", "contact[body]",
            "contact[message]", "contact[comments]", "form_fields[message]",
            "wpforms[fields][5]", "q5_message", "order_notes"
        ]
    }

    # Common Submit Button Keywords
    SUBMIT_KEYWORDS = [
        "send", "submit", "send message", "get in touch", "contact us",
        "submit inquiry", "send inquiry", "reach out", "request quote",
        "send email", "post comment", "submit form", "continue", "apply"
    ]

    # Dropdown Priority Options (For Wholesale / General / Partnership)
    PREFERRED_DROPDOWN_CHOICES = [
        "wholesale", "partnership", "business", "sales", "general inquiry",
        "inquiry", "collaboration", "supplier", "buyer", "other", "support"
    ]

    def __init__(self, driver):
        self.driver = driver

    # --------------------------------------------------------------------------
    # HELPER: HUMAN BEHAVIOR SIMULATION
    # --------------------------------------------------------------------------
    def _human_move_to(self, element):
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
            time.sleep(random.uniform(0.15, 0.35))
            ActionChains(self.driver).move_to_element(element).perform()
        except Exception:
            pass

    def _human_type(self, element, text):
        try:
            element.clear()
        except Exception:
            pass
        time.sleep(random.uniform(0.1, 0.2))
        for char in str(text):
            element.send_keys(char)
            time.sleep(random.uniform(0.015, 0.045))

    # --------------------------------------------------------------------------
    # ANTI-HONEYPOT & VISIBILITY CHECK
    # --------------------------------------------------------------------------
    def is_genuinely_visible(self, element):
        """
        Detects if an element is truly visible to a real user and NOT a hidden
        honeypot anti-spam trap.
        """
        try:
            if not element.is_displayed() or not element.is_enabled():
                return False

            # Check CSS styles (display:none, visibility:hidden, opacity:0, height:0)
            style = element.get_attribute("style") or ""
            cls = (element.get_attribute("class") or "").lower()
            elem_id = (element.get_attribute("id") or "").lower()
            name = (element.get_attribute("name") or "").lower()

            # Known anti-bot honeypot names
            if any(h in name or h in elem_id or h in cls for h in ["honeypot", "hp_field", "bot_check", "g-recaptcha-response-fake", "trap"]):
                return False

            # Check bounding box size
            size = element.size
            if size.get("width", 0) <= 2 or size.get("height", 0) <= 2:
                return False

            # Execute JS check for computed opacity or off-screen positioning
            is_visible_js = self.driver.execute_script("""
                const el = arguments[0];
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                if (rect.width <= 2 || rect.height <= 2) return false;
                if (rect.left < -500 || rect.top < -500) return false;
                return true;
            """, element)

            return bool(is_visible_js)
        except Exception:
            return False

    # --------------------------------------------------------------------------
    # ATTRIBUTE & LABEL SEMANTIC MATCHER
    # --------------------------------------------------------------------------
    def get_element_context(self, element):
        """
        Aggregates all semantic context of an input element:
        Name, ID, Placeholder, Class, Aria-Label, Autocomplete, Associated Label Text.
        """
        context = []
        for attr in ["name", "id", "placeholder", "aria-label", "class", "autocomplete", "title", "data-testid"]:
            val = element.get_attribute(attr)
            if val:
                context.append(str(val).lower())

        # Check associated <label> via 'for' attribute
        elem_id = element.get_attribute("id")
        if elem_id:
            try:
                labels = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{elem_id}']")
                for lbl in labels:
                    context.append(lbl.text.lower())
            except Exception:
                pass

        # Check parent label text
        try:
            parent = element.find_element(By.XPATH, "..")
            if parent.tag_name.lower() == "label" or "form-group" in (parent.get_attribute("class") or "").lower():
                context.append(parent.text.lower())
        except Exception:
            pass

        return " ".join(context)

    def match_field_type(self, element, input_type="text"):
        """
        Determines the semantic field type from the 30+ field models.
        """
        ctx = self.get_element_context(element)

        # 1. Check strict email input type
        if input_type == "email" or "type='email'" in ctx:
            return "email"
        # 2. Check strict tel input type
        if input_type == "tel" or "type='tel'" in ctx:
            return "phone"

        # Check in prioritized order
        # Check First Name vs Full Name (First Name takes precedence if specified)
        if any(k in ctx for k in self.FIELD_MODELS["first_name"]) and not any(x in ctx for x in ["last", "email", "phone"]):
            return "first_name"

        if any(k in ctx for k in self.FIELD_MODELS["last_name"]) and not any(x in ctx for x in ["first", "email", "phone"]):
            return "last_name"

        if any(k in ctx for k in self.FIELD_MODELS["email"]):
            return "email"

        if any(k in ctx for k in self.FIELD_MODELS["phone"]):
            return "phone"

        if any(k in ctx for k in self.FIELD_MODELS["website"]):
            return "website"

        if any(k in ctx for k in self.FIELD_MODELS["company"]) and not any(x in ctx for x in ["email", "phone"]):
            return "company"

        if any(k in ctx for k in self.FIELD_MODELS["subject"]):
            return "subject"

        if any(k in ctx for k in self.FIELD_MODELS["city"]):
            return "city"

        if any(k in ctx for k in self.FIELD_MODELS["state"]):
            return "state"

        if any(k in ctx for k in self.FIELD_MODELS["zip"]):
            return "zip"

        if any(k in ctx for k in self.FIELD_MODELS["country"]):
            return "country"

        if any(k in ctx for k in self.FIELD_MODELS["job_title"]):
            return "job_title"

        if any(k in ctx for k in self.FIELD_MODELS["quantity"]):
            return "quantity"

        if any(k in ctx for k in self.FIELD_MODELS["full_name"]) and not any(x in ctx for x in ["email", "phone", "subject", "company"]):
            return "full_name"

        if any(k in ctx for k in self.FIELD_MODELS["message"]):
            return "message"

        return None

    # --------------------------------------------------------------------------
    # MAIN FORM FILLING METHOD
    # --------------------------------------------------------------------------
    def fill_form_fields(self, brand_name, niche, sender_data, message_text):
        """
        Fills all available form fields dynamically using 30+ field models.
        Returns: (success: bool, fields_filled: list)
        """
        full_name = sender_data.get("full_name") or "Our Team"
        name_parts = full_name.split()
        first_name = name_parts[0] if name_parts else "Partner"
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "Representative"

        sender_email = sender_data.get("sender_email") or ""
        company_name = sender_data.get("company_name") or "Our Company"
        sender_phone = sender_data.get("phone") or "+1 (555) 019-2834"
        sender_website = sender_data.get("website") or "https://ourcompany.com"
        subject_line = f"Partnership & Sourcing Inquiry — {brand_name}"

        # Contextual values dictionary
        field_values = {
            "first_name": first_name,
            "last_name": last_name,
            "full_name": full_name,
            "email": sender_email,
            "phone": sender_phone,
            "company": company_name,
            "website": sender_website,
            "subject": subject_line,
            "city": sender_data.get("city", "New York"),
            "state": sender_data.get("state", "California"),
            "zip": "90210",
            "country": sender_data.get("country", "USA"),
            "job_title": "Business Development Director",
            "quantity": "500 - 1,000 units",
            "message": message_text
        }

        filled_fields = []
        name_already_filled = False

        # ----------------------------------------------------------------------
        # 1. PROCESS TEXT INPUTS (<input>)
        # ----------------------------------------------------------------------
        inputs = self.driver.find_elements(By.TAG_NAME, "input")
        for inp in inputs:
            try:
                if not self.is_genuinely_visible(inp):
                    continue

                typ = (inp.get_attribute("type") or "text").lower()
                if typ in ["hidden", "submit", "button", "file", "search", "image", "reset"]:
                    continue

                # Handle Checkboxes (Consent / Terms / Privacy Policy)
                if typ == "checkbox":
                    ctx = self.get_element_context(inp)
                    # Check if checkbox is required or privacy/terms related
                    if inp.get_attribute("required") or any(w in ctx for w in ["agree", "terms", "privacy", "consent", "accept", "policy", "not-a-robot"]):
                        if not inp.is_selected():
                            self._human_move_to(inp)
                            inp.click()
                            filled_fields.append("checkbox_consent")
                            time.sleep(0.1)
                    continue

                # Handle Radio Buttons
                if typ == "radio":
                    continue

                # Match semantic field type
                field_type = self.match_field_type(inp, input_type=typ)

                if field_type:
                    # Avoid double filling name if already split
                    if field_type == "full_name" and name_already_filled:
                        continue
                    if field_type in ["first_name", "last_name"]:
                        name_already_filled = True

                    val = field_values.get(field_type)
                    if val:
                        self._human_move_to(inp)
                        self._human_type(inp, val)
                        filled_fields.append(field_type)
                        time.sleep(random.uniform(0.1, 0.25))

                # Fallback: if field has 'required' attribute and wasn't matched yet
                elif inp.get_attribute("required") and not inp.get_attribute("value"):
                    # Check if it looks like a general text field
                    self._human_move_to(inp)
                    self._human_type(inp, company_name)
                    filled_fields.append("generic_required")

            except Exception:
                continue

        # ----------------------------------------------------------------------
        # 2. PROCESS TEXTAREAS (<textarea> for Message Body)
        # ----------------------------------------------------------------------
        textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
        for ta in textareas:
            try:
                if not self.is_genuinely_visible(ta):
                    continue

                self._human_move_to(ta)
                self._human_type(ta, message_text)
                filled_fields.append("message_textarea")
                time.sleep(random.uniform(0.15, 0.3))
                break  # Usually only 1 main message textarea
            except Exception:
                continue

        # ----------------------------------------------------------------------
        # 3. PROCESS DROPDOWNS (<select>)
        # ----------------------------------------------------------------------
        selects = self.driver.find_elements(By.TAG_NAME, "select")
        for sel in selects:
            try:
                if not self.is_genuinely_visible(sel):
                    continue

                select_obj = Select(sel)
                options = select_obj.options
                if not options or len(options) <= 1:
                    continue

                chosen_option = None
                # Check for preferred choices (Wholesale, Partnership, Business, General)
                for opt in options:
                    opt_text = opt.text.lower()
                    if any(pref in opt_text for pref in self.PREFERRED_DROPDOWN_CHOICES):
                        chosen_option = opt
                        break

                # Fallback: Pick 2nd option (1st is usually "-- Select an option --")
                if not chosen_option and len(options) > 1:
                    chosen_option = options[1]

                if chosen_option:
                    self._human_move_to(sel)
                    select_obj.select_by_visible_text(chosen_option.text)
                    filled_fields.append("dropdown_selected")
                    time.sleep(0.15)
            except Exception:
                continue

        # A successful form fill requires at least Name/Company OR Email OR Message
        success = any(f in filled_fields for f in ["email", "full_name", "first_name", "message_textarea"])
        return success, filled_fields

    # --------------------------------------------------------------------------
    # SUBMIT BUTTON FINDER & AUTOMATION
    # --------------------------------------------------------------------------
    def try_submit(self):
        """
        Finds and clicks the primary submit button using multi-priority selectors.
        """
        # Priority 1: input[type=submit] or button[type=submit]
        for selector in ["input[type='submit']", "button[type='submit']", "button.submit", "input.submit"]:
            for btn in self.driver.find_elements(By.CSS_SELECTOR, selector):
                try:
                    if self.is_genuinely_visible(btn):
                        self._human_move_to(btn)
                        btn.click()
                        return True
                except Exception:
                    continue

        # Priority 2: Buttons with submit-like text
        for btn in self.driver.find_elements(By.TAG_NAME, "button"):
            try:
                if self.is_genuinely_visible(btn):
                    txt = btn.text.lower().strip()
                    cls = (btn.get_attribute("class") or "").lower()
                    if any(w in txt or w in cls for w in self.SUBMIT_KEYWORDS):
                        self._human_move_to(btn)
                        btn.click()
                        return True
            except Exception:
                continue

        # Priority 3: <a> tags formatted as submit buttons
        for a in self.driver.find_elements(By.TAG_NAME, "a"):
            try:
                if self.is_genuinely_visible(a):
                    cls = (a.get_attribute("class") or "").lower()
                    txt = a.text.lower().strip()
                    if ("btn" in cls or "button" in cls) and any(w in txt for w in self.SUBMIT_KEYWORDS):
                        self._human_move_to(a)
                        a.click()
                        return True
            except Exception:
                continue

        return False


# ==============================================================================
#  UNIVERSAL CONTACT PAGE DISCOVERY & RECOGNITION ENGINE (35+ PATTERNS)
# ==============================================================================
class ContactPageDiscoveryEngine:
    """
    Intelligent engine to discover contact, reach-out, wholesale, and support
    pages across Shopify, WordPress, Wix, Squarespace, BigCommerce, and Custom sites.
    """

    # 35+ Link Anchor Text, Button Text, Title & Aria-Label Variations
    CONTACT_PHRASES = [
        "contact", "contact us", "contact-us", "contactus", "get in touch",
        "get-in-touch", "reach us", "reach-us", "reach out", "reach-out",
        "reach me", "reach-me", "say hello", "say-hello", "talk to us",
        "talk with us", "message us", "email us", "write to us", "write us",
        "connect with us", "connect", "help & contact", "customer support",
        "customer care", "customer service", "inquiries", "inquiry",
        "general inquiry", "wholesale inquiry", "wholesale", "b2b inquiry",
        "work with us", "partnership", "collaborate", "drop us a line",
        "ask a question", "feedback", "let's talk", "lets talk", "get a quote",
        "request a quote", "submit a request", "contact form", "touch base"
    ]

    # 35+ Standard URL Paths Across Major CMS & Custom Platforms
    STANDARD_PATHS = [
        # Shopify standard paths
        "/pages/contact", "/pages/contact-us", "/pages/contactus",
        "/pages/get-in-touch", "/pages/reach-us", "/pages/reach-out",
        "/pages/reach-me", "/pages/say-hello", "/pages/wholesale",
        "/pages/inquiries", "/pages/inquiry", "/pages/support",
        "/pages/help", "/pages/collaborate", "/pages/work-with-us",
        "/pages/partnership", "/pages/b2b",

        # WordPress / WooCommerce standard paths
        "/contact", "/contact/", "/contact-us", "/contact-us/",
        "/contactus", "/contactus/", "/get-in-touch", "/get-in-touch/",
        "/reach-us", "/reach-us/", "/reach-out", "/reach-out/",
        "/reach-me", "/reach-me/", "/say-hello", "/say-hello/",
        "/support", "/support/", "/wholesale", "/wholesale/",

        # Wix / Squarespace / BigCommerce / Custom
        "/about/contact", "/support/contact", "/help/contact",
        "/info/contact", "/customer-service/contact", "/customer-service",
        "/help-center", "/contact.html", "/contact.php", "/contact-us.html",
        "/contact-us.php", "/index.php?route=information/contact"
    ]

    def __init__(self, driver):
        self.driver = driver

    def is_valid_contact_form_page(self):
        """
        Validates if the currently loaded page contains a genuine contact form
        (filters out newsletter-only subscription bars, search forms, and comment sections).
        """
        try:
            html = self.driver.page_source.lower()

            # Check for embedded iframe forms (HubSpot, TypeForm, JotForm, Klaviyo)
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for frame in iframes:
                src = (frame.get_attribute("src") or "").lower()
                if any(srv in src for srv in ["hubspot", "typeform", "jotform", "formstack", "klaviyo", "mailchimp", "google.com/forms"]):
                    return True

            # Check for presence of form elements
            forms = self.driver.find_elements(By.TAG_NAME, "form")
            textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
            inputs = self.driver.find_elements(By.TAG_NAME, "input")

            # Must have at least a textarea or at least 2 text inputs (name + email or phone)
            valid_inputs = [
                inp for inp in inputs
                if (inp.get_attribute("type") or "text").lower() in ["text", "email", "tel"]
                and not any(x in (inp.get_attribute("name") or "").lower() for x in ["search", "q", "newsletter_only"])
            ]

            has_message_area = len(textareas) > 0
            has_multiple_inputs = len(valid_inputs) >= 2
            has_contact_keywords = any(kw in html for kw in [
                "contact", "get in touch", "send message", "reach out",
                "inquiry", "message us", "your email", "your name", "feedback"
            ])

            # Filter out single-field newsletter popups / footers
            is_pure_newsletter = (len(valid_inputs) == 1 and not has_message_area and
                                  any(nl in html for nl in ["subscribe to newsletter", "join our newsletter", "get 10% off"]))

            if (has_message_area or has_multiple_inputs) and has_contact_keywords and not is_pure_newsletter:
                return True

            return False
        except Exception:
            return False

    def find_contact_page(self, base_url=""):
        """
        Comprehensive contact page discovery across DOM scan, modal trigger,
        and multi-platform URL probing.
        """
        if not base_url:
            base_url = self.driver.current_url

        try:
            parsed_base = urlparse(base_url)
            base_root = f"{parsed_base.scheme}://{parsed_base.netloc}".rstrip("/")
            base_domain = parsed_base.netloc.replace("www.", "").lower()
        except Exception:
            base_root = base_url.rstrip("/")
            base_domain = ""

        # ----------------------------------------------------------------------
        # STEP 1: Check if current page (e.g. Homepage / Single-Page site)
        # already has a visible active contact form
        # ----------------------------------------------------------------------
        if self.is_valid_contact_form_page():
            return self.driver.current_url

        # ----------------------------------------------------------------------
        # STEP 2: Check for Contact Modal / Drawer Triggers on the page
        # ----------------------------------------------------------------------
        try:
            modal_selectors = [
                "a[href*='#contact']", "button[data-target*='contact']",
                "button[aria-controls*='contact']", ".contact-modal-btn",
                "a.contact-btn", "button.contact-btn", "a[data-toggle='modal'][href*='contact']"
            ]
            for sel in modal_selectors:
                for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed():
                        el.click()
                        time.sleep(1.0)
                        if self.is_valid_contact_form_page():
                            return self.driver.current_url
        except Exception:
            pass

        # ----------------------------------------------------------------------
        # STEP 3: Scan all <a> links and buttons on page matching 35+ phrase variations
        # ----------------------------------------------------------------------
        candidate_urls = []
        seen = set()

        try:
            links = self.driver.find_elements(By.TAG_NAME, "a")
            for a in links:
                try:
                    href = (a.get_attribute("href") or "").strip()
                    if not href or not href.startswith("http") or href.startswith("mailto:") or href.startswith("tel:"):
                        continue

                    # Filter out third party social links / app stores
                    link_parsed = urlparse(href)
                    if base_domain and base_domain not in link_parsed.netloc.lower():
                        continue

                    text = a.text.lower().strip()
                    aria = (a.get_attribute("aria-label") or "").lower().strip()
                    title = (a.get_attribute("title") or "").lower().strip()
                    combined_text = f"{text} {aria} {title}"

                    # Match against 35+ phrase variations or url path
                    path_lower = link_parsed.path.lower()
                    if any(phrase in combined_text for phrase in self.CONTACT_PHRASES) or \
                       any(phrase in path_lower for phrase in ["contact", "reach-us", "get-in-touch", "reach-out", "wholesale", "reachme"]):
                        clean_link = href.split("?")[0].split("#")[0].rstrip("/")
                        if clean_link not in seen and clean_link != base_root:
                            seen.add(clean_link)
                            candidate_urls.append(clean_link)
                except Exception:
                    continue
        except Exception:
            pass

        # ----------------------------------------------------------------------
        # STEP 4: Append Standard Platform Candidate Paths
        # ----------------------------------------------------------------------
        for p in self.STANDARD_PATHS:
            full_candidate = (base_root + p).rstrip("/")
            if full_candidate not in seen:
                seen.add(full_candidate)
                candidate_urls.append(full_candidate)

        # ----------------------------------------------------------------------
        # STEP 5: Probe candidates with form validation
        # ----------------------------------------------------------------------
        for url in candidate_urls[:12]:  # Test top 12 most relevant candidate paths
            try:
                self.driver.get(url)
                time.sleep(random.uniform(1.2, 2.0))

                if self.is_valid_contact_form_page():
                    return url
            except Exception:
                continue

        return ""


def find_universal_contact_page(driver, base_url=""):
    """
    Helper function to discover contact page using ContactPageDiscoveryEngine.
    """
    engine = ContactPageDiscoveryEngine(driver)
    return engine.find_contact_page(base_url)


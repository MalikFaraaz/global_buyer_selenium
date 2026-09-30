# 🌐 Global Buyer Selenium — Autonomous B2B Lead Generator & Outreach Engine

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1-black.svg)](https://palletsprojects.com/p/flask/)
[![Selenium](https://img.shields.io/badge/Selenium-4.41-brightgreen.svg)](https://www.selenium.dev/)
[![Scikit-Learn](https://img.shields.io/badge/Machine%20Learning-Scikit--Learn-orange.svg)](https://scikit-learn.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

**Global Buyer Selenium** is an enterprise-grade, autonomous B2B lead generation, enrichment, and outreach automation platform. It discovers live e-commerce stores across multiple CMS platforms, extracts verified contact information (emails, phone numbers, contact forms, social media, addresses), qualifies buyer quality using Machine Learning & NLP models, and automates customized outreach via intelligent form-filling and personalized email generation.

---

## 🚀 Key Features

### 1. Multi-Platform E-Commerce Discovery
- **Platforms Supported:** Shopify (`myshopify.com`), WordPress / WooCommerce (`wp-content`), Wix (`wixsite.com`), Squarespace, BigCommerce, and Custom / Independent brands.
- **Smart Query Generator:** Dynamically composes precision search queries targeting niche keywords, platforms, and locations.
- **Search Engine Resilience:** Seamless parsing of organic DuckDuckGo search results with automatic rate-limit throttling and exponential backoff.

### 2. Precision Geo-Fencing & State Normalization
- Target by country: **United States, Canada, United Kingdom, Australia, Germany**, etc.
- **Strict State / Province Geofencing:** Normalizes variations (e.g. `California (CA)`, `Calif.`, `CA`), matches phone area codes, ZIP codes, and major cities (`Los Angeles`, `San Francisco`, `San Diego`, etc.), ensuring candidate stores strictly match target locations.

### 3. Selenium Stealth Browser with Live Visual Mode
- **Stealth Automation:** Removes `navigator.webdriver` flags, injects realistic plugins/languages, and randomizes User-Agents to prevent bot detection.
- **Visible Desktop Window:** Windows Win32 API integration hooks child processes to `WinSta0\Default` so Chrome windows physically open and display live on your primary screen monitor.
- **Headless Option:** Toggle between real-time visible desktop browsing and silent Headless Turbo mode in user settings.

### 4. High-Speed Parallel Multi-Workers (P2 Architecture)
- Run **1 to 5 parallel worker threads** concurrently.
- Thread-safe queue architecture (`queue.Queue`, `threading.Lock`) distributes candidate store analysis across workers, accelerating lead discovery and form submissions by up to 5x.

### 5. Persistent State & Tab-Switching Resilience
- **Uninterrupted Background Execution:** Scraping threads run independently on the server. Navigating across tabs, opening other pages, or minimizing the browser will **never** stop or break the scraping process.
- **Auto-Restore Console:** Refreshing or navigating back to the Lead Generation tab immediately restores the ongoing scraper state, progress bar, and up to 100 historical log entries.
- **Interactive STOP Button:** An integrated `🛑 Stop Scraping` controller allows users to safely halt workers at any time while preserving all verified leads collected up to that moment.

### 6. Machine Learning Quality Qualification & NLP Scoring
- Pre-trained ML model (`buyer_model.pkl` + `label_encoder.pkl`) and NLP sentiment/intent analyzer (`ML.py`, `NLP.py`).
- Scores and categorizes leads into **High**, **Medium**, or **Low** priority based on store attributes, brand signals, and verification quality.

### 7. Autonomous Form-Filling Engine
- Inspects store contact pages (`/contact`, `/pages/contact-us`, `/about`, etc.).
- Identifies and auto-fills contact form fields (name, sender email, company name, phone, personalized pitch message).
- Built-in heuristic solver for basic math and honeypot captchas (`captcha_solver.py`).

### 8. Enterprise Web Dashboard & Lead Management
- **Role-Based Access Control:** Admin & Standard User roles with secure password hashing (`werkzeug.security`).
- **Live Terminal Window:** Terminal-style console with real-time log streaming.
- **Analytics & Visualizations:** Geographic distribution maps, top category bar charts, and historical trends.
- **Data Export:** Instant one-click export of verified leads to CSV/Excel with filtering by user or role.
- **Customizable Message Templates:** Create, edit, and organize B2B outreach message templates with dynamic placeholders (`{brand}`, `{niche}`, `{sender_name}`, `{company_name}`).

---

## 📁 Repository Structure

```
global_buyer_selenium/
├── app.py                      # Flask Application entry point, auth & API routes
├── shopify_leads.py            # Core scraping engine, parallel workers & Selenium controller
├── form_filler_engine.py       # Autonomous contact form detector and submission engine
├── proxy_manager.py            # Proxy pool rotator & HTTP/SOCKS proxy manager
├── captcha_solver.py           # Captcha detection & heuristic solver
├── ai_personalizer.py          # AI message generator with personalized pitch copy
├── ML.py                       # Machine Learning training & evaluation pipeline
├── NLP.py                      # Natural Language Processing text feature extractor
├── init_sqlite.py              # SQLite database schema initializer
├── database.db                 # SQLite database storing users, buyers & settings
├── requirements.txt            # Python package dependencies
├── .gitignore                  # Git ignore rules for environments & cache
├── static/                     # CSS stylesheets, UI icons, and frontend assets
│   ├── css/
│   │   ├── style.css
│   │   ├── admin_dashboard.css
│   │   └── user_dashboard.css
│   └── images/
├── templates/                  # Jinja2 HTML templates
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── admin_dashboard.html
│   ├── user_dashboard.html
│   ├── generate_leads.html     # Lead generation form & Live Scraping Console
│   ├── export_leads.html       # Lead table viewer & CSV exporter
│   ├── export_history.html     # Historical scraping audit log
│   ├── settings.html           # Profile, template & proxy configuration
│   └── edit_user.html          # User administration interface
├── buyer_model.pkl             # Serialized Scikit-Learn classification model
└── label_encoder.pkl           # Label encoder for lead category prediction
```

---

## 🛠️ Installation & Setup

### Prerequisites
1. **Python 3.9+** installed and added to `PATH`.
2. **Google Chrome** browser installed (64-bit).
3. **Git** installed on your operating system.

### Step 1: Clone the Repository
```bash
git clone https://github.com/MalikFaraaz/global_buyer_selenium.git
cd global_buyer_selenium
```

### Step 2: Create and Activate Virtual Environment
- **Windows (Command Prompt / PowerShell):**
  ```powershell
  python -m venv .venv
  .venv\Scripts\activate
  ```
- **macOS / Linux:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

### Step 3: Install Required Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Run the Application
```bash
python app.py
```

### Step 5: Access the Dashboard
Open your browser and navigate to:
```
http://127.0.0.1:5000
```
- **Default Admin Account:** `admin` / `admin123` (or register a new user).

---

## 🎯 How to Use

1. **Log in** to your account.
2. Navigate to **Lead Generation** (`/generate_leads`).
3. Set your target parameters:
   - **Target Keyword / Niche:** e.g., `jackets`, `organic skincare`, `jewelry`.
   - **Country:** Select from dropdown (e.g., `United States`, `United Kingdom`, `Canada`).
   - **State / Province:** Select target region or choose `All Regions / Nationwide`.
   - **CMS Platforms:** Check target platforms (Shopify, WordPress, Wix, Squarespace, BigCommerce, Custom).
   - **Max Leads:** Number of verified stores to collect.
   - **Live Browser Window:** Keep checked to observe Chrome browsing in real time.
   - **Parallel Scraper Workers:** Choose speed level (1 to 5 workers).
4. Click **🚀 Start Targeted Scraping**.
5. Watch the **Live Scraping Console** stream real-time store discoveries, contact extractions, and verification scores.
6. Click **🛑 Stop Scraping** at any time if you wish to pause — all leads captured up to that point are permanently stored.
7. Export your verified buyers anytime from **Export Leads** (`/export_leads`) as a structured CSV or Excel file.

---

## 🔒 Security & Best Practices
- **Thread Safety:** Database transactions use SQLite WAL mode with serialized access lock for background workers.
- **Isolated User Profiles:** Each Chrome instance runs in a freshly isolated temporary user profile directory to prevent profile lock conflicts.
- **Proxy Support:** Rotating proxies can be configured under Settings to distribute request volume across unique IPs.

---

## 📄 License
This software is developed and distributed under proprietary commercial licensing. All rights reserved.

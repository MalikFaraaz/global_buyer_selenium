import sys
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except:
    pass

from flask import Flask, render_template, request, redirect, flash, url_for, jsonify, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3
import threading
import io
import csv
import re

import os
import sys

from shopify_leads import scrape, SCRAPER_STATUS, patch_winapi_for_default_desktop, stop_scraper_for_user
patch_winapi_for_default_desktop()

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

if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)

app.secret_key = 'super_secret_key_change_in_production' 

# Setup Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

def get_db_connection():
    return sqlite3.connect(get_db_path())

class User(UserMixin):
    def __init__(self, id, username, role, is_blocked, show_browser=1):
        self.id = str(id)
        self.username = username
        self.role = role
        self.is_blocked = is_blocked
        self.show_browser = int(show_browser) if show_browser is not None else 1

@login_manager.user_loader
def load_user(user_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role, is_blocked, COALESCE(show_browser, 1) FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return User(row[0], row[1], row[2], row[3], row[4])
    except Exception as e:
        print(f"Error loading user: {e}")
    finally:
        if conn:
            conn.close()
    return None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash("Administrator login required to access this area.", "error")
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ================= AUTH ROUTES =================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, password_hash, role, is_blocked, COALESCE(show_browser, 1) FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            
            if row and check_password_hash(row[2], password):
                if row[4] == 1:
                    flash("Your account has been blocked.", "error")
                    return redirect(url_for('login'))
                
                user = User(row[0], row[1], row[3], row[4], row[5])
                login_user(user)
                if user.role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('user_dashboard'))
            else:
                flash("Invalid username or password.", "error")
        except Exception as e:
            flash(f"Database error: {str(e)}", "error")
        finally:
            if conn:
                conn.close()
                
    return render_template('login.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, password_hash, role, is_blocked, COALESCE(show_browser, 1) FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            
            if row and check_password_hash(row[2], password):
                if row[4] == 1:
                    flash("Admin account is blocked.", "error")
                    return redirect(url_for('admin_login'))
                if row[3] != 'admin':
                    flash("Access Denied: You do not have administrator permissions.", "error")
                    return redirect(url_for('admin_login'))
                
                user = User(row[0], row[1], row[3], row[4], row[5])
                login_user(user)
                return redirect(url_for('admin_dashboard'))
            else:
                flash("Invalid admin credentials.", "error")
        except Exception as e:
            flash(f"Database error: {str(e)}", "error")
        finally:
            if conn:
                conn.close()

    return render_template('admin_login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('Email')
        password = request.form.get('password')
        
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                flash("Username already exists.", "error")
            else:
                hashed_pw = generate_password_hash(password)
                cursor.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'user')", 
                               (username, email, hashed_pw))
                conn.commit()
                flash("Registration successful. Please log in.", "success")
                return redirect(url_for('login'))
        except Exception as e:
            flash(f"Database error: {str(e)}", "error")
        finally:
            if conn:
                conn.close()
    return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ================= ADMIN ROUTES =================
@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, is_blocked, created_at FROM users ORDER BY created_at DESC")
    users = cursor.fetchall()
    conn.close()
    return render_template('admin_users.html', users=users)

@app.route('/admin/toggle_block/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_block(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if str(user_id) == str(current_user.id):
        flash("You cannot block yourself.", "error")
        conn.close()
        return redirect(url_for('admin_users'))
    cursor.execute("SELECT is_blocked FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        new_status = 0 if row[0] == 1 else 1
        cursor.execute("UPDATE users SET is_blocked = ? WHERE id = ?", (new_status, user_id))
        conn.commit()
        flash("User status updated.", "success")
    conn.close()
    return redirect(url_for('admin_users'))

@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        new_username = request.form.get('username', '').strip()
        new_email    = request.form.get('email', '').strip()
        new_password = request.form.get('password', '').strip()

        # Check username not taken by another user
        cursor.execute("SELECT id FROM users WHERE username = ? AND id != ?", (new_username, user_id))
        if cursor.fetchone():
            flash("Username already taken by another user.", "error")
            conn.close()
            return redirect(url_for('edit_user', user_id=user_id))

        if new_password:
            hashed = generate_password_hash(new_password)
            cursor.execute(
                "UPDATE users SET username=?, email=?, password_hash=? WHERE id=?",
                (new_username, new_email, hashed, user_id)
            )
        else:
            cursor.execute(
                "UPDATE users SET username=?, email=? WHERE id=?",
                (new_username, new_email, user_id)
            )
        conn.commit()
        flash(f"User '{new_username}' updated successfully!", "success")
        conn.close()
        return redirect(url_for('admin_users'))

    # GET: load user data
    cursor.execute("SELECT id, username, email, role FROM users WHERE id = ?", (user_id,))
    user_row = cursor.fetchone()
    conn.close()

    if not user_row:
        flash("User not found.", "error")
        return redirect(url_for('admin_users'))

    return render_template('edit_user.html', edit_user=user_row)

# ================= DASHBOARDS =================
@app.route("/")
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('user_dashboard'))

@app.route("/admin/dashboard")
@login_required
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM buyers")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM buyers WHERE created_at >= datetime('now', '-1 day')")
    new_leads = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM buyers WHERE lead_category='High'")
    verified_buyers = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM buyers WHERE is_relevant=1 AND email IS NOT NULL")
    leads_to_export = cursor.fetchone()[0]

    cursor.execute("SELECT country, COUNT(*) FROM buyers WHERE country IS NOT NULL AND country != '' GROUP BY country ORDER BY COUNT(*) DESC LIMIT 5")
    regions_raw = cursor.fetchall()
    regions = {row[0].upper(): row[1] for row in regions_raw} if regions_raw else {}
    
    cursor.execute("SELECT niche, COUNT(*) FROM buyers WHERE niche IS NOT NULL AND niche != '' GROUP BY niche ORDER BY COUNT(*) DESC LIMIT 5")
    niches_raw = cursor.fetchall()
    top_categories = {row[0]: row[1] for row in niches_raw} if niches_raw else {}

    cursor.execute("""
        SELECT b.brand_name, b.niche, b.email, b.lead_category, b.is_relevant, u.username, b.country, b.state, b.platform, b.website, b.status, b.phone, b.address
        FROM buyers b
        LEFT JOIN users u ON b.generated_by = u.id
        ORDER BY b.buyer_id DESC LIMIT 100
    """)
    recent_buyers = cursor.fetchall()

    # Fetch all registered users with their profile info
    cursor.execute("SELECT id, username, email, full_name, company_name, sender_email, role, is_blocked FROM users ORDER BY created_at DESC")
    all_users = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_leads=total, new_leads_today=new_leads, verified_buyers=verified_buyers,
        leads_to_export=leads_to_export, regions=regions, top_categories=top_categories,
        buyers=recent_buyers, all_users=all_users
    )

@app.route("/user/dashboard")
@login_required
def user_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Total Stats for current user
    cursor.execute("SELECT COUNT(*) FROM buyers WHERE generated_by=?", (current_user.id,))
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM buyers WHERE generated_by=? AND created_at >= datetime('now', '-1 day')", (current_user.id,))
    new_leads = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM buyers WHERE generated_by=? AND lead_category='High'", (current_user.id,))
    verified_buyers = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM buyers WHERE generated_by=? AND is_relevant=1 AND email IS NOT NULL", (current_user.id,))
    leads_to_export = cursor.fetchone()[0]

    # 2. Charts Data for current user
    cursor.execute("SELECT country, COUNT(*) FROM buyers WHERE generated_by=? AND country IS NOT NULL AND country != '' GROUP BY country ORDER BY COUNT(*) DESC LIMIT 5", (current_user.id,))
    regions_raw = cursor.fetchall()
    regions = {row[0].upper(): row[1] for row in regions_raw} if regions_raw else {}
    
    cursor.execute("SELECT niche, COUNT(*) FROM buyers WHERE generated_by=? AND niche IS NOT NULL AND niche != '' GROUP BY niche ORDER BY COUNT(*) DESC LIMIT 5", (current_user.id,))
    niches_raw = cursor.fetchall()
    top_categories = {row[0]: row[1] for row in niches_raw} if niches_raw else {}

    # 3. Recent Leads for current user
    cursor.execute("""
        SELECT brand_name, niche, email, lead_category, is_relevant, status, country, state, platform, website, phone, address
        FROM buyers
        WHERE generated_by=?
        ORDER BY buyer_id DESC LIMIT 100
    """, (current_user.id,))
    recent_buyers = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        "user_dashboard.html",
        total_leads=total, new_leads_today=new_leads, verified_buyers=verified_buyers,
        leads_to_export=leads_to_export, regions=regions, top_categories=top_categories,
        buyers=recent_buyers
    )

# ================= SCRAPER & EXPORT =================
@app.route("/generate_leads", methods=["GET"])
@login_required
def generate_leads():
    return render_template("generate_leads.html")

@app.route("/api/start_scraper", methods=["POST"])
@login_required
def api_start_scraper():
    user_id = current_user.id
    current_status = SCRAPER_STATUS.get(user_id, {}).get("status")
    if current_status in ["running", "starting"]:
        return jsonify({
            "success": False,
            "message": "Scraper is already actively running in the background! Use the Stop button if you wish to halt it.",
            "already_running": True
        }), 400

    keyword = request.form.get("keyword", "").strip()
    country = request.form.get("country", "USA").strip()
    state   = request.form.get("state", "").strip()
    
    country = re.sub(r'\(.*?\)', '', country).strip() or "USA"
    state   = re.sub(r'\(.*?\)', '', state).strip()
    
    # Handle multi-select platforms
    platforms = request.form.getlist("platforms")
    if not platforms and request.form.get("platforms"):
        platforms = [p.strip() for p in request.form.get("platforms").split(",") if p.strip()]
    if not platforms:
        platforms = ["Shopify", "WordPress", "Custom"]
        
    strict_state = request.form.get("strict_state") in ["true", "1", "on", True]

    try:
        max_leads = int(request.form.get("max_leads", 50))
    except ValueError:
        max_leads = 50
    user_id = current_user.id
    
    show_browser_val = request.form.get("show_browser")
    if show_browser_val is not None:
        show_browser = str(show_browser_val).strip() in ["1", "true", "on", "True"]
    else:
        show_browser = True

    try:
        num_workers = int(request.form.get("num_workers", 2))
        num_workers = max(1, min(num_workers, 5))
    except (ValueError, TypeError):
        num_workers = 2

    print(f">> [API start_scraper] keyword='{keyword}', country='{country}', state='{state}', show_browser={show_browser}, workers={num_workers}")

    # Ensure desktop attachment is active for new threads
    patch_winapi_for_default_desktop()

    # Run in background
    thread = threading.Thread(
        target=scrape,
        args=(keyword, country, state, platforms, strict_state, max_leads, user_id, show_browser, num_workers)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True, "message": f"Scraper started with {num_workers} parallel workers"})

@app.route("/api/stop_scraper", methods=["POST"])
@login_required
def api_stop_scraper():
    user_id = current_user.id
    stopped = stop_scraper_for_user(user_id)
    return jsonify({"success": True, "message": "Scraper stop signal transmitted.", "stopped": stopped})

@app.route("/api/scraper_status", methods=["GET"])
@login_required
def api_scraper_status():
    user_id = current_user.id
    status = SCRAPER_STATUS.get(user_id, {"status": "idle", "progress": 0, "total": 0, "message": "Ready to start", "logs": []})
    return jsonify(status)

@app.route("/export_leads", methods=["GET", "POST"])
@login_required
def export_leads():
    conn = get_db_connection()
    cursor = conn.cursor()
    if current_user.role == 'admin':
        cursor.execute("""
            SELECT brand_name, email, phone, address, website, social_links, niche, country, state, platform, lead_category, status, contact_page
            FROM buyers ORDER BY buyer_id DESC
        """)
    else:
        cursor.execute("""
            SELECT brand_name, email, phone, address, website, social_links, niche, country, state, platform, lead_category, status, contact_page
            FROM buyers WHERE generated_by = ? ORDER BY buyer_id DESC
        """, (current_user.id,))
    rows = cursor.fetchall()
    
    cursor.execute("INSERT INTO export_logs (user_id, username, total_leads) VALUES (?, ?, ?)", 
                   (current_user.id, current_user.username, len(rows)))
    conn.commit()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Brand Name', 'Business Email', 'Phone Number', 'Physical Address / Location', 'Website URL', 
        'Social Profiles', 'Niche / Category', 'Country', 'State / Region', 
        'CMS Platform', 'Lead Quality', 'Contact Status', 'Contact Page URL'
    ])
    for r in rows:
        writer.writerow(r)
        
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=verified_buyer_leads.csv"
    return response

@app.route("/export_history", methods=["GET"])
@login_required
def export_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    if current_user.role == 'admin':
        cursor.execute("SELECT * FROM export_logs ORDER BY export_date DESC")
        export_logs = cursor.fetchall()
        cursor.execute("SELECT * FROM scraping_logs ORDER BY created_at DESC")
        scraping_logs = cursor.fetchall()
    else:
        cursor.execute("SELECT * FROM export_logs WHERE user_id = ? ORDER BY export_date DESC", (current_user.id,))
        export_logs = cursor.fetchall()
        cursor.execute("SELECT * FROM scraping_logs WHERE user_id = ? ORDER BY created_at DESC", (current_user.id,))
        scraping_logs = cursor.fetchall()
    conn.close()
    return render_template("export_history.html", export_logs=export_logs, scraping_logs=scraping_logs)


# ================= USER SETTINGS =================
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        full_name        = request.form.get("full_name", "").strip()
        sender_email     = request.form.get("sender_email", "").strip()
        company_name     = request.form.get("company_name", "").strip()
        show_browser     = 1 if request.form.get("show_browser") in ["1", "true", "on", True] else 0
        ai_enabled       = 1 if request.form.get("ai_enabled") in ["1", "true", "on", True] else 0
        gemini_api_key   = request.form.get("gemini_api_key", "").strip()
        ai_tone          = request.form.get("ai_tone", "b2b_wholesale").strip()
        ai_custom_prompt = request.form.get("ai_custom_prompt", "").strip()

        proxy_enabled    = 1 if request.form.get("proxy_enabled") in ["1", "true", "on", True] else 0
        proxy_list       = request.form.get("proxy_list", "").strip()

        cursor.execute("""
            UPDATE users 
            SET full_name=?, sender_email=?, company_name=?, show_browser=?,
                ai_enabled=?, gemini_api_key=?, ai_tone=?, ai_custom_prompt=?,
                proxy_enabled=?, proxy_list=?
            WHERE id=?
        """, (full_name, sender_email, company_name, show_browser, ai_enabled, gemini_api_key, ai_tone, ai_custom_prompt, proxy_enabled, proxy_list, current_user.id))
        conn.commit()
        flash("Settings, AI Outreach & Proxy Configuration saved!", "success")
        conn.close()
        return redirect(url_for('settings'))

    # GET: load profile
    cursor.execute(
        "SELECT full_name, sender_email, company_name, COALESCE(show_browser, 1), gemini_api_key, COALESCE(ai_enabled, 0), ai_tone, ai_custom_prompt, COALESCE(proxy_enabled, 0), COALESCE(proxy_list, '') FROM users WHERE id = ?",
        (current_user.id,)
    )
    row = cursor.fetchone()

    # Load all templates for this user
    cursor.execute(
        "SELECT id, name, template_text FROM message_templates WHERE user_id = ? ORDER BY id",
        (current_user.id,)
    )
    templates = cursor.fetchall()
    conn.close()

    user_settings = {
        "full_name":        row[0] if row else "",
        "sender_email":     row[1] if row else "",
        "company_name":     row[2] if row else "",
        "show_browser":     row[3] if row and row[3] is not None else 1,
        "gemini_api_key":   row[4] if row else "",
        "ai_enabled":       row[5] if row and row[5] is not None else 0,
        "ai_tone":          row[6] if row and row[6] else "b2b_wholesale",
        "ai_custom_prompt": row[7] if row else "",
        "proxy_enabled":    row[8] if row and row[8] is not None else 0,
        "proxy_list":       row[9] if row else "",
    }
    return render_template("settings.html", user_settings=user_settings, templates=templates)

@app.route("/api/test_ai_prompt", methods=["POST"])
@login_required
def api_test_ai_prompt():
    from ai_personalizer import generate_ai_personalized_message
    api_key          = request.form.get("api_key", "").strip()
    sender_name      = request.form.get("sender_name", "Alex Hunter").strip()
    company_name     = request.form.get("company_name", "Global Supply Co.").strip()
    tone             = request.form.get("tone", "b2b_wholesale").strip()
    custom_prompt    = request.form.get("custom_prompt", "").strip()
    sample_brand     = request.form.get("sample_brand", "Urban Luxe Apparel").strip()
    sample_niche     = request.form.get("sample_niche", "Streetwear & Premium Caps").strip()
    sample_context   = request.form.get("sample_context", "Eco-friendly heavyweight hoodies and organic cotton 6-panel caps with minimalist embroidery").strip()

    if not api_key:
        return jsonify({"success": False, "error": "Please enter your Gemini API Key."})

    success, message = generate_ai_personalized_message(
        brand=sample_brand,
        niche=sample_niche,
        context=sample_context,
        sender_name=sender_name,
        company_name=company_name,
        api_key=api_key,
        tone=tone,
        custom_instructions=custom_prompt
    )

    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "error": message})


@app.route("/settings/templates/add", methods=["POST"])
@login_required
def add_template():
    name          = request.form.get("template_name", "").strip()
    template_text = request.form.get("template_text", "").strip()
    if not name or not template_text:
        flash("Template name and text are required.", "error")
        return redirect(url_for('settings'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO message_templates (user_id, name, template_text) VALUES (?, ?, ?)",
        (current_user.id, name, template_text)
    )
    conn.commit()
    conn.close()
    flash(f"Template '{name}' added!", "success")
    return redirect(url_for('settings'))


@app.route("/settings/templates/delete/<int:template_id>", methods=["POST"])
@login_required
def delete_template(template_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM message_templates WHERE id = ? AND user_id = ?",
        (template_id, current_user.id)
    )
    conn.commit()
    conn.close()
    flash("Template deleted.", "success")
    return redirect(url_for('settings'))


@app.route("/settings/templates/edit/<int:template_id>", methods=["POST"])
@login_required
def edit_template(template_id):
    name          = request.form.get("template_name", "").strip()
    template_text = request.form.get("template_text", "").strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE message_templates SET name=?, template_text=? WHERE id=? AND user_id=?",
        (name, template_text, template_id, current_user.id)
    )
    conn.commit()
    conn.close()
    flash(f"Template '{name}' updated!", "success")
    return redirect(url_for('settings'))


if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        import webbrowser
        def open_browser():
            import time
            time.sleep(1.5)
            webbrowser.open("http://127.0.0.1:5000")
        threading.Thread(target=open_browser, daemon=True).start()
        print("\n" + "="*60)
        print("  Global Buyer Selenium Lead Generator Started!")
        print("  Access Dashboard: http://127.0.0.1:5000")
        print("  (Opening default web browser automatically...)")
        print("  Press CTRL+C in this console to exit.")
        print("="*60 + "\n")
        app.run(host="127.0.0.1", port=5000, debug=False)
    else:
        app.run(debug=True)

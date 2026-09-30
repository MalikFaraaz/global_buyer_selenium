import sqlite3
from werkzeug.security import generate_password_hash

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Create Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            full_name TEXT DEFAULT '',
            company_name TEXT DEFAULT '',
            sender_email TEXT DEFAULT '',
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            is_blocked INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create Buyers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS buyers (
            buyer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_name TEXT,
            email TEXT,
            website TEXT,
            niche TEXT,
            contact_page TEXT,
            source_url TEXT,
            status TEXT,
            is_relevant INTEGER DEFAULT 0,
            lead_category TEXT DEFAULT 'Low',
            country TEXT DEFAULT 'USA',
            platform TEXT DEFAULT 'Shopify',
            phone TEXT DEFAULT '',
            address TEXT DEFAULT '',
            social_links TEXT DEFAULT '',
            generated_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create Export Logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS export_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            export_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_leads INTEGER DEFAULT 0
        )
    ''')

    # Create Scraping Logs table (Activity History)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scraping_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            keyword TEXT,
            country TEXT,
            state TEXT,
            platforms TEXT,
            leads_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create Message Templates table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            template_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Run auto-migrations for existing database
    existing_cols = [row[1] for row in cursor.execute("PRAGMA table_info(buyers)").fetchall()]
    if 'state' not in existing_cols:
        cursor.execute("ALTER TABLE buyers ADD COLUMN state TEXT DEFAULT ''")
    if 'platform' not in existing_cols:
        cursor.execute("ALTER TABLE buyers ADD COLUMN platform TEXT DEFAULT 'Shopify'")
    if 'country' not in existing_cols:
        cursor.execute("ALTER TABLE buyers ADD COLUMN country TEXT DEFAULT 'USA'")
    if 'phone' not in existing_cols:
        cursor.execute("ALTER TABLE buyers ADD COLUMN phone TEXT DEFAULT ''")
    if 'address' not in existing_cols:
        cursor.execute("ALTER TABLE buyers ADD COLUMN address TEXT DEFAULT ''")
    if 'social_links' not in existing_cols:
        cursor.execute("ALTER TABLE buyers ADD COLUMN social_links TEXT DEFAULT ''")
    if 'generated_by' not in existing_cols:
        cursor.execute("ALTER TABLE buyers ADD COLUMN generated_by INTEGER")

    existing_user_cols = [row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()]
    if 'show_browser' not in existing_user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN show_browser INTEGER DEFAULT 1")
    if 'gemini_api_key' not in existing_user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN gemini_api_key TEXT DEFAULT ''")
    if 'ai_enabled' not in existing_user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN ai_enabled INTEGER DEFAULT 0")
    if 'ai_tone' not in existing_user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN ai_tone TEXT DEFAULT 'b2b_wholesale'")
    if 'ai_custom_prompt' not in existing_user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN ai_custom_prompt TEXT DEFAULT ''")
    if 'proxy_enabled' not in existing_user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN proxy_enabled INTEGER DEFAULT 0")
    if 'proxy_list' not in existing_user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN proxy_list TEXT DEFAULT ''")
    
    # Clean up any dummy buyers
    cursor.execute("DELETE FROM buyers WHERE brand_name LIKE '%Dummy%' OR email LIKE '%dummy%'")

    # Check if admin exists
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        admin_pw = generate_password_hash("admin123")
        cursor.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)", 
                       ("admin", "admin@admin.com", admin_pw, "admin"))
        print("Default admin created (admin / admin123)")
    
    # Check if user exists
    cursor.execute("SELECT id FROM users WHERE username = 'user'")
    if not cursor.fetchone():
        user_pw = generate_password_hash("user123")
        cursor.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)", 
                       ("user", "user@user.com", user_pw, "user"))
        print("Default user created (user / user123)")

    conn.commit()
    conn.close()
    print("Database initialized successfully without dummy data.")

if __name__ == '__main__':
    init_db()

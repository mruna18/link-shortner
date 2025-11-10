import sqlite3

def update_database_schema():
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    
    print("🔄 Updating database schema for guest support...")
    
    # Check if columns exist and add them if they don't
    columns_to_add = [
        ('is_guest', 'BOOLEAN DEFAULT 0'),
        ('guest_token', 'TEXT'),
        ('expires_at', 'TIMESTAMP')
    ]
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(shortened_urls)")
    existing_columns = [column[1] for column in cursor.fetchall()]
    
    for column_name, column_type in columns_to_add:
        if column_name not in existing_columns:
            try:
                cursor.execute(f'ALTER TABLE shortened_urls ADD COLUMN {column_name} {column_type}')
                print(f"✅ Added column: {column_name}")
            except sqlite3.OperationalError as e:
                print(f"❌ Error adding {column_name}: {e}")
        else:
            print(f"✅ Column already exists: {column_name}")
    
    # Create users table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create a default admin user for testing
    try:
        import hashlib
        default_password = "admin123"
        password_hash = hashlib.sha256(default_password.encode()).hexdigest()
        
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
        ''', ('admin', 'admin@urlshortener.com', password_hash))
        
        print("✅ Created default admin user: admin / admin123")
    except sqlite3.IntegrityError:
        print("✅ Default user already exists")
    
    conn.commit()
    conn.close()
    print("🎉 Database schema update complete!")

if __name__ == "__main__":
    update_database_schema()
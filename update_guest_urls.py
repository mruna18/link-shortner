import sqlite3

def update_database_for_guests():
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    
    print("🔄 Updating database for guest URLs...")
    
    try:
        # Add guest_token and expires_at columns
        cursor.execute('ALTER TABLE shortened_urls ADD COLUMN guest_token TEXT')
        cursor.execute('ALTER TABLE shortened_urls ADD COLUMN expires_at TIMESTAMP')
        cursor.execute('ALTER TABLE shortened_urls ADD COLUMN is_guest BOOLEAN DEFAULT 0')
        print("✅ Added guest support columns")
    except sqlite3.OperationalError:
        print("✅ Guest columns already exist")
    
    conn.commit()
    conn.close()
    print("🎉 Database update complete!")

if __name__ == "__main__":
    update_database_for_guests()
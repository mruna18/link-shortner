import sqlite3
import pandas as pd

def visualize_data():
    conn = sqlite3.connect('urls.db')
    
    # Read data into pandas DataFrame
    df = pd.read_sql_query('''
        SELECT id, short_code, custom_name, click_count, created_at,
               substr(long_url, 1, 30) as short_url
        FROM shortened_urls
    ''', conn)
    
    print("📊 YOUR URL DATA IN A PRETTY TABLE:")
    print("=" * 80)
    print(df.to_string(index=False))
    
    conn.close()

if __name__ == "__main__":
    visualize_data()
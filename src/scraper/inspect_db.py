import os
import sys
from datetime import datetime

# Add the parent directory to sys.path to allow absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import DatabaseManager

def inspect_database():
    db = DatabaseManager()
    
    print("="*60)
    print("DEB's Health Navigator — Database Inspection")
    print(f"Time: {datetime.now()}")
    print("="*60)
    
    tables = [
        "diseases",
        "outbreaks",
        "trends",
        "scraper_logs",
        "education_resources"
    ]
    
    for table in tables:
        try:
            count_query = f"SELECT COUNT(*) FROM {table};"
            count = db.execute_query(count_query, fetch=True)[0]
            print(f"\n[Table: {table}]")
            print(f"Total Records: {count}")
            
            if count > 0:
                # Fetch last 5 records
                sample_query = f"SELECT * FROM {table} ORDER BY id DESC LIMIT 5;"
                # Note: We need to handle tables without 'id' if any, but most of them have it.
                # Let's use a simpler way to see column names and values
                conn = db.get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute(sample_query)
                        cols = [desc[0] for desc in cur.description]
                        rows = cur.fetchall()
                        
                        print("-" * 20)
                        print(f"Latest 5 records (Columns: {', '.join(cols[:5])}...)")
                        for row in rows:
                            # Display a snippet of the record
                            snippet = ", ".join([str(val)[:30] for val in row[:5]])
                            print(f"- {snippet}...")
                finally:
                    db.put_connection(conn)
            else:
                print("No data found in this table.")
                
        except Exception as e:
            print(f"Error inspecting table {table}: {e}")

    print("\n" + "="*60)
    print("Inspection Complete.")
    print("="*60)

if __name__ == "__main__":
    inspect_database()

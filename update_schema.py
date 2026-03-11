import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def update_schema():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Add show_date column to movies table
        print("Adding show_date column to movies table...")
        cur.execute("ALTER TABLE movies ADD COLUMN IF NOT EXISTS show_date DATE;")
        
        # Also ensure screens_count is an integer in theaters
        print("Checking theaters table...")
        cur.execute("ALTER TABLE theaters ALTER COLUMN screens_count TYPE INTEGER;")
        
        conn.commit()
        print("Schema updated successfully!")
    except Exception as e:
        print(f"Error updating schema: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    update_schema()

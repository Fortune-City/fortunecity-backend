import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def update_schema():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Drop show_date and add start_date, end_date
        print("Modifying movies table for date ranges...")
        cur.execute("ALTER TABLE movies DROP COLUMN IF EXISTS show_date;")
        cur.execute("ALTER TABLE movies ADD COLUMN IF NOT EXISTS start_date DATE;")
        cur.execute("ALTER TABLE movies ADD COLUMN IF NOT EXISTS end_date DATE;")
        
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

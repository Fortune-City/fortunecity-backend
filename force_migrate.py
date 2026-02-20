import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def migrate():
    url = os.getenv("DATABASE_URL")
    # Convert sqlalchemy url to psycopg2 if needed, but usually postgresql:// works
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    
    columns_to_add = [
        ("start_date", "VARCHAR"),
        ("end_date", "VARCHAR"),
        ("featured_image", "VARCHAR"),
        ("featured_image_public_id", "VARCHAR")
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            print(f"Executing: ALTER TABLE events ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            cur.execute(f"ALTER TABLE events ADD COLUMN IF NOT EXISTS {col_name} {col_type};")
            print(f"Success for {col_name}")
        except Exception as e:
            print(f"Error for {col_name}: {e}")
            conn.rollback()
            continue
    
    conn.commit()
    cur.close()
    conn.close()
    print("Migration finished.")

if __name__ == "__main__":
    migrate()

import psycopg2
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def check_schema():
    if not DATABASE_URL:
        print("DATABASE_URL not found")
        return

    result = urlparse(DATABASE_URL)
    username = result.username
    password = result.password
    database = result.path[1:]
    hostname = result.hostname
    port = result.port or 5432

    try:
        conn = psycopg2.connect(
            database=database,
            user=username,
            password=password,
            host=hostname,
            port=port
        )
        cur = conn.cursor()
        
        # List all tables
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        tables = cur.fetchall()
        print("Tables in 'public' schema:")
        for t in tables:
            print(f"- {t[0]}")
            
        # List columns for 'events'
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'events'")
        columns = cur.fetchall()
        print(f"\nColumns in 'events' table:")
        if not columns:
            print("No columns found (check case sensitivity or table existence)")
        for col in columns:
            print(f"- {col[0]} ({col[1]})")
            
        # Try a simple SELECT
        print("\nTesting SELECT * FROM events LIMIT 1...")
        try:
            cur.execute("SELECT * FROM events LIMIT 1")
            row = cur.fetchone()
            print(f"Success! Row found: {row}")
        except Exception as query_err:
            print(f"Query Error: {query_err}")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_schema()

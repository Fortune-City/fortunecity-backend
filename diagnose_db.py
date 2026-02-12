import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import os
from dotenv import load_dotenv

# Try to load .env manually to be sure
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
print(f"Loaded DATABASE_URL: {DATABASE_URL}")

def test_psycopg2_connection(url):
    print("\n--- Testing psycopg2 connection ---")
    try:
        # manual parse for psycopg2
        from urllib.parse import urlparse
        result = urlparse(url)
        username = result.username
        password = result.password
        database = result.path[1:]
        hostname = result.hostname
        port = result.port or 5432
        
        print(f"Connecting to: user={username}, host={hostname}, port={port}, db={database}")
        
        conn = psycopg2.connect(
            database=database,
            user=username,
            password=password,
            host=hostname,
            port=port
        )
        print("SUCCESS: Connected via psycopg2!")
        conn.close()
        return True
    except Exception as e:
        print(f"FAILURE: psycopg2 connection failed: {e}")
        return False

def test_sqlalchemy_connection(url):
    print("\n--- Testing SQLAlchemy connection ---")
    try:
        engine = create_engine(url)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("SUCCESS: Connected via SQLAlchemy! Result:", result.fetchone())
        return True
    except Exception as e:
        print(f"FAILURE: SQLAlchemy connection failed: {e}")
        return False

def create_db_if_missing(url):
    print("\n--- Checking database existence ---")
    try:
        from urllib.parse import urlparse
        result = urlparse(url)
        username = result.username
        password = result.password
        target_db = result.path[1:]
        hostname = result.hostname
        port = result.port or 5432

        # Connect to 'postgres' default db
        conn = psycopg2.connect(
            database="postgres",
            user=username,
            password=password,
            host=hostname,
            port=port
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        cur.execute(f"SELECT 1 FROM pg_database WHERE datname = '{target_db}'")
        exists = cur.fetchone()
        
        if not exists:
            print(f"Database '{target_db}' does not exist. Creating...")
            cur.execute(f"CREATE DATABASE {target_db}")
            print(f"SUCCESS: Database '{target_db}' created.")
        else:
            print(f"Database '{target_db}' already exists.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"FAILURE: Could not check/create database: {e}")

if __name__ == "__main__":
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not found in environment.")
    else:
        # First ensure DB exists (using the credentials in URL)
        create_db_if_missing(DATABASE_URL)
        
        success_psycopg2 = test_psycopg2_connection(DATABASE_URL)
        if success_psycopg2:
            test_sqlalchemy_connection(DATABASE_URL)

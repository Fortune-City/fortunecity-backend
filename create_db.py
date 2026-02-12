import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()

# Default credentials from .env or fallback
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost/fortunecity")

# Parse connection params simply (assuming format postgresql://user:password@host/db)
try:
    # This is a very basic parser, better to use urlparse but this suffices for standard Connection String
    from urllib.parse import urlparse
    result = urlparse(DATABASE_URL)
    user = result.username
    password = result.password
    host = result.hostname
    port = result.port or 5432
    dbname = result.path[1:] # remove leading slash
except Exception as e:
    print(f"Error parsing DATABASE_URL: {e}")
    exit(1)

def create_database():
    try:
        # Connect to default 'postgres' database to create new db
        con = psycopg2.connect(dbname='postgres', user=user, host=host, password=password, port=port)
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()
        
        # Check if database exists
        cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{dbname}'")
        exists = cur.fetchone()
        
        if not exists:
            print(f"Creating database '{dbname}'...")
            cur.execute(f'CREATE DATABASE "{dbname}"')
            print(f"Database '{dbname}' created successfully.")
        else:
            print(f"Database '{dbname}' already exists.")
            
        cur.close()
        con.close()
    except Exception as e:
        print(f"Error creating database: {e}")
        # If connection failed, maybe password handles differ?
        # But we can't do much without user input if connectivity fails.

if __name__ == "__main__":
    create_database()

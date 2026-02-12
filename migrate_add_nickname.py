from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

def migrate():
    # Use the same logic as database.py to get the URL
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
    if not SQLALCHEMY_DATABASE_URL:
        SQLALCHEMY_DATABASE_URL = "postgresql://postgres:password@localhost/fortunecity"

    print(f"Connecting to database...")
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

    try:
        with engine.connect() as conn:
            # Check if nickname column exists
            check_sql = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='nickname';
            """)
            result = conn.execute(check_sql).fetchone()
            
            if not result:
                print("Adding nickname column to users table...")
                conn.execute(text("ALTER TABLE users ADD COLUMN nickname VARCHAR"))
                conn.commit()
                print("Migration successful: Added nickname column.")
            else:
                print("Migration skipped: nickname column already exists.")
                
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    migrate()

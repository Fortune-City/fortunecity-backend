from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

def migrate():
    engine = create_engine(os.getenv("DATABASE_URL"))
    
    with engine.connect() as conn:
        try:
            # Add start_date column
            conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS start_date VARCHAR;"))
            # Add end_date column
            conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS end_date VARCHAR;"))
            conn.commit()
            print("Migration successful: added start_date and end_date columns to events table.")
        except Exception as e:
            print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()

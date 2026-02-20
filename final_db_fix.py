from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

def fix():
    engine = create_engine(os.getenv("DATABASE_URL"))
    
    with engine.connect() as conn:
        # Drop problematic columns if they exist
        cols_to_drop = ["organizer_name_public_id"]
        for col in cols_to_drop:
            try:
                conn.execute(text(f"ALTER TABLE events DROP COLUMN IF EXISTS {col};"))
                conn.commit()
                print(f"Dropped {col}")
            except: pass
            
        # Add correct columns
        cols_to_add = [
            ("featured_image", "VARCHAR"),
            ("featured_image_public_id", "VARCHAR"),
            ("organizer_name", "VARCHAR"),
            ("organizer_phone", "VARCHAR"),
            ("organizer_email", "VARCHAR")
        ]
        
        for col, ctype in cols_to_add:
            try:
                print(f"Adding {col}...")
                conn.execute(text(f"ALTER TABLE events ADD COLUMN IF NOT EXISTS {col} {ctype};"))
                conn.commit()
                print(f"Added {col}")
            except Exception as e:
                print(f"Error adding {col}: {e}")

if __name__ == "__main__":
    fix()

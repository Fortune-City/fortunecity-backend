from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

def fix():
    engine = create_engine(os.getenv("DATABASE_URL"))
    
    with engine.connect() as conn:
        # 1. Drop the weird column
        try:
            conn.execute(text("ALTER TABLE events DROP COLUMN IF EXISTS organizer_name_public_id;"))
            conn.commit()
            print("Dropped weird column")
        except Exception as e:
            print(f"Error dropping: {e}")

        # 2. Add the correct columns one by one
        cols = [
            "featured_image",
            "featured_image_public_id",
            "organizer_name",
            "organizer_phone",
            "organizer_email",
            "start_date",
            "end_date"
        ]
        
        for col in cols:
            try:
                conn.execute(text(f"ALTER TABLE events ADD COLUMN IF NOT EXISTS {col} VARCHAR;"))
                conn.commit()
                print(f"Ensured {col} exists")
            except Exception as e:
                print(f"Error ensuring {col}: {e}")

if __name__ == "__main__":
    fix()

from sqlalchemy import create_engine, inspect, text
import os
from dotenv import load_dotenv

load_dotenv()

def migrate():
    engine = create_engine(os.getenv("DATABASE_URL"))
    inspector = inspect(engine)
    existing_columns = [col['name'] for col in inspector.get_columns('events')]
    
    # List of columns that SHOULD be there based on models.py
    required_columns = [
        ("start_date", "VARCHAR"),
        ("end_date", "VARCHAR"),
        ("featured_image", "VARCHAR"),
        ("featured_image_public_id", "VARCHAR"),
        ("organizer_name", "VARCHAR"),
        ("organizer_phone", "VARCHAR"),
        ("organizer_email", "VARCHAR"),
        ("category", "VARCHAR"),
        ("address", "TEXT"),
        ("map_url", "TEXT")
    ]
    
    with engine.connect() as conn:
        for col_name, col_type in required_columns:
            if col_name not in existing_columns:
                try:
                    print(f"Adding missing column: {col_name} ({col_type})")
                    conn.execute(text(f"ALTER TABLE events ADD COLUMN {col_name} {col_type};"))
                    conn.commit()
                except Exception as e:
                    print(f"Failed to add {col_name}: {e}")
            else:
                print(f"Column already exists: {col_name}")

if __name__ == "__main__":
    migrate()

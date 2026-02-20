from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

def migrate():
    engine = create_engine(os.getenv("DATABASE_URL"))
    
    columns_to_add = [
        ("start_date", "VARCHAR"),
        ("end_date", "VARCHAR"),
        ("featured_image", "VARCHAR"),
        ("featured_image_public_id", "VARCHAR")
    ]
    
    with engine.connect() as conn:
        for col_name, col_type in columns_to_add:
            try:
                # Direct SQL execution
                print(f"Adding {col_name}...")
                conn.execute(text(f'ALTER TABLE events ADD COLUMN IF NOT EXISTS {col_name} {col_type};'))
                conn.commit()
                print(f"Added {col_name} successfully.")
            except Exception as e:
                print(f"Error adding {col_name}: {e}")

if __name__ == "__main__":
    migrate()

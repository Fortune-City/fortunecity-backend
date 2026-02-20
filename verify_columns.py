from sqlalchemy import create_engine, inspect
import os
from dotenv import load_dotenv

load_dotenv()

def verify():
    engine = create_engine(os.getenv("DATABASE_URL"))
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('events')]
    
    check_list = ['featured_image', 'featured_image_public_id', 'start_date', 'end_date']
    
    print("--- Verification Results ---")
    for col in check_list:
        status = "EXISTS" if col in columns else "MISSING"
        print(f"Column '{col}': {status}")
    
    print("\nAll columns found:", columns)

if __name__ == "__main__":
    verify()

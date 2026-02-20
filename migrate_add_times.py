from database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE events ADD COLUMN start_time VARCHAR"))
            conn.execute(text("ALTER TABLE events ADD COLUMN end_time VARCHAR"))
            conn.commit()
            print("Successfully added start_time and end_time columns to events table.")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                print("Columns already exist.")
            else:
                print(f"Error migrating: {e}")

if __name__ == "__main__":
    migrate()

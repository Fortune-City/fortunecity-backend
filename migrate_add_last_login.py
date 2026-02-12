"""
Migration script to add last_login column to users table
"""
from database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        try:
            # Add last_login column to users table
            conn.execute(text("ALTER TABLE users ADD COLUMN last_login TIMESTAMP"))
            conn.commit()
            print("✅ Successfully added last_login column to users table")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("ℹ️  Column last_login already exists, skipping migration")
            else:
                print(f"❌ Error during migration: {e}")
                raise

if __name__ == "__main__":
    migrate()

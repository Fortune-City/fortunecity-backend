"""
Set default nickname for admin user
"""
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in .env file")
    exit(1)

print(f"Connecting to database...")
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        # Update admin user's nickname to "Admin"
        result = conn.execute(text("""
            UPDATE users 
            SET nickname = 'Admin' 
            WHERE role = 'admin' AND (nickname IS NULL OR nickname = '')
        """))
        conn.commit()
        
        print(f"✓ Updated {result.rowcount} admin user(s) with default nickname 'Admin'")
        
        # Show current admin users
        result = conn.execute(text("""
            SELECT username, nickname, role 
            FROM users 
            WHERE role = 'admin'
        """))
        
        print("\nCurrent admin users:")
        for row in result:
            print(f"  - Username: {row[0]}, Nickname: {row[1]}, Role: {row[2]}")
            
except Exception as e:
    print(f"Error: {e}")

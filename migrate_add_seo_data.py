"""
Migration script to add seo_data column to blog_posts table
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
        # Check if column exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='blog_posts' AND column_name='seo_data'
        """))
        
        exists = result.fetchone() is not None
        
        if exists:
            print("✓ seo_data column already exists")
        else:
            print("✗ seo_data column does not exist")
            print("Adding seo_data column...")
            
            conn.execute(text("""
                ALTER TABLE blog_posts 
                ADD COLUMN seo_data JSON
            """))
            conn.commit()
            
            print("✓ seo_data column added successfully")
            
except Exception as e:
    print(f"Error: {e}")

"""
Migration script to add comments table
"""
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in .env file")
    exit(1)

print(f"Connecting to database...")
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        # Check if comments table exists (PostgreSQL specific)
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'comments'
        """))
        
        if result.fetchone():
            print("✓ Comments table already exists")
        else:
            print("Creating comments table...")
            
            # Create comments table (PostgreSQL syntax)
            conn.execute(text("""
                CREATE TABLE comments (
                    id SERIAL PRIMARY KEY,
                    post_id INTEGER NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    phone_number VARCHAR(20) NOT NULL,
                    message TEXT NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (post_id) REFERENCES blog_posts(id) ON DELETE CASCADE
                )
            """))
            
            conn.commit()
            print("✓ Comments table created successfully")
            
except Exception as e:
    print(f"Error: {e}")

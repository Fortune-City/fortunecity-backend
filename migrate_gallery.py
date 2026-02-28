import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")

try:
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    # Create collections table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gallery_collections (
        id SERIAL PRIMARY KEY,
        name VARCHAR NOT NULL,
        description TEXT,
        date VARCHAR,
        type VARCHAR DEFAULT 'photo',
        featured_image VARCHAR,
        featured_image_public_id VARCHAR,
        "order" INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_gallery_collections_id ON gallery_collections (id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_gallery_collections_type ON gallery_collections (type);")
    
    # Add collection_id to gallery_items
    cursor.execute("ALTER TABLE gallery_items ADD COLUMN IF NOT EXISTS collection_id INTEGER REFERENCES gallery_collections(id) ON DELETE CASCADE;")
    
    conn.commit()
    print("Migration successful")
except Exception as e:
    print(f"Migration failed: {e}")
finally:
    if 'conn' in locals():
        conn.close()

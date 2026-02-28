"""
Safe, idempotent migration script for the gallery schema.
Adds every column that the SQLAlchemy models expect but that may be missing
from the production database.  Uses IF NOT EXISTS checks so it is completely
safe to re-run — existing columns are never touched.

Usage:
    cd backend
    python migrate_gallery.py
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in .env")

# ---------------------------------------------------------------------------
# All ALTER TABLE statements.
# Each one uses  ADD COLUMN IF NOT EXISTS  so they are idempotent.
# ---------------------------------------------------------------------------
MIGRATIONS = [
    # ── gallery_collections ────────────────────────────────────────────────
    "ALTER TABLE gallery_collections ADD COLUMN IF NOT EXISTS description TEXT;",
    "ALTER TABLE gallery_collections ADD COLUMN IF NOT EXISTS date VARCHAR;",
    "ALTER TABLE gallery_collections ADD COLUMN IF NOT EXISTS type VARCHAR DEFAULT 'photo';",
    "ALTER TABLE gallery_collections ADD COLUMN IF NOT EXISTS featured_image VARCHAR;",
    "ALTER TABLE gallery_collections ADD COLUMN IF NOT EXISTS featured_image_public_id VARCHAR;",
    'ALTER TABLE gallery_collections ADD COLUMN IF NOT EXISTS "order" INTEGER DEFAULT 0;',
    "CREATE INDEX IF NOT EXISTS ix_gallery_collections_type  ON gallery_collections (type);",
    'CREATE INDEX IF NOT EXISTS ix_gallery_collections_order ON gallery_collections ("order");',

    # ── gallery_collections table (create if it doesn't exist at all) ──────
    # (The ALTER statements above will fail gracefully if the table is missing;
    #  the CREATE TABLE below ensures it exists first.)

    # ── gallery_items ──────────────────────────────────────────────────────
    "ALTER TABLE gallery_items ADD COLUMN IF NOT EXISTS collection_id INTEGER REFERENCES gallery_collections(id) ON DELETE CASCADE;",
    "ALTER TABLE gallery_items ADD COLUMN IF NOT EXISTS type VARCHAR DEFAULT 'photo';",
    "ALTER TABLE gallery_items ADD COLUMN IF NOT EXISTS public_id VARCHAR;",
    "ALTER TABLE gallery_items ADD COLUMN IF NOT EXISTS thumbnail_url VARCHAR;",
    "ALTER TABLE gallery_items ADD COLUMN IF NOT EXISTS title VARCHAR;",
    "ALTER TABLE gallery_items ADD COLUMN IF NOT EXISTS collection_name VARCHAR;",
    "ALTER TABLE gallery_items ADD COLUMN IF NOT EXISTS event_date VARCHAR;",
    'ALTER TABLE gallery_items ADD COLUMN IF NOT EXISTS "order" INTEGER DEFAULT 0;',
    "CREATE INDEX IF NOT EXISTS ix_gallery_items_type         ON gallery_items (type);",
    'CREATE INDEX IF NOT EXISTS ix_gallery_items_order        ON gallery_items ("order");',
    "CREATE INDEX IF NOT EXISTS ix_gallery_items_collection_id ON gallery_items (collection_id);",
]

ENSURE_TABLES = """
-- Create gallery_collections if it does not already exist
CREATE TABLE IF NOT EXISTS gallery_collections (
    id                       SERIAL PRIMARY KEY,
    name                     VARCHAR NOT NULL,
    description              TEXT,
    date                     VARCHAR,
    type                     VARCHAR DEFAULT 'photo',
    featured_image           VARCHAR,
    featured_image_public_id VARCHAR,
    "order"                  INTEGER DEFAULT 0,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create gallery_items if it does not already exist
CREATE TABLE IF NOT EXISTS gallery_items (
    id              SERIAL PRIMARY KEY,
    collection_id   INTEGER REFERENCES gallery_collections(id) ON DELETE CASCADE,
    type            VARCHAR DEFAULT 'photo',
    url             VARCHAR NOT NULL,
    public_id       VARCHAR,
    thumbnail_url   VARCHAR,
    title           VARCHAR,
    collection_name VARCHAR,
    event_date      VARCHAR,
    "order"         INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

def run():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("🔧 Ensuring tables exist...")
        cur.execute(ENSURE_TABLES)

        print("🔧 Applying column migrations...")
        for sql in MIGRATIONS:
            try:
                cur.execute(sql)
                label = sql.strip().split("\n")[0][:80]
                print(f"  ✅ {label}")
            except Exception as col_err:
                # Roll back only the failed statement and continue
                conn.rollback()
                print(f"  ⚠️  Skipped (already applied or minor error): {col_err}")
                continue
            conn.commit()   # commit each statement individually

        print("\n✅ Migration complete.")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    run()

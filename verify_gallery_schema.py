import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()
cur.execute("""
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_name IN ('gallery_items', 'gallery_collections')
    ORDER BY table_name, ordinal_position;
""")
rows = cur.fetchall()
current_table = None
for table, col, dtype in rows:
    if table != current_table:
        print(f"\n📋 {table}")
        current_table = table
    print(f"   • {col:35s} {dtype}")
conn.close()

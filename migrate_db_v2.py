from sqlalchemy import text, inspect
from database import engine, SQLALCHEMY_DATABASE_URL

def migrate():
    print(f"Connecting to: {SQLALCHEMY_DATABASE_URL}")
    
    # Structure: (Table, Column, Type)
    migrations = [
        # Events table
        ("events", "is_registration_enabled", "BOOLEAN DEFAULT FALSE"),
        ("events", "registration_fee", "VARCHAR DEFAULT '0'"),
        ("events", "child_registration_fee", "VARCHAR DEFAULT '0'"),
        ("events", "child_age_limit", "VARCHAR"),
        ("events", "max_attendees", "INTEGER"),
        ("events", "external_registration_url", "VARCHAR"),
        ("events", "start_date", "VARCHAR"),
        ("events", "end_date", "VARCHAR"),
        ("events", "start_time", "VARCHAR"),
        ("events", "end_time", "VARCHAR"),
        ("events", "registration_start_date", "VARCHAR"),
        ("events", "registration_end_date", "VARCHAR"),
        ("events", "order", "INTEGER DEFAULT 0"),
        ("events", "featured_image_alt", "VARCHAR"),
        
        # Users table
        ("users", "role", "VARCHAR DEFAULT 'admin'"),
        ("users", "nickname", "VARCHAR"),
        ("users", "last_login", "TIMESTAMP"),
        ("users", "profile_image", "VARCHAR"),
        ("users", "profile_image_public_id", "VARCHAR"),
        
        # Blog Posts table
        ("blog_posts", "seo_data", "JSONB DEFAULT '{}'"),
        ("blog_posts", "tags", "JSONB DEFAULT '[]'"),
        
        # Event Registrations table
        ("event_registrations", "child_ticket_count", "INTEGER DEFAULT 0"),
        ("event_registrations", "ticket_id", "VARCHAR"),
        ("event_registrations", "status", "VARCHAR DEFAULT 'confirmed'"),
        
        # Gallery Items table
        ("gallery_items", "collection_name", "VARCHAR"),
        ("gallery_items", "event_date", "VARCHAR"),
        ("gallery_items", "order", "INTEGER DEFAULT 0"),
        
        # Gallery Collections table
        ("gallery_collections", "order", "INTEGER DEFAULT 0"),
    ]
    
    inspector = inspect(engine)
    
    with engine.connect() as conn:
        for table, col, col_type in migrations:
            # Check if table exists
            if not inspector.has_table(table):
                print(f"Skipping {table}.{col} - Table '{table}' does not exist.")
                continue
                
            # Check if column exists
            columns = [c['name'] for c in inspector.get_columns(table)]
            if col in columns:
                print(f"Column '{col}' already exists in '{table}'.")
                continue
                
            try:
                print(f"Adding column '{col}' to '{table}'...")
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
                print(f"Successfully added '{col}' to '{table}'.")
            except Exception as e:
                print(f"Error adding '{col}' to '{table}': {e}")
                
    print("\nMigration verification complete.")

if __name__ == "__main__":
    migrate()

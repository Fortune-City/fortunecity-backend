from sqlalchemy import text
from database import engine

def migrate():
    # Columns to add to 'events' table
    events_cols = [
        ("is_registration_enabled", "BOOLEAN DEFAULT FALSE"),
        ("registration_fee", "VARCHAR DEFAULT '0'"),
        ("child_registration_fee", "VARCHAR DEFAULT '0'"),
        ("child_age_limit", "VARCHAR"),
        ("max_attendees", "INTEGER"),
        ("external_registration_url", "VARCHAR")
    ]
    
    # Columns to add to 'event_registrations' table
    reg_cols = [
        ("child_ticket_count", "INTEGER DEFAULT 0")
    ]
    
    print("Starting migration...")
    
    # Apply 'events' migrations
    for col_name, col_type in events_cols:
        with engine.connect() as conn:
            try:
                conn.execute(text(f"ALTER TABLE events ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                print(f"Added '{col_name}' to 'events'.")
            except Exception as e:
                # If column already exists, it's fine
                if "already exists" in str(e).lower():
                    print(f"Column '{col_name}' already exists in 'events'.")
                else:
                    print(f"Error adding '{col_name}' to 'events': {e}")

    # Apply 'event_registrations' migrations
    for col_name, col_type in reg_cols:
        with engine.connect() as conn:
            try:
                conn.execute(text(f"ALTER TABLE event_registrations ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                print(f"Added '{col_name}' to 'event_registrations'.")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"Column '{col_name}' already exists in 'event_registrations'.")
                else:
                    print(f"Error adding '{col_name}' to 'event_registrations': {e}")
                    
    print("Migration finished.")

if __name__ == "__main__":
    migrate()

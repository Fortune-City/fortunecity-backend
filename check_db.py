from sqlalchemy import text
from database import engine

def check_columns():
    with engine.connect() as conn:
        print("Checking columns for table 'events':")
        result = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'events'"))
        for row in result:
            print(f" - {row[0]}: {row[1]}")
            
        print("\nChecking columns for table 'event_registrations':")
        result = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'event_registrations'"))
        for row in result:
            print(f" - {row[0]}: {row[1]}")

if __name__ == "__main__":
    check_columns()

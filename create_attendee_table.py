import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine, Base
import models

def create_tables():
    print("Creating tables...")
    try:
        # This will create event_attendees if it doesn't exist
        Base.metadata.create_all(bind=engine)
        print("Tables created/verified successfully.")
    except Exception as e:
        print(f"Error creating tables: {e}")

if __name__ == "__main__":
    create_tables()

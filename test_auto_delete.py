
from database import SessionLocal
import models
from datetime import datetime

def insert_expired():
    db = SessionLocal()
    # Delete any existing test-expired-event first
    db.query(models.Event).filter(models.Event.slug == "test-expired-event").delete()
    db.commit()
    
    event = models.Event(
        title="Test Expired Event",
        slug="test-expired-event",
        description="This event should be auto-deleted",
        end_date="20-02-2026",
        end_time="11:00 PM",
        category="ENTERTAINMENT"
    )
    db.add(event)
    db.commit()
    print("Inserted expired event with date 20-02-2026 11:00 PM.")
    db.close()

if __name__ == "__main__":
    insert_expired()

from database import SessionLocal
import models
import schemas
from typing import List

db = SessionLocal()
try:
    events = db.query(models.Event).all()
    print(f"Fetched {len(events)} events.")
    for event in events:
        print(f"Event ID: {event.id}, Title: {event.title}")
        # Try to validate with schema
        try:
            s = schemas.EventResponse.from_orm(event)
            print(f"  Schema validation success for {event.id}")
        except Exception as ve:
            print(f"  Schema validation FAILED for {event.id}: {ve}")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()

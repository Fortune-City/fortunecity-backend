
from database import SessionLocal
import models
from datetime import datetime

def check():
    db = SessionLocal()
    events = db.query(models.Event).all()
    print(f"Total events: {len(events)}")
    for e in events:
        print(f"ID: {e.id}, Title: {e.title}, End Date: {e.end_date}, End Time: {e.end_time}")
    db.close()

if __name__ == "__main__":
    check()

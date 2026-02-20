from database import engine
from sqlalchemy import inspect
import models

inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"Tables: {tables}")

if "events" in tables:
    from sqlalchemy.orm import Session
    from database import SessionLocal
    db = SessionLocal()
    try:
        count = db.query(models.Event).count()
        print(f"Events count: {count}")
    except Exception as e:
        print(f"Error querying events: {e}")
    finally:
        db.close()
else:
    print("Events table MISSING!")

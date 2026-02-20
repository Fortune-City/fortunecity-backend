from database import SessionLocal
import models
import json
from datetime import datetime

def serialize(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj

db = SessionLocal()
try:
    events = db.query(models.Event).all()
    for event in events:
        d = {c.name: serialize(getattr(event, c.name)) for c in event.__table__.columns}
        print(json.dumps(d, indent=2))
finally:
    db.close()

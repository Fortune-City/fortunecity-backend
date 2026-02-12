from database import SessionLocal
from models import User

db = SessionLocal()
users = db.query(User).all()

print(f"Found {len(users)} users.")
for user in users:
    print(f"ID: {user.id}, Username: {user.username}, Role: {user.role}")
    if user.role is None:
        print(f"Fixing role for user {user.username}...")
        user.role = "admin"
        db.commit()
        print("Fixed.")

db.close()

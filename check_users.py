from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models

# Create a session
db = SessionLocal()

try:
    # Query all users
    users = db.query(models.User).all()
    
    print("\n--- Users in Database ---")
    print(f"{'ID':<5} | {'Username':<30} | {'Is Active':<10}")
    print("-" * 50)
    
    for user in users:
        print(f"{user.id:<5} | {user.username:<30} | {str(user.is_active):<10}")
        
    print("-" * 50)
    print(f"Total Users: {len(users)}\n")
    
except Exception as e:
    print(f"Error querying database: {e}")
finally:
    db.close()

from sqlalchemy import create_engine, inspect
import os
from dotenv import load_dotenv

load_dotenv()

def verify():
    engine = create_engine(os.getenv("DATABASE_URL"))
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('events')]
    print("Columns found:")
    for c in columns:
        print(f"COL: {c}")

if __name__ == "__main__":
    verify()

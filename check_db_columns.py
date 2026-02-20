from sqlalchemy import create_engine, inspect
import os
from dotenv import load_dotenv

load_dotenv()

def check_columns():
    engine = create_engine(os.getenv("DATABASE_URL"))
    inspector = inspect(engine)
    columns = inspector.get_columns('events')
    print("Columns in 'events' table:")
    for column in columns:
        print(f"- {column['name']}: {column['type']}")

if __name__ == "__main__":
    check_columns()

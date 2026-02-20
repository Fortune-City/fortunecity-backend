from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()

def verify():
    engine = create_engine(os.getenv("DATABASE_URL"))
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM events LIMIT 0"))
        print("Real Column Names:")
        for name in result.keys():
            print(f"|{name}|")

from sqlalchemy import text
if __name__ == "__main__":
    verify()

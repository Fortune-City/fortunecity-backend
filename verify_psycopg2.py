import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def verify():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("SELECT * FROM events LIMIT 0;")
    colnames = [desc[0] for desc in cur.description]
    print("Real Column Names:")
    for name in colnames:
        print(f"|{name}|")
    cur.close()
    conn.close()

if __name__ == "__main__":
    verify()

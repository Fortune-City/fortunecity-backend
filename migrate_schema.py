from sqlalchemy import text
from database import engine

def migrate():
    with engine.connect() as connection:
        statement = text("ALTER TABLE comments ALTER COLUMN phone_number DROP NOT NULL;")
        connection.execute(statement)
        connection.commit()
        print("Migration successful: phone_number is now nullable.")

if __name__ == "__main__":
    migrate()

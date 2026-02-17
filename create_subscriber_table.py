from database import engine
from models import Base, Subscriber

def create_table():
    print("Creating subscriber table...")
    Base.metadata.create_all(bind=engine)
    print("Done.")

if __name__ == "__main__":
    create_table()

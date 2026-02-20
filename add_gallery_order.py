from sqlalchemy import text
from database import engine

def add_gallery_order_column():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE gallery_items ADD COLUMN \"order\" INTEGER DEFAULT 0"))
            conn.commit()
            print("Column 'order' added successfully to 'gallery_items' table.")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("Column 'order' already exists.")
            else:
                print(f"Error: {e}")

if __name__ == "__main__":
    add_gallery_order_column()

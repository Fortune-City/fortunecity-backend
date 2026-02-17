from database import engine
from sqlalchemy import text

def add_column():
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE blog_posts ADD COLUMN featured_image_alt VARCHAR"))
            conn.commit()
        print("Successfully added featured_image_alt column to blog_posts table")
    except Exception as e:
        print(f"Error adding column (it might already exist): {e}")

if __name__ == "__main__":
    add_column()

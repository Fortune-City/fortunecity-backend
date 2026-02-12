from database import SessionLocal
from models import BlogPost

db = SessionLocal()
posts = db.query(BlogPost).all()

print(f"Total posts: {len(posts)}")
for post in posts:
    print(f"ID: {post.id}, Title: {post.title}, Status: '{post.status}', Slug: {post.slug}")

db.close()

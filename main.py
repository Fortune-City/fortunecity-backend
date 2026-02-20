from fastapi import FastAPI, Depends, HTTPException, status, Form, File, UploadFile
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text
from datetime import datetime
from database import engine, get_db
import models
import schemas
from auth_utils import verify_password, get_password_hash, create_access_token
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import os
import traceback
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
import asyncio
import re

load_dotenv(override=True)

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Fortune City API")

# Security: CORS Policy
origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174")
origins = [origin.strip() for origin in origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security: Trusted Host
allowed_hosts_str = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
allowed_hosts = [host.strip() for host in allowed_hosts_str.split(",")]

from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=allowed_hosts
)

@app.on_event("startup")
async def startup_db_client():
    # Seed Admin User if not exists
    db = next(get_db())
    try:
        # Check for admin user
        admin_email = "admin@123"
        admin_user = db.query(models.User).filter(models.User.username == admin_email).first()
        
        if not admin_user:
            # Create default admin user
            # In production, you might want to load these from env vars too for better security
            default_password = os.getenv("ADMIN_DEFAULT_PASSWORD", "fortunecityadmin@123")
            hashed_pwd = get_password_hash(default_password)
            
            new_admin = models.User(username=admin_email, hashed_password=hashed_pwd)
            db.add(new_admin)
            db.commit()
            print(f"System: Admin user '{admin_email}' seeded successfully.")
    except Exception as e:
        print(f"System: Error seeding database: {e}")
    finally:
        db.close()
    
    # Start background cleanup task for expired events
    print("System: Launching event cleanup background task...")
    asyncio.create_task(cleanup_expired_events_task())

# Configure Cloudinary globally once
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

def get_cloudinary_config():
    """Redundant now, but kept for compatibility with existing code if needed."""
    pass

async def cleanup_expired_events_task():
    """Background task to remove events that have already passed their end time."""
    print("System: Event cleanup background task started.")
    while True:
        try:
            from database import SessionLocal
            import models
            from datetime import datetime
            import cloudinary.uploader
            
            db = SessionLocal()
            try:
                # Use current local time for comparison since dates in DB are local strings
                now = datetime.now()
                events = db.query(models.Event).all()
                deleted_count = 0
                
                for event in events:
                    if not event.end_date:
                        continue
                        
                    try:
                        # Parse date and time (default to 11:59 PM if no end_time)
                        time_str = event.end_time if event.end_time else "11:59 PM"
                        # Expecting format like '22-02-2026 11:46 PM'
                        end_dt = datetime.strptime(f"{event.end_date} {time_str}", "%d-%m-%Y %I:%M %p")
                        
                        if now > end_dt:
                            print(f"Cleanup: Event '{event.title}' (ID: {event.id}) expired on {end_dt}. Deleting...")
                            
                            # Delete image from Cloudinary if it exists
                            if event.featured_image_public_id:
                                try:
                                    cloudinary.uploader.destroy(event.featured_image_public_id, invalidate=True)
                                except Exception as ce:
                                    print(f"Cleanup: Cloudinary deletion failed for {event.featured_image_public_id}: {ce}")
                            
                            db.delete(event)
                            deleted_count += 1
                    except Exception as parse_err:
                        # Skip if date format is invalid or can't be parsed
                        continue
                
                if deleted_count > 0:
                    db.commit()
                    print(f"Cleanup: Successfully removed {deleted_count} expired events.")
            finally:
                db.close()
        except Exception as e:
            print(f"Cleanup Error: {e}")
            
        # Run every 600 seconds (10 minutes)
        await asyncio.sleep(600)

@app.get("/")
def read_root():
    return {"message": "Welcome to Fortune City Backend"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}

@app.post("/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    # query user by username
    user = db.query(models.User).filter(models.User.username == user_credentials.username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login timestamp
    from datetime import datetime
    user.last_login = datetime.utcnow()
    db.commit()
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role or "user"}

# Dependency to get current user
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from jose import JWTError, jwt
    from auth_utils import SECRET_KEY, ALGORITHM
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

@app.get("/me", response_model=schemas.UserResponse)
def get_current_user_info(current_user: models.User = Depends(get_current_user)):
    """Get current authenticated user's information"""
    return current_user


@app.post("/users", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Only admin can create users
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create users"
        )
        
    # Validate username has @
    if "@" not in user.username:
        raise HTTPException(status_code=400, detail="Username must contain '@'")
        
    # Check if user exists
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Set default nickname for admin users if not provided
    nickname = user.nickname
    if not nickname and user.role == "admin":
        nickname = "Admin"
        
    hashed_password = get_password_hash(user.password)
    new_user = models.User(
        username=user.username, 
        nickname=nickname,
        hashed_password=hashed_password, 
        role=user.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

from typing import List
@app.get("/users", response_model=List[schemas.UserResponse])
def get_users(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view users"
        )
    users = db.query(models.User).all()
    return users

@app.put("/users/{username}")
def update_user(username: str, update_data: dict, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Only admin can update users
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update users"
        )
    
    # Prevent updating the default admin account
    if username == "admin@123":
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The default admin account credentials cannot be modified"
        )

    # Get the user to update
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update username if provided and different
    if "username" in update_data and update_data["username"] != user.username:
        # Check if new username already exists
        new_username = update_data["username"]
        if "@" not in new_username:
             raise HTTPException(status_code=400, detail="Username must contain '@'")
             
        existing_user = db.query(models.User).filter(models.User.username == new_username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="New username already taken")
        user.username = new_username
    
    # Update password if provided
    if "password" in update_data and update_data["password"]:
        user.hashed_password = get_password_hash(update_data["password"])
    
    # Update role if provided
    if "role" in update_data:
        user.role = update_data["role"]
        
    # Update nickname if provided
    if "nickname" in update_data:
        user.nickname = update_data["nickname"]
    
    db.commit()
    db.refresh(user)
    return {"message": "User updated successfully", "username": user.username}

@app.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(username: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Only admin can delete users
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete users"
        )
    
    # Check if user is trying to delete themselves
    if current_user.username == username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account"
        )
        
    # Prevent deleting the default admin account
    if username == "admin@123":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The default admin account cannot be deleted"
        )

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    db.delete(user)
    db.commit()
    db.delete(user)
    db.commit()
    return None

# --- Subscriber Endpoints ---
@app.post("/subscribe", response_model=schemas.SubscriberResponse, status_code=status.HTTP_201_CREATED)
def subscribe_newsletter(subscriber: schemas.SubscriberCreate, db: Session = Depends(get_db)):
    # Check if email exists
    existing_subscriber = db.query(models.Subscriber).filter(models.Subscriber.email == subscriber.email).first()
    if existing_subscriber:
        raise HTTPException(status_code=400, detail="Email already subscribed")
    
    new_subscriber = models.Subscriber(name=subscriber.name, email=subscriber.email, phone=subscriber.phone)
    db.add(new_subscriber)
    db.commit()
    db.refresh(new_subscriber)
    return new_subscriber

@app.get("/admin/subscribers", response_model=List[schemas.SubscriberResponse])
def get_subscribers(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return db.query(models.Subscriber).order_by(models.Subscriber.created_at.desc()).all()

@app.delete("/admin/subscribers/{subscriber_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscriber(subscriber_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    subscriber = db.query(models.Subscriber).filter(models.Subscriber.id == subscriber_id).first()
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")
        
    db.delete(subscriber)
    db.commit()
    return None

# --- Contact Enquiries ---

@app.post("/contact", response_model=schemas.ContactEnquiryResponse, status_code=status.HTTP_201_CREATED)
def create_contact_enquiry(enquiry: schemas.ContactEnquiryCreate, db: Session = Depends(get_db)):
    new_enquiry = models.ContactEnquiry(
        name=enquiry.name,
        email=enquiry.email,
        phone=enquiry.phone,
        message=enquiry.message
    )
    db.add(new_enquiry)
    db.commit()
    db.refresh(new_enquiry)
    return new_enquiry

@app.get("/contact", response_model=List[schemas.ContactEnquiryResponse])
def get_contact_enquiries(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Only admin can view enquiries
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view enquiries"
        )
    return db.query(models.ContactEnquiry).order_by(models.ContactEnquiry.created_at.desc()).all()

@app.delete("/contact/{enquiry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact_enquiry(enquiry_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete enquiries"
        )
    
    enquiry = db.query(models.ContactEnquiry).filter(models.ContactEnquiry.id == enquiry_id).first()
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")
        
    db.delete(enquiry)
    db.commit()
    return None


# --- Blog Posts ---

@app.post("/posts", response_model=schemas.BlogPostResponse, status_code=status.HTTP_201_CREATED)
def create_blog_post(post: schemas.BlogPostCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "editor"]:
        raise HTTPException(status_code=403, detail="Not authorized to create posts")
    
    # Generate slug if not provided
    if not post.slug:
        post.slug = post.title.lower().replace(" ", "-")
    
    # Check slug uniqueness
    existing_slug = db.query(models.BlogPost).filter(models.BlogPost.slug == post.slug).first()
    if existing_slug:
        raise HTTPException(status_code=400, detail="Slug already exists")

    new_post = models.BlogPost(
        title=post.title,
        content=post.content,
        excerpt=post.excerpt,
        featured_image=post.featured_image,
        featured_image_alt=post.featured_image_alt,
        status=post.status,
        slug=post.slug,
        seo_data=post.seo,
        author_id=current_user.id,
        created_at=post.created_at if post.created_at else datetime.utcnow()
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post

@app.get("/posts", response_model=List[schemas.BlogPostResponse])
def get_blog_posts(skip: int = 0, limit: int = 20, status: str = None, db: Session = Depends(get_db)):
    query = db.query(models.BlogPost)
    if status:
        query = query.filter(models.BlogPost.status == status)
    return query.order_by(models.BlogPost.created_at.desc()).offset(skip).limit(limit).all()

@app.get("/posts/{post_id}", response_model=schemas.BlogPostResponse)
def get_blog_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(models.BlogPost).filter(models.BlogPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@app.get("/posts/slug/{slug}", response_model=schemas.BlogPostResponse)
def get_blog_post_by_slug(slug: str, db: Session = Depends(get_db)):
    post = db.query(models.BlogPost).filter(models.BlogPost.slug == slug).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@app.put("/posts/{post_id}", response_model=schemas.BlogPostResponse)
def update_blog_post(post_id: int, post_update: schemas.BlogPostUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "editor"]:
        raise HTTPException(status_code=403, detail="Not authorized to update posts")
        
    db_post = db.query(models.BlogPost).filter(models.BlogPost.id == post_id).first()
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    update_data = post_update.dict(exclude_unset=True)
    
    # Map 'seo' field to 'seo_data' for database
    if 'seo' in update_data:
        update_data['seo_data'] = update_data.pop('seo')
    
    for key, value in update_data.items():
        setattr(db_post, key, value)
             
    db.commit()
    db.refresh(db_post)
    return db_post

@app.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_blog_post(post_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "editor"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete posts")
        
    post = db.query(models.BlogPost).filter(models.BlogPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    db.delete(post)
    db.commit()
    return None

# ==================== COMMENT ENDPOINTS ====================

@app.post("/posts/{post_id}/comments", response_model=schemas.CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(post_id: int, comment: schemas.CommentCreate, db: Session = Depends(get_db)):
    """Submit a new comment on a blog post (public endpoint)"""
    # Verify post exists
    post = db.query(models.BlogPost).filter(models.BlogPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Create comment with pending status
    new_comment = models.Comment(
        post_id=post_id,
        name=comment.name,
        email=comment.email,
        phone_number=comment.phone_number,
        message=comment.message,
        status="pending"
    )
    
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment

@app.get("/posts/{post_id}/comments", response_model=List[schemas.CommentResponse])
def get_post_comments(post_id: int, db: Session = Depends(get_db)):
    """Get all approved comments for a blog post (public endpoint)"""
    comments = db.query(models.Comment).filter(
        models.Comment.post_id == post_id,
        models.Comment.status == "approved"
    ).order_by(models.Comment.created_at.desc()).all()
    
    return comments

@app.get("/admin/comments", response_model=List[schemas.CommentResponse])
def get_all_comments(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get all comments for admin (requires authentication)"""
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    comments = db.query(models.Comment).options(joinedload(models.Comment.post)).order_by(models.Comment.created_at.desc()).all()
    return comments

@app.put("/admin/comments/{comment_id}/approve", response_model=schemas.CommentResponse)
def approve_comment(comment_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Approve a comment (requires authentication)"""
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    comment.status = "approved"
    db.commit()
    db.refresh(comment)
    return comment

@app.delete("/admin/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a comment (requires authentication)"""
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    db.delete(comment)
    db.commit()
    return None

from fastapi import Response

@app.get("/sitemap.xml")
def get_sitemap(db: Session = Depends(get_db)):
    """Generate dynamic sitemap.xml"""
    base_url = "https://fortunemill.com" # Update this with your actual domain
    
    # Static pages
    static_pages = [
        {"loc": f"{base_url}/", "changefreq": "daily", "priority": "1.0"},
        {"loc": f"{base_url}/about", "changefreq": "monthly", "priority": "0.8"},
        {"loc": f"{base_url}/contact", "changefreq": "monthly", "priority": "0.8"},
        {"loc": f"{base_url}/blog", "changefreq": "daily", "priority": "0.9"},
    ]
    
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    # Add static pages
    for page in static_pages:
        xml_content += '  <url>\n'
        xml_content += f'    <loc>{page["loc"]}</loc>\n'
        xml_content += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
        xml_content += f'    <priority>{page["priority"]}</priority>\n'
        xml_content += '  </url>\n'
    
    # Add blog posts
    posts = db.query(models.BlogPost).filter(models.BlogPost.status == 'published').all()
    for post in posts:
        last_mod = post.created_at.strftime("%Y-%m-%d")
        xml_content += '  <url>\n'
        xml_content += f'    <loc>{base_url}/blog/{post.slug}</loc>\n'
        xml_content += f'    <lastmod>{last_mod}</lastmod>\n'
        xml_content += '    <changefreq>weekly</changefreq>\n'
        xml_content += '    <priority>0.7</priority>\n'
        xml_content += '  </url>\n'
        
    xml_content += '</urlset>'
    
    return Response(content=xml_content, media_type="application/xml")

# ==================== CLOUDINARY UPLOAD & MEDIA MANAGER ====================
import cloudinary
import cloudinary.uploader
import cloudinary.api
from fastapi import File, UploadFile



@app.get("/media/images")
def get_images(current_user: models.User = Depends(get_current_user)):
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        # Fetch images from specific folder
        result = cloudinary.api.resources(
            type="upload",
            prefix="fortune-city/blogs", 
            max_results=100
        )
        return result.get("resources", [])
    except Exception as e:
        # Log error for debugging
        print(f"Cloudinary error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch images: {str(e)}")

@app.delete("/media/images/{public_id:path}")
def delete_image(public_id: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    get_cloudinary_config()
    
    try:
        # 1. Cascade Nullification: 
        # Instead of blocking, we automatically clear this image from all Blog Posts 
        # so you don't end up with broken/ghost images.
        db.query(models.BlogPost).filter(
            models.BlogPost.featured_image.like(f"%{public_id}%")
        ).update({models.BlogPost.featured_image: None}, synchronize_session=False)
        
        # Also clear from user profiles if used there
        db.query(models.User).filter(
            models.User.profile_image_public_id == public_id
        ).update({
            models.User.profile_image: None, 
            models.User.profile_image_public_id: None
        }, synchronize_session=False)

        # Also clear from Events if used there
        db.query(models.Event).filter(
            models.Event.featured_image_public_id == public_id
        ).update({
            models.Event.featured_image: None,
            models.Event.featured_image_public_id: None
        }, synchronize_session=False)

        db.commit()

        # 2. Delete from Cloudinary with full invalidation
        result = cloudinary.uploader.destroy(public_id, invalidate=True)
        
        return {
            "message": "Image deleted and references cleared", 
            "cloud_result": result.get("result")
        }
        
    except Exception as e:
        db.rollback()
        print(f"Delete Error for {public_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")

@app.post("/media/crop")
def crop_image(
    public_id: str = Form(...),
    image_url: str = Form(...),
    x: int = Form(...),
    y: int = Form(...),
    width: int = Form(...),
    height: int = Form(...),
    current_user: models.User = Depends(get_current_user)
):
    """Perform server-side crop using Cloudinary transformation and overwrite the original."""
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    get_cloudinary_config()
    
    try:
        # This is extremely fast as Cloudinary handles the fetch and crop on their end
        result = cloudinary.uploader.upload(
            image_url,
            public_id=public_id,
            overwrite=True,
            invalidate=True,
            transformation=[{
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "crop": "crop"
            }]
        )
        return {
            "public_id": result.get("public_id"),
            "secure_url": result.get("secure_url"),
            "width": result.get("width"),
            "height": result.get("height"),
            "format": result.get("format"),
            "bytes": result.get("bytes"),
            "created_at": result.get("created_at")
        }
    except Exception as e:
        print(f"Crop Error: {e}")
        raise HTTPException(status_code=500, detail=f"Server-side crop failed: {str(e)}")

@app.post("/user/profile-image")
def upload_profile_image(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Upload a profile image to Cloudinary and update user record."""
    get_cloudinary_config()
    
    try:
        # 1. Delete old image if exists
        if current_user.profile_image_public_id:
            try:
                cloudinary.uploader.destroy(current_user.profile_image_public_id)
            except Exception as e:
                print(f"Error deleting old profile image: {e}")
        
        # 2. Upload new image to profile-img folder
        # Check file size (1MB = 1024 * 1024 bytes)
        MAX_SIZE = 1 * 1024 * 1024
        file_content = file.file.read()
        if len(file_content) > MAX_SIZE:
             raise HTTPException(status_code=400, detail="File too large. Maximum size is 1MB.")
        file.file.seek(0)
        
        result = cloudinary.uploader.upload(file.file, folder="fortune-city/profile-img")
        
        # 3. Update database
        current_user.profile_image = result.get("secure_url")
        current_user.profile_image_public_id = result.get("public_id")
        db.commit()
        db.refresh(current_user)
        
        return {
            "profile_image": current_user.profile_image,
            "username": current_user.username
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile image update failed: {str(e)}")

@app.delete("/user/profile-image")
def delete_profile_image(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Remove profile image from Cloudinary and clear user record."""
    if not current_user.profile_image_public_id:
        raise HTTPException(status_code=400, detail="No profile image to remove")
    
    get_cloudinary_config()
    
    try:
        # 1. Delete from Cloudinary
        cloudinary.uploader.destroy(current_user.profile_image_public_id)
        
        # 2. Clear database fields
        current_user.profile_image = None
        current_user.profile_image_public_id = None
        db.commit()
        db.refresh(current_user)
        
        return {"message": "Profile image removed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove image: {str(e)}")

import hashlib

@app.post("/upload")
async def upload_image(
    file: UploadFile = File(...), 
    public_id: Optional[str] = Form(None),
    folder: Optional[str] = Form("blogs"),
    current_user: models.User = Depends(get_current_user)
):
    """Upload an image to Cloudinary with automatic deduplication. Optimized for speed and large files."""
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to upload files")
    
    try:
        # Read file content efficiently
        file_content = await file.read()
        await file.seek(0)
        
        is_video = "video" in folder.lower() or file.content_type.startswith("video/")
        # Images: 2MB, Videos: 50MB (increased slightly for convenience)
        MAX_SIZE = (50 if is_video else 2) * 1024 * 1024
        
        if len(file_content) > MAX_SIZE:
             size_label = "50MB" if is_video else "2MB"
             raise HTTPException(status_code=400, detail=f"File too large. Maximum size for {'videos' if is_video else 'images'} is {size_label}.")
        
        # Deduplication logic
        if not public_id:
            file_hash = hashlib.md5(file_content).hexdigest()
            base_folder = "fortune-city"
            final_folder = folder if folder.startswith(base_folder) else f"{base_folder}/{folder}"
            
            upload_params = {
                "public_id": file_hash,
                "folder": final_folder,
                "overwrite": True,
                "resource_type": "auto",
                "quality": "auto:good", # Automatic quality optimization
                "fetch_format": "auto"   # Automatic format optimization (webp/avif where supported)
            }
        else:
            upload_params = {
                "public_id": public_id,
                "overwrite": True,
                "resource_type": "auto"
            }

        # Use upload_large for anything over 10MB or videos for better reliability and speed
        if is_video or len(file_content) > 10 * 1024 * 1024:
            result = await asyncio.to_thread(
                cloudinary.uploader.upload_large,
                file.file,
                **upload_params,
                chunk_size=6000000 # 6MB chunks
            )
        else:
            result = await asyncio.to_thread(
                cloudinary.uploader.upload,
                file.file,
                **upload_params
            )
        
        return {
            "public_id": result.get("public_id"),
            "secure_url": result.get("secure_url"),
            "width": result.get("width"),
            "height": result.get("height"),
            "format": result.get("format"),
            "bytes": result.get("bytes"),
            "created_at": result.get("created_at")
        }
    except Exception as e:
        print(f"Upload Error: {e}")
        raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")

# ==================== GALLERY ENDPOINTS ====================

@app.post("/gallery", response_model=schemas.GalleryItemResponse, status_code=status.HTTP_201_CREATED)
def create_gallery_item(item: schemas.GalleryItemCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to add gallery items")
    
    new_item = models.GalleryItem(
        type=item.type,
        url=item.url,
        public_id=item.public_id,
        thumbnail_url=item.thumbnail_url,
        title=item.title
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item

@app.get("/gallery", response_model=List[schemas.GalleryItemResponse])
def get_gallery_items(type: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.GalleryItem)
    if type:
        query = query.filter(models.GalleryItem.type == type)
    return query.order_by(models.GalleryItem.order.asc(), models.GalleryItem.created_at.desc()).all()

@app.delete("/gallery/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gallery_item(item_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete gallery items")
    
    item = db.query(models.GalleryItem).filter(models.GalleryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # If it's a photo or video upload (has public_id), remove from Cloudinary
    if item.public_id:
        get_cloudinary_config()
        try:
            # Determine resource_type based on item type
            resource_type = "video" if item.type == "video" else "image"
            cloudinary.uploader.destroy(item.public_id, resource_type=resource_type, invalidate=True)
        except Exception as e:
            print(f"Error deleting from Cloudinary: {e}")
            # We continue to delete from DB even if Cloudinary fails, or maybe we should log it
            
    db.delete(item)
    db.commit()
    return None

@app.put("/gallery/{item_id}", response_model=schemas.GalleryItemResponse)
def update_gallery_item(
    item_id: int,
    item_data: schemas.GalleryItemUpdate, 
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to update gallery items")
    
    item = db.query(models.GalleryItem).filter(models.GalleryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # 1. Update Title / Alt Text
    if item_data.title is not None:
        item.title = item_data.title
    
    # 2. Handle Server-Side Cropping if provided
    # Only proceed if crop_data exists and is not empty
    if item_data.crop_data and len(item_data.crop_data) > 0 and item.public_id:
        get_cloudinary_config()
        try:
            crop = item_data.crop_data
            # Convert values to int safely
            cx = int(float(crop.get('x', 0)))
            cy = int(float(crop.get('y', 0)))
            cw = int(float(crop.get('width', 100)))
            ch = int(float(crop.get('height', 100)))

            # Revert to URL but strip versioning (/v123456789/) to avoid "Resource not found" errors
            import re
            source_url = item.url
            # Remove the version string (e.g., /v1771392831/) from the URL if present
            clean_url = re.sub(r'/v\d+/', '/', source_url)

            result = cloudinary.uploader.upload(
                clean_url,
                public_id=item.public_id,
                overwrite=True,
                invalidate=True,
                transformation=[{
                    "x": cx,
                    "y": cy,
                    "width": cw,
                    "height": ch,
                    "crop": "crop"
                }]
            )
            item.url = result.get("secure_url")
            item.public_id = result.get("public_id")
        except Exception as e:
            # Enhanced logging for debugging
            import traceback
            print(f"--- Gallery Crop Error ---")
            print(f"Item ID: {item_id}")
            print(f"Clean URL: {clean_url if 'clean_url' in locals() else 'N/A'}")
            print(f"Error: {str(e)}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Failed to apply crop: {str(e)}")
    
    db.commit()
    db.refresh(item)
    return item

@app.post("/gallery/reorder")
def reorder_gallery(id_order: List[int], current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        for index, item_id in enumerate(id_order):
            db.query(models.GalleryItem).filter(models.GalleryItem.id == item_id).update({"order": index})
        db.commit()
        return {"message": "Order updated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==================== EVENT ENDPOINTS ====================

@app.post("/events", response_model=schemas.EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(event: schemas.EventCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to create events")
    
    event_data = event.dict()
    if not event_data.get("slug"):
        # Simple slugification
        base_slug = re.sub(r'[^\w\s-]', '', event_data["title"].lower())
        base_slug = re.sub(r'[\s_-]+', '-', base_slug).strip('-')
        slug = base_slug
        counter = 1
        while db.query(models.Event).filter(models.Event.slug == slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        event_data["slug"] = slug
        
    new_event = models.Event(**event_data)
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event

@app.get("/events", response_model=List[schemas.EventResponse])
def get_events(category: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        query = db.query(models.Event)
        if category:
            query = query.filter(models.Event.category == category)
        events = query.order_by(models.Event.order.asc(), models.Event.created_at.desc()).all()
        return events
    except Exception as e:
        print(f"Error in get_events: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/events/{slug}", response_model=schemas.EventResponse)
def get_event(slug: str, db: Session = Depends(get_db)):
    # Try ID first for backward compatibility, then slug
    event = None
    if slug.isdigit():
        event = db.query(models.Event).filter(models.Event.id == int(slug)).first()
    
    if not event:
        event = db.query(models.Event).filter(models.Event.slug == slug).first()
        
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@app.put("/events/{event_id}", response_model=schemas.EventResponse)
def update_event(event_id: int, event_update: schemas.EventUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to update events")
    
    db_event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    update_data = event_update.dict(exclude_unset=True)
    
    # If a new image is being set, delete the old one from Cloudinary
    if "featured_image_public_id" in update_data and db_event.featured_image_public_id:
        if update_data["featured_image_public_id"] != db_event.featured_image_public_id:
            get_cloudinary_config()
            try:
                cloudinary.uploader.destroy(db_event.featured_image_public_id, invalidate=True)
            except Exception as e:
                print(f"Error deleting old event image from Cloudinary: {e}")

    for key, value in update_data.items():
        setattr(db_event, key, value)
    
    db.commit()
    db.refresh(db_event)
    return db_event

@app.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete events")
    
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Delete image from Cloudinary if exists
    if event.featured_image_public_id:
        get_cloudinary_config()
        try:
            cloudinary.uploader.destroy(event.featured_image_public_id, invalidate=True)
        except Exception as e:
            print(f"Error deleting event image from Cloudinary: {e}")
            
    db.delete(event)
    db.commit()
    return None

@app.get("/admin/stats", response_model=schemas.DashboardStats)
def get_dashboard_stats(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch analytics for the dashboard"""
    # Only allow admin and authorized users
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    total_posts = db.query(models.BlogPost).count()
    published_posts = db.query(models.BlogPost).filter(models.BlogPost.status == "published").count()
    total_events = db.query(models.Event).count()
    total_subscribers = db.query(models.Subscriber).count()
    total_enquiries = db.query(models.ContactEnquiry).count()
    
    return {
        "total_posts": total_posts,
        "published_posts": published_posts,
        "total_events": total_events,
        "total_subscribers": total_subscribers,
        "total_enquiries": total_enquiries
    }

@app.post("/events/reorder")
def reorder_events(id_order: List[int], current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        # Use a more efficient update method if many events, but this is fine for dozens
        for index, event_id in enumerate(id_order):
            db.query(models.Event).filter(models.Event.id == event_id).update({"order": index})
        db.commit()
        return {"message": "Order updated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

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
from dotenv import load_dotenv

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
def startup_db_client():
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
    if current_user.role not in ["admin", "editor"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    comments = db.query(models.Comment).options(joinedload(models.Comment.post)).order_by(models.Comment.created_at.desc()).all()
    return comments

@app.put("/admin/comments/{comment_id}/approve", response_model=schemas.CommentResponse)
def approve_comment(comment_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Approve a comment (requires authentication)"""
    if current_user.role not in ["admin", "editor"]:
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
    if current_user.role not in ["admin", "editor"]:
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

# Cloudinary config moved inside endpoint for hot-reload support or helper
def get_cloudinary_config():
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET")
    )

@app.get("/media/images")
def get_images(current_user: models.User = Depends(get_current_user)):
    if current_user.role not in ["admin", "editor"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    get_cloudinary_config()
    
    try:
        # Fetch images from specific folder
        # Note: listing resources might require Admin API enabled on Cloudinary console
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
    if current_user.role not in ["admin", "editor"]:
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
    if current_user.role not in ["admin", "editor"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    get_cloudinary_config()
    
    try:
        # This is extremely fast as Cloudinary handles the fetch and crop on their end
        result = cloudinary.uploader.upload(
            image_url,
            public_id=public_id,
            overwrite=True,
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
def upload_image(
    file: UploadFile = File(...), 
    public_id: Optional[str] = Form(None),
    current_user: models.User = Depends(get_current_user)
):
    """Upload an image to Cloudinary with automatic deduplication by content hashing."""
    if current_user.role not in ["admin", "editor"]:
        raise HTTPException(status_code=403, detail="Not authorized to upload files")
    
    get_cloudinary_config()
    
    try:
        # Read file content for hashing
        file_content = file.file.read()
        file.file.seek(0) # Reset to start for upload
        
        # 1. Deduplication: Use MD5 hash as public_id if none provided
        if not public_id:
            file_hash = hashlib.md5(file_content).hexdigest()
            # We prefix with hash but keep it in the blogs folder
            # Cloudinary handles overwrite=True with the same public_id
            target_public_id = f"fortune-city/blogs/{file_hash}"
        else:
            target_public_id = public_id

        upload_params = {
            "public_id": target_public_id,
            "overwrite": True,
            "resource_type": "auto"
        }

        result = cloudinary.uploader.upload(file.file, **upload_params)
        
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

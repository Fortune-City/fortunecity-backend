from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
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

load_dotenv()

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
        
    hashed_password = get_password_hash(user.password)
    new_user = models.User(
        username=user.username, 
        nickname=user.nickname,
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
        status=post.status,
        slug=post.slug,
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

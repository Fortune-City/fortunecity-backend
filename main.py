from fastapi import FastAPI, Depends, HTTPException, status, Form, File, UploadFile, BackgroundTasks
from typing import Optional, List, Union
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
import cloudinary.utils
from dotenv import load_dotenv
import string
import random
import logging
import hashlib
import re
import asyncio

from logging.handlers import RotatingFileHandler

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler("backend.log", maxBytes=10*1024*1024, backupCount=5)
    ]
)
logger = logging.getLogger("fortune-city")

load_dotenv(override=True)

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Fortune City API")

# Security & Performance Middleware Stack
# Note: Last added = first executed for requests.


# 1. CORS Policy (Outer-most for responses)
origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174")
origins = [origin.strip() for origin in origins_str.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# 2. GZip Compression
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 1. Trusted Host (Outer-most - runs first)
allowed_hosts_str = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
allowed_hosts = [host.strip() for host in allowed_hosts_str.split(",")]
# In many production environments (like AWS LB), we might need to trust the load balancer
# but strict host checking is good security practice.
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=allowed_hosts
)

# 4. Custom Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; object-src 'none';"
    return response

# Error Logging Middleware
@app.middleware("http")
async def log_requests(request, call_next):
    start_time = datetime.now()
    response = await call_next(request)
    duration = datetime.now() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} ({duration.total_seconds():.3f}s)")
    return response

# Validate essential environment variables
required_env_vars = [
    "DATABASE_URL",
    "SECRET_KEY",
    "CLOUDINARY_CLOUD_NAME",
    "CLOUDINARY_API_KEY",
    "CLOUDINARY_API_SECRET"
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    logger.warning(f"Missing environment variables: {', '.join(missing_vars)}. This may cause issues in production.")

from fastapi.responses import JSONResponse
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled Exception: {exc}")
    logger.error(traceback.format_exc())
    
    # Return 500 even if it's a validation error to prevent leaking details
    # We include CORS header manually here as exception handlers can sometimes bypass middleware
    headers = {}
    origin = request.headers.get("origin")
    if origin in origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"

    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"},
        headers=headers
    )


# Configure Cloudinary globally once
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

LOGO_URL = "https://res.cloudinary.com/doazatm15/image/upload/v1774003284/001_FC_Fortune_City_Logo_B_3_ficepn.png" # User provided logo

async def upload_logo_to_cloudinary():
    global LOGO_URL
    try:
        # Path to light mode logo in frontend assets
        logo_path = os.path.join(os.path.dirname(os.getcwd()), "frontend", "src", "assets", "light mode logo.webp")
        if os.path.exists(logo_path):
            result = cloudinary.uploader.upload(
                logo_path,
                public_id="fortune_city_email_logo",
                overwrite=True,
                folder="branding"
            )
            LOGO_URL = result.get("secure_url")
            logger.info(f"Logo uploaded to Cloudinary for emails: {LOGO_URL}")
        else:
            logger.warning(f"Logo file not found at {logo_path}, using fallback.")
    except Exception as e:
        logger.error(f"Failed to upload logo to Cloudinary: {e}")

@app.on_event("startup")
async def startup_db_client():
    # Start background cleanup task for expired events
    logger.info("Launching event cleanup background task...")
    asyncio.create_task(cleanup_expired_events_task())
    # Using specific logo URL provided by user
    # asyncio.create_task(upload_logo_to_cloudinary())
    pass

async def cleanup_expired_events_task():
    """Background task previously used to remove events, now disabled placeholder."""
    logger.info("Event cleanup background task started (Disabled).")
    while True:
        await asyncio.sleep(600)

@app.get("/search")
def search(q: str, db: Session = Depends(get_db)):
    """Search for posts and events based on query string."""
    if not q or len(q) < 2:
        return {"results": []}

    search_query = f"%{q}%"
    
    # Search Blog Posts
    posts = db.query(models.BlogPost).filter(
        (models.BlogPost.status == "published") & 
        (models.BlogPost.title.ilike(search_query) | models.BlogPost.content.ilike(search_query) | models.BlogPost.excerpt.ilike(search_query))
    ).limit(5).all()
    
    # Search Events
    events = db.query(models.Event).filter(
        models.Event.title.ilike(search_query) | models.Event.description.ilike(search_query) | models.Event.category.ilike(search_query)
    ).limit(5).all()
    
    results = []
    
    for post in posts:
        results.append({
            "id": post.id,
            "title": post.title,
            "slug": post.slug,
            "type": "blog",
            "image": post.featured_image,
            "description": post.excerpt or (post.content[:100] + "...") if post.content else ""
        })
        
    for event in events:
        results.append({
            "id": event.id,
            "title": event.title,
            "slug": event.slug,
            "type": "event",
            "image": event.featured_image,
            "description": event.description[:100] + "..." if event.description else ""
        })
        
    return {"results": results}

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
def subscribe_newsletter(subscriber: schemas.SubscriberCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Check if email exists
    existing_subscriber = db.query(models.Subscriber).filter(models.Subscriber.email == subscriber.email).first()
    if existing_subscriber:
        raise HTTPException(status_code=400, detail="Email already subscribed")
    
    new_subscriber = models.Subscriber(name=subscriber.name, email=subscriber.email, phone=subscriber.phone)
    db.add(new_subscriber)
    db.commit()
    db.refresh(new_subscriber)
    
    # Send welcome email in background
    background_tasks.add_task(send_subscriber_welcome_email, new_subscriber.email, new_subscriber.name)
    
    return new_subscriber

@app.get("/admin/subscribers", response_model=List[schemas.SubscriberResponse])
def get_subscribers(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "enquiry_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return db.query(models.Subscriber).order_by(models.Subscriber.created_at.desc()).all()

@app.delete("/admin/subscribers/{subscriber_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscriber(subscriber_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "enquiry_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    subscriber = db.query(models.Subscriber).filter(models.Subscriber.id == subscriber_id).first()
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")
        
    db.delete(subscriber)
    db.commit()
    return None

# --- Contact Enquiries ---

import urllib.request
import json
import ssl
import resend

def send_subscriber_welcome_email(email_address: str, name: str = None):
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        logger.warning("RESEND_API_KEY not found in environment")
        return
    
    resend.api_key = api_key
    from_email = "noreply@mail.fortunecity.in"
    
    try:
        display_name = name if name else "Subscriber"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 0; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #ffffff; padding: 30px; text-align: center; border-bottom: 1px solid #eee;">
                <img src="{LOGO_URL}" alt="Fortune City" style="max-height: 100px; width: auto; display: block; margin: 0 auto;">
            </div>
            <div style="padding: 30px;">
                <h2 style="color: #333; margin-top: 0;">Welcome to Fortune City!</h2>
            <p>Hi {display_name},</p>
            <p>Thank you for subscribing to our newsletter! You've successfully joined our community.</p>
            <p>You will now receive the latest updates about <strong>Fortune City</strong> and details about our upcoming events directly in your inbox.</p>
            <p>Stay tuned for exciting news!</p>
            <br>
            <br>
            <p>Best Regards,<br>The Fortune City Team</p>
            </div>
            <div style="background-color: #f8f9fa; padding: 15px; text-align: center; border-top: 1px solid #eee;">
                <p style="font-size: 12px; color: #999; margin: 0;">If you didn't mean to subscribe, please ignore this email.</p>
                <p style="font-size: 11px; color: #bbb; margin-top: 5px;">© 2026 Fortune City. All rights reserved.</p>
            </div>
        </div>
        """
        
        params = {
            "from": f"Fortune City <{from_email}>",
            "to": [email_address],
            "subject": "Thank you for subscribing to Fortune City!",
            "html": html_content,
        }
        
        max_retries = 3
        import time
        for attempt in range(max_retries):
            try:
                email = resend.Emails.send(params)
                logger.info(f"Welcome email sent to {email_address}. ID: {email.get('id')}")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                wait_time = (2 ** attempt) + 0.5
                logger.warning(f"Error sending welcome email (attempt {attempt+1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        
    except Exception as e:
        logger.error(f"Failed to send welcome email to {email_address}: {str(e)}")
        logger.error(traceback.format_exc())

def send_enquiry_email(data: dict):
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        logger.warning("RESEND_API_KEY not found in environment")
        return
    
    resend.api_key = api_key
    from_email = "noreply@mail.fortunecity.in"
    to_email = "social@texvalley.info"
    
    try:
        html_content = f"""
        <h3>New Website Enquiry</h3>
        <p><strong>Name:</strong> {data['name']}</p>
        <p><strong>Email:</strong> {data['email']}</p>
        <p><strong>Phone:</strong> {data['phone']}</p>
        <p><strong>Message:</strong></p>
        <p style="white-space: pre-wrap;">{data['message']}</p>
        <hr>
        <p><small>Enquiry ID: {data['id']} | Date: {data['date']}</small></p>
        """
        
        params = {
            "from": f"Fortune City Enquiry <{from_email}>",
            "to": [to_email],
            "subject": f"New Enquiry from {data['name']}",
            "html": html_content,
        }
        
        max_retries = 3
        import time
        for attempt in range(max_retries):
            try:
                email = resend.Emails.send(params)
                logger.info(f"Enquiry email sent successfully. ID: {email.get('id')}")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                wait_time = (2 ** attempt) + 0.5
                logger.warning(f"Error sending enquiry email (attempt {attempt+1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        
    except Exception as e:
        logger.error(f"Failed to send enquiry email via Resend: {str(e)}")
        logger.error(traceback.format_exc())

def format_time_12h(time_str):
    if not time_str:
        return ""
    try:
        # Try common formats
        for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p"):
            try:
                dt = datetime.strptime(time_str, fmt)
                return dt.strftime("%I:%M %p")
            except ValueError:
                continue
        return time_str # Return original if no format matches
    except:
        return time_str

def send_event_notification_to_subscribers(event_id: int, is_update: bool = False):
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        logger.warning("RESEND_API_KEY not found in environment")
        return
    
    db = next(get_db())
    try:
        event = db.query(models.Event).filter(models.Event.id == event_id).first()
        if not event:
            return
            
        subscribers = db.query(models.Subscriber).all()
        if not subscribers:
            return
            
        resend.api_key = api_key
        from_email = "noreply@mail.fortunecity.in"
        base_url = "https://fortunecity.in"
        
        # Format Date and Time
        date_display = event.date or event.start_date
        if event.start_date and event.end_date and event.start_date != event.end_date:
            date_display = f"{event.start_date} - {event.end_date}"
        
        time_display = event.time or ""
        if event.start_time:
            time_display = format_time_12h(event.start_time)
            if event.end_time:
                time_display += f" - {format_time_12h(event.end_time)}"
        
        subject = f"New Event: {event.title}" if not is_update else f"Event Updated: {event.title}"
        header_text = "New Event" if not is_update else "Event Updated"

        # Batch send using resend.Batch.send in chunks of 100
        batch_size = 100
        import time
        for i in range(0, len(subscribers), batch_size):
            chunk = subscribers[i:i + batch_size]
            batch_payload = []
            
            for sub in chunk:
                display_name = sub.name if sub.name else "Subscriber"
                html_content = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 0; border-radius: 8px; overflow: hidden;">
                    <div style="background-color: #ffffff; padding: 30px; text-align: center; border-bottom: 1px solid #eee;">
                        <img src="{LOGO_URL}" alt="Fortune City" style="max-height: 80px; width: auto; display: block; margin: 0 auto;">
                    </div>
                    <div style="padding: 30px;">
                        <div style="display: inline-block; background-color: {'#E0C287' if is_update else '#000'}; color: {'#000' if is_update else '#E0C287'}; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; margin-bottom: 15px; text-transform: uppercase;">
                            {header_text}
                        </div>
                        <h2 style="color: #333; margin-top: 0;">{event.title}</h2>
                        <p>Hi {display_name},</p>
                        <p>{"We are excited to announce a new event at Fortune City!" if not is_update else "An event you might be interested in has been updated with new details."}</p>
                        
                        <div style="background-color: #f9f9f9; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #E0C287;">
                            <h3 style="margin-top: 0; color: #333;">Event Details</h3>
                            <p style="margin-bottom: 8px; margin-top: 10px;"><strong>📅 Date:</strong> {date_display}</p>
                            {f'<p style="margin-bottom: 8px;"><strong>⏰ Time:</strong> {time_display}</p>' if time_display else ''}
                            <p style="margin-bottom: 8px;"><strong>📍 Location:</strong> {event.location}</p>
                            {f'<p style="margin-bottom: 8px;"><strong>🏷️ Category:</strong> {event.category}</p>' if event.category else ''}
                        </div>
                        
                        <p style="color: #555; line-height: 1.6;">{event.description[:250] + "..." if event.description and len(event.description) > 250 else event.description}</p>
                        
                        <div style="text-align: center; margin-top: 30px;">
                            <a href="{base_url}/events/{event.slug}" style="background-color: #000; color: #E0C287; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">View Full Details</a>
                        </div>
                    </div>
                    <div style="background-color: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #eee;">
                        <p style="font-size: 11px; color: #bbb; margin: 0;">© 2026 Fortune City. All rights reserved.</p>
                        <p style="font-size: 10px; color: #ccc; margin-top: 5px;">You are receiving this because you subscribed to Fortune City updates.</p>
                    </div>
                </div>
                """
                
                batch_payload.append({
                    "from": f"Fortune City <{from_email}>",
                    "to": [sub.email],
                    "subject": subject,
                    "html": html_content
                })
            
            # Send the batch with retries for transient errors
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    resend.Batch.send(batch_payload)
                    logger.info(f"Successfully sent event notification batch (size {len(batch_payload)}) starting at index {i}.")
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to send event notification batch starting at index {i} after {max_retries} attempts: {str(e)}")
                    else:
                        wait_time = (2 ** attempt) + 0.5
                        logger.warning(f"Error sending batch starting at index {i} (attempt {attempt+1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
            
            # Rate limit politeness buffer
            time.sleep(0.5)
                
        logger.info(f"Event notification blast sent for event ID {event_id} ({'Update' if is_update else 'New'}) to {len(subscribers)} subscribers.")
        
    except Exception as e:
        logger.error(f"Failed to send event notifications: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        db.close()

def trigger_google_sheet_webhook(data: dict, webhook_url: str = None):
    import urllib.request
    import urllib.parse
    import json
    import ssl
    
    if not webhook_url:
        webhook_url = os.getenv("GOOGLE_SHEET_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("Google Sheet Webhook URL not found in environment")
        return
    
    # Strip quotes if they were loaded with quotes
    if webhook_url.startswith('"') and webhook_url.endswith('"'):
        webhook_url = webhook_url[1:-1]
    if webhook_url.startswith("'") and webhook_url.endswith("'"):
        webhook_url = webhook_url[1:-1]
    
    logger.info(f"Attempting to send data to Google Sheet: {webhook_url}")
    
    # By default, we try sending as url-encoded form data first,
    # which is expected by the vast majority of standard Apps Scripts (Custom Forms, Carnival, Business).
    form_success = False
    try:
        form_data = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(
            webhook_url, 
            data=form_data, 
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )
        
        # ssl context to avoid SSL issues
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(req, timeout=15, context=ctx) as response:
            status = response.getcode()
            body = response.read().decode("utf-8")
            logger.info(f"Google Sheet (Form) Response Status: {status}")
            logger.info(f"Google Sheet (Form) Response Body: {body}")
            
            # Check if it was successful and did NOT return a JSON parsing error
            if status == 200:
                if "error" in body.lower() and ("syntax" in body.lower() or "json" in body.lower() or "unexpected token" in body.lower()):
                    logger.warning("Google Sheet script reported a JSON parsing error. Form-encoded data was likely not parsed.")
                else:
                    form_success = True
                    
    except Exception as e:
        logger.warning(f"Failed to send form-encoded data to Google Sheet: {str(e)}")
        
    # If form-encoded failed or returned a JSON/Syntax error, retry/fallback to application/json
    if not form_success:
        logger.info("Retrying/falling back to application/json...")
        try:
            json_payload = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=json_payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            # ssl context to avoid SSL issues
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            with urllib.request.urlopen(req, timeout=15, context=ctx) as response:
                status = response.getcode()
                body = response.read().decode("utf-8")
                logger.info(f"Google Sheet (JSON) Response Status: {status}")
                logger.info(f"Google Sheet (JSON) Response Body: {body}")
        except Exception as e:
            logger.error(f"Failed to send JSON payload to Google Sheet: {str(e)}")
            logger.error(traceback.format_exc())

@app.post("/contact", response_model=schemas.ContactEnquiryResponse, status_code=status.HTTP_201_CREATED)
def create_contact_enquiry(enquiry: schemas.ContactEnquiryCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    new_enquiry = models.ContactEnquiry(
        name=enquiry.name,
        email=enquiry.email,
        phone=enquiry.phone,
        message=enquiry.message
    )
    db.add(new_enquiry)
    db.commit()
    db.refresh(new_enquiry)

    enquiry_data = {
        "id": new_enquiry.id,
        "name": new_enquiry.name,
        "email": new_enquiry.email,
        "phone": new_enquiry.phone,
        "message": new_enquiry.message,
        "date": new_enquiry.created_at.isoformat()
    }
    background_tasks.add_task(trigger_google_sheet_webhook, enquiry_data)
    background_tasks.add_task(send_enquiry_email, enquiry_data)

    return new_enquiry

@app.get("/contact", response_model=List[schemas.ContactEnquiryResponse])
def get_contact_enquiries(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Only admin and enquiry manager can view enquiries
    if current_user.role not in ["admin", "enquiry_manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view enquiries"
        )
    return db.query(models.ContactEnquiry).order_by(models.ContactEnquiry.created_at.desc()).all()

@app.delete("/contact/{enquiry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact_enquiry(enquiry_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "enquiry_manager"]:
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
        tags=post.tags,
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
        logger.error(f"Cloudinary error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch images: {str(e)}")

@app.delete("/media/images/{public_id:path}")
def delete_image(public_id: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
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

        # NEW: Delete from GalleryItem if it was archived there
        db.query(models.GalleryItem).filter(
            models.GalleryItem.public_id == public_id
        ).delete(synchronize_session=False)

        db.commit()

        # 2. Delete from Cloudinary with full invalidation
        result = cloudinary.uploader.destroy(public_id, invalidate=True)
        
        return {
            "message": "Image deleted and references cleared", 
            "cloud_result": result.get("result")
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Delete Error for {public_id}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")

@app.delete("/media/delete")
def delete_image_alt(public_id: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Alternative deletion endpoint using query parameter to avoid path conversion issues."""
    return delete_image(public_id, current_user, db)

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
        logger.error(f"Crop Error: {e}")
        raise HTTPException(status_code=500, detail=f"Server-side crop failed: {str(e)}")

@app.post("/user/profile-image")
def upload_profile_image(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Upload a profile image to Cloudinary and update user record."""
    
    try:
        # 1. Delete old image if exists
        if current_user.profile_image_public_id:
            try:
                cloudinary.uploader.destroy(current_user.profile_image_public_id)
            except Exception as e:
                logger.error(f"Error deleting old profile image: {e}")
        
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
    
    try:
        # 1. Delete from Cloudinary
        cloudinary.uploader.destroy(current_user.profile_image_public_id)
        
        # 2. Clear database fields
        current_user.profile_image = None
        current_user.profile_image_public_id = None
        db.commit()
        db.refresh(current_user)
        
    except Exception as e:
        logger.error(f"Failed to remove image: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove image: {str(e)}")

@app.post("/upload")
async def upload_image(
    file: UploadFile = File(...), 
    public_id: Optional[str] = Form(None),
    folder: Optional[str] = Form("blogs"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload an image to Cloudinary. Optimized for speed and large files."""
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to upload files")
    
    try:
        is_video = "video" in folder.lower() or file.content_type.startswith("video/")
        # Limits: Images: 20MB, Videos: 100MB (Increased image limit slightly for better quality)
        MAX_SIZE = (100 if is_video else 20) * 1024 * 1024
        
        # Check size without reading everything if possible
        file.file.seek(0, 2)
        actual_size = file.file.tell()
        file.file.seek(0)

        if actual_size > MAX_SIZE:
             size_label = "100MB" if is_video else "20MB"
             raise HTTPException(status_code=400, detail=f"File too large. Maximum size for {'videos' if is_video else 'images'} is {size_label}.")
        
        # Base folder
        base_folder = "fortune-city"
        final_folder = folder if folder.startswith(base_folder) else f"{base_folder}/{folder}"

        # Initialize upload params
        upload_params = {
            "folder": final_folder,
            "overwrite": True,
            "resource_type": "image" if not is_video else "video",
        }

        # If not provided, generate a fresh name to avoid clobbering old formats
        if not public_id:
            from datetime import datetime
            import random
            timestamp = str(int(datetime.now().timestamp()))
            clean_name = "".join(c for c in file.filename if c.isalnum() or c in "._-").rstrip().split('.')[0]
            # Use random prefix to guarantee uniqueness and bypass caches
            unique_prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
            upload_params["public_id"] = f"{clean_name}_{unique_prefix}_{timestamp}"
        else:
            upload_params["public_id"] = public_id

        # Forces WEBP strictly for images
        if not is_video:
            upload_params.update({
                "format": "webp",
                "transformation": [{"quality": "auto:best", "fetch_format": "webp"}]
            })
        
        logger.info(f"Uploading {file.filename} as {upload_params.get('public_id')} to {final_folder} (is_video: {is_video})")

        # Use upload_large for large files or videos
        if is_video or actual_size > 10 * 1024 * 1024:
            result = await asyncio.to_thread(
                cloudinary.uploader.upload_large,
                file.file,
                **upload_params,
                chunk_size=6000000 
            )
        else:
            result = await asyncio.to_thread(
                cloudinary.uploader.upload,
                file.file,
                **upload_params
            )
        
        logger.info(f"Upload complete. Final format: {result.get('format')}, URL: {result.get('secure_url')}")
        
        return {
            "public_id": result.get("public_id"),
            "secure_url": result.get("secure_url"),
            "width": result.get("width"),
            "height": result.get("height"),
            "format": result.get("format"),
            "bytes": result.get("bytes"),
            "created_at": result.get("created_at")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload Error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

@app.get("/media/sign")
def sign_upload(folder: str = "blogs", public_id: Optional[str] = None, current_user: models.User = Depends(get_current_user)):
    """Generate a signed upload signature for direct browser-to-Cloudinary uploading."""
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # We use a timestamp for the signature
    import time
    timestamp = int(time.time())
    
    # Parameters to sign
    params = {
        "timestamp": timestamp,
        "folder": folder if folder.startswith("fortune-city") else f"fortune-city/{folder}"
    }
    
    if public_id:
        params["public_id"] = public_id
        
    # Generate signature using API Secret
    signature = cloudinary.utils.api_sign_request(
        params, 
        os.getenv("CLOUDINARY_API_SECRET")
    )
    
    return {
        "signature": signature,
        "timestamp": timestamp,
        "api_key": os.getenv("CLOUDINARY_API_KEY"),
        "cloud_name": os.getenv("CLOUDINARY_CLOUD_NAME"),
        "folder": params["folder"]
    }

# --- Gallery Collections ---

@app.post("/gallery/collections", response_model=schemas.GalleryCollectionResponse, status_code=status.HTTP_201_CREATED)
def create_gallery_collection(collection: schemas.GalleryCollectionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    new_collection = models.GalleryCollection(**collection.dict())
    db.add(new_collection)
    db.commit()
    db.refresh(new_collection)
    return new_collection

@app.get("/gallery/collections", response_model=List[schemas.GalleryCollectionWithItems])
def get_gallery_collections(type: Optional[str] = None, include_items: bool = False, db: Session = Depends(get_db)):
    query = db.query(models.GalleryCollection)
    if type:
        query = query.filter(models.GalleryCollection.type == type)
    
    if include_items:
        collections = query.options(joinedload(models.GalleryCollection.items)).order_by(models.GalleryCollection.order.asc(), models.GalleryCollection.created_at.desc()).all()
        # Sort items within each collection by order
        for coll in collections:
            coll.items.sort(key=lambda x: x.order)
        return collections
        
    return query.order_by(models.GalleryCollection.order.asc(), models.GalleryCollection.created_at.desc()).all()

@app.get("/gallery/collections/{collection_id}", response_model=schemas.GalleryCollectionWithItems)
def get_gallery_collection(collection_id: int, db: Session = Depends(get_db)):
    collection = db.query(models.GalleryCollection).filter(models.GalleryCollection.id == collection_id).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    # Sort items by order
    collection.items.sort(key=lambda x: x.order)
    return collection

@app.put("/gallery/collections/{collection_id}", response_model=schemas.GalleryCollectionResponse)
def update_gallery_collection(collection_id: int, collection_data: schemas.GalleryCollectionUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db_collection = db.query(models.GalleryCollection).filter(models.GalleryCollection.id == collection_id).first()
    if not db_collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    update_data = collection_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_collection, key, value)
    
    db.commit()
    db.refresh(db_collection)
    return db_collection

@app.delete("/gallery/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gallery_collection(collection_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    collection = db.query(models.GalleryCollection).filter(models.GalleryCollection.id == collection_id).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    # 1. Delete all items from Cloudinary
    for item in collection.items:
        if item.public_id:
            try:
                resource_type = "video" if item.type == "video" else "image"
                cloudinary.uploader.destroy(item.public_id, resource_type=resource_type, invalidate=True)
            except Exception as e:
                logger.error(f"Error deleting collection item from Cloudinary: {e}")
    
    # 2. Delete collection's featured image
    if collection.featured_image_public_id:
        try:
            cloudinary.uploader.destroy(collection.featured_image_public_id, invalidate=True)
        except Exception as e:
            logger.error(f"Error deleting collection featured image: {e}")
            
    db.delete(collection)
    db.commit()
    return None

@app.post("/gallery/collections/reorder")
def reorder_gallery_collections(id_order: List[int], current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        for index, coll_id in enumerate(id_order):
            db.query(models.GalleryCollection).filter(models.GalleryCollection.id == coll_id).update({"order": index})
        db.commit()
        return {"message": "Collections reordered successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

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
        title=item.title,
        collection_id=item.collection_id,
        collection_name=item.collection_name,
        event_date=item.event_date
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
    
    if item.public_id:
        try:
            # Cascade Nullification for Blog Posts
            db.query(models.BlogPost).filter(
                models.BlogPost.featured_image.like(f"%{item.public_id}%")
            ).update({models.BlogPost.featured_image: None}, synchronize_session=False)

            # Cascade for User profile if used there
            db.query(models.User).filter(
                models.User.profile_image_public_id == item.public_id
            ).update({
                models.User.profile_image: None, 
                models.User.profile_image_public_id: None
            }, synchronize_session=False)

            # Cascade for Events if used there
            db.query(models.Event).filter(
                models.Event.featured_image_public_id == item.public_id
            ).update({
                models.Event.featured_image: None,
                models.Event.featured_image_public_id: None
            }, synchronize_session=False)

            resource_type = "video" if item.type == "video" else "image"
            cloudinary.uploader.destroy(item.public_id, resource_type=resource_type, invalidate=True)
        except Exception as e:
            logger.error(f"Error during gallery item cascade/destroy from Cloudinary: {e}")
            
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
    
    # 1. Update Title / Alt Text / Collection
    if item_data.title is not None:
        item.title = item_data.title
    if item_data.collection_id is not None:
        item.collection_id = item_data.collection_id
    if item_data.collection_name is not None:
        item.collection_name = item_data.collection_name
    if item_data.event_date is not None:
        item.event_date = item_data.event_date
    
    # 2. Handle Server-Side Cropping if provided
    # Only proceed if crop_data exists and is not empty
    if item_data.crop_data and len(item_data.crop_data) > 0 and item.public_id:
        try:
            crop = item_data.crop_data
            cx = int(float(crop.get('x', 0)))
            cy = int(float(crop.get('y', 0)))
            cw = int(float(crop.get('width', 100)))
            ch = int(float(crop.get('height', 100)))

            source_url = item.url
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
            logger.exception(f"Gallery Crop Error for item {item_id}")
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
def create_event(event: schemas.EventCreate, background_tasks: BackgroundTasks, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
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
        
    if not event_data.get("end_date"):
        event_data["end_date"] = event_data.get("start_date")
        
    new_event = models.Event(**event_data)
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    
    # Notify subscribers about the new event
    background_tasks.add_task(send_event_notification_to_subscribers, new_event.id)
    
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
        logger.exception("Error in get_events")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/events/registrations", response_model=List[schemas.EventRegistrationListResponse])
def get_all_registrations(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get all event registrations for admin (requires authentication)"""
    if current_user.role not in ["admin", "editor", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    registrations = db.query(models.EventRegistration).options(joinedload(models.EventRegistration.event)).order_by(models.EventRegistration.created_at.desc()).all()
    
    # Map event_title to response
    response_data = []
    for reg in registrations:
        reg_dict = {
            "id": reg.id,
            "event_id": reg.event_id,
            "full_name": reg.full_name,
            "email": reg.email,
            "phone": reg.phone,
            "ticket_id": reg.ticket_id,
            "ticket_count": reg.ticket_count,
            "child_ticket_count": reg.child_ticket_count,
            "status": reg.status,
            "created_at": reg.created_at,
            "attendees": reg.attendees,
            "event_title": reg.event.title if reg.event else "Unknown Event"
        }
        response_data.append(reg_dict)
        
    return response_data

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
def update_event(event_id: int, event_update: schemas.EventUpdate, background_tasks: BackgroundTasks, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to update events")
    
    db_event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    update_data = event_update.dict(exclude_unset=True)
    
    # If a new image is being set, delete the old one from Cloudinary in background
    if "featured_image_public_id" in update_data and db_event.featured_image_public_id:
        if update_data["featured_image_public_id"] != db_event.featured_image_public_id:
            def delete_cloudinary_image(public_id):
                try:
                    cloudinary.uploader.destroy(public_id, invalidate=True)
                except Exception as e:
                    try:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.exception(f"Error deleting old event image from Cloudinary: {e}")
                    except:
                        print(f"Error deleting old event image from Cloudinary: {e}")
            background_tasks.add_task(delete_cloudinary_image, db_event.featured_image_public_id)

    for key, value in update_data.items():
        setattr(db_event, key, value)
    
    db.commit()
    db.refresh(db_event)
    
    # Notify subscribers about the update
    background_tasks.add_task(send_event_notification_to_subscribers, db_event.id, True)
    
    return db_event

@app.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, background_tasks: BackgroundTasks, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete events")
    
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Delete image from Cloudinary in background to prevent blocking
    if event.featured_image_public_id:
        def delete_cloudinary_image(public_id):
            try:
                cloudinary.uploader.destroy(public_id, invalidate=True)
            except Exception as e:
                try:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.exception(f"Error deleting event image from Cloudinary: {e}")
                except:
                    print(f"Error deleting event image from Cloudinary: {e}")
                    
        background_tasks.add_task(delete_cloudinary_image, event.featured_image_public_id)
            
    db.delete(event)
    db.commit()
    return None

# ==================== EVENT REGISTRATION ENDPOINTS ====================

@app.post("/events/{event_id}/register", response_model=schemas.EventRegistrationResponse, status_code=status.HTTP_201_CREATED)
def register_for_event(event_id: int, registration: schemas.EventRegistrationCreate, db: Session = Depends(get_db)):
    """Register for an event (public endpoint)"""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    if not event.is_registration_enabled:
        raise HTTPException(status_code=400, detail="Registration is not enabled for this event")
    
    # Check max attendees if set
    if event.max_attendees:
        current_registrations = db.query(models.EventRegistration).filter(
            models.EventRegistration.event_id == event_id,
            models.EventRegistration.status == "confirmed"
        ).count()
        
        if current_registrations >= event.max_attendees:
            raise HTTPException(status_code=400, detail="Event is already full")

    # Generate a unique ticket ID (e.g., FC-A8B291)
    def generate_ticket_id():
        chars = string.ascii_uppercase + string.digits
        return "FC-" + "".join(random.choices(chars, k=6))
    
    ticket_id = generate_ticket_id()
    # Ensure it's unique
    while db.query(models.EventRegistration).filter(models.EventRegistration.ticket_id == ticket_id).first():
        ticket_id = generate_ticket_id()

    new_reg = models.EventRegistration(
        event_id=event_id,
        full_name=registration.full_name,
        email=registration.email,
        phone=registration.phone,
        ticket_id=ticket_id,
        ticket_count=registration.ticket_count,
        child_ticket_count=registration.child_ticket_count,
        status="confirmed"
    )
    
    db.add(new_reg)
    db.flush() # Get the registration ID before committing

    # Add individual attendees if provided
    if registration.attendees:
        for attendee_data in registration.attendees:
            new_attendee = models.Attendee(
                registration_id=new_reg.id,
                name=attendee_data.name,
                dob=attendee_data.dob,
                category=attendee_data.category
            )
            db.add(new_attendee)

    db.commit()
    db.refresh(new_reg)
    return new_reg

@app.get("/admin/events/{event_id}/registrations", response_model=List[schemas.EventRegistrationResponse])
def get_event_registrations(event_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get all registrations for a specific event (admin only)"""
    if current_user.role not in ["admin", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    return db.query(models.EventRegistration).filter(models.EventRegistration.event_id == event_id).all()

@app.delete("/admin/registrations/{registration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_registration(registration_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a registration (admin only)"""
    if current_user.role not in ["admin", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    reg = db.query(models.EventRegistration).filter(models.EventRegistration.id == registration_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found")
        
    db.delete(reg)
    db.commit()
    return None

@app.post("/business-enquiry/submit", status_code=status.HTTP_200_OK)
def submit_business_enquiry(enquiry_data: dict, background_tasks: BackgroundTasks):
    """Submit a business enquiry and save to Google Sheet, bypassing PostgreSQL."""
    enquiry_data["date"] = datetime.now().isoformat()
    webhook_url = os.getenv("BUSINESS_ENQUIRY_WEBHOOK_URL")
    
    # Smart fallback to primary GOOGLE_SHEET_WEBHOOK_URL if specific is not configured or placeholder
    if not webhook_url or "PLACEHOLDER" in webhook_url:
        webhook_url = os.getenv("GOOGLE_SHEET_WEBHOOK_URL")
        
    background_tasks.add_task(trigger_google_sheet_webhook, enquiry_data, webhook_url)
    return {"status": "success", "message": "Enquiry submitted to Google Sheet"}

@app.get("/admin/stats", response_model=schemas.DashboardStats)
def get_dashboard_stats(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch analytics for the dashboard"""
    # Only allow admin and authorized users
    if current_user.role not in ["admin", "editor", "events_manager", "enquiry_manager", "theater_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    total_posts = db.query(models.BlogPost).count()
    published_posts = db.query(models.BlogPost).filter(models.BlogPost.status == "published").count()
    total_events = db.query(models.Event).count()
    total_subscribers = db.query(models.Subscriber).count()
    total_enquiries = db.query(models.ContactEnquiry).count()
    total_registrations = db.query(models.EventRegistration).count()
    
    return {
        "total_posts": total_posts,
        "published_posts": published_posts,
        "total_events": total_events,
        "total_subscribers": total_subscribers,
        "total_enquiries": total_enquiries,
        "total_registrations": total_registrations
    }

@app.post("/events/reorder")
def reorder_events(id_order: List[int], current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "events_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        for index, event_id in enumerate(id_order):
            db.query(models.Event).filter(models.Event.id == event_id).update({"order": index})
        db.commit()
        return {"message": "Events reordered successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==================== THEATER & MOVIE ENDPOINTS ====================

@app.get("/theaters", response_model=List[schemas.TheaterResponse])
def get_theaters(db: Session = Depends(get_db)):
    """Fetch all theaters."""
    return db.query(models.Theater).all()

@app.get("/theaters/{theater_id}/movies", response_model=List[schemas.MovieResponse])
def get_theater_movies(theater_id: int, db: Session = Depends(get_db)):
    """Fetch all movies for a specific theater."""
    return db.query(models.Movie).filter(models.Movie.theater_id == theater_id).all()

@app.post("/movies", response_model=schemas.MovieResponse)
async def create_movie(
    theater_id: int = Form(...),
    title: str = Form(...),
    screen_number: int = Form(...),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    show_timings: str = Form(...), # Expecting JSON string of list
    booking_link: Optional[str] = Form(None),
    status: str = Form("active"),
    poster: UploadFile = File(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a new movie with poster upload (restricted to admin/theater_manager)."""
    if current_user.role not in ["admin", "theater_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    import json
    try:
        timings = json.loads(show_timings)
    except:
        timings = [t.strip() for t in show_timings.split(",") if t.strip()]

    poster_url = None
    poster_public_id = None

    if poster:
        # 1MB size limit check
        contents = await poster.read()
        if len(contents) > 1 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Poster size must be less than 1MB")
        await poster.seek(0)

        try:
            # Upload with auto-conversion to WebP
            upload_result = cloudinary.uploader.upload(
                poster.file,
                folder="fortune-city/movies",
                format="webp"
            )
            poster_url = upload_result.get("secure_url")
            poster_public_id = upload_result.get("public_id")
        except Exception as e:
            logger.error(f"Poster upload failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload poster")

    new_movie = models.Movie(
        theater_id=theater_id,
        title=title,
        screen_number=screen_number,
        start_date=start_date,
        end_date=end_date,
        show_timings=timings,
        booking_link=booking_link,
        status=status,
        poster_url=poster_url,
        poster_public_id=poster_public_id
    )
    db.add(new_movie)
    db.commit()
    db.refresh(new_movie)
    return new_movie

@app.put("/movies/{movie_id}", response_model=schemas.MovieResponse)
async def update_movie(
    movie_id: int,
    theater_id: Optional[int] = Form(None),
    title: Optional[str] = Form(None),
    screen_number: Optional[int] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    show_timings: Optional[str] = Form(None),
    booking_link: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    poster: UploadFile = File(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing movie (restricted to admin/theater_manager)."""
    if current_user.role not in ["admin", "theater_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db_movie = db.query(models.Movie).filter(models.Movie.id == movie_id).first()
    if not db_movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    if theater_id is not None: db_movie.theater_id = theater_id
    if title is not None: db_movie.title = title
    if screen_number is not None: db_movie.screen_number = screen_number
    if start_date is not None: db_movie.start_date = start_date
    if end_date is not None: db_movie.end_date = end_date
    if status is not None: db_movie.status = status
    if booking_link is not None: db_movie.booking_link = booking_link
    
    if show_timings is not None:
        import json
        try:
            db_movie.show_timings = json.loads(show_timings)
        except:
            db_movie.show_timings = [t.strip() for t in show_timings.split(",") if t.strip()]

    if poster:
        # 1MB size limit check
        contents = await poster.read()
        if len(contents) > 1 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Poster size must be less than 1MB")
        await poster.seek(0)

        try:
            # Delete old poster if exists
            if db_movie.poster_public_id:
                cloudinary.uploader.destroy(db_movie.poster_public_id)
            
            # Upload new poster with auto-conversion to WebP
            upload_result = cloudinary.uploader.upload(
                poster.file,
                folder="fortune-city/movies",
                format="webp"
            )
            db_movie.poster_url = upload_result.get("secure_url")
            db_movie.poster_public_id = upload_result.get("public_id")
        except Exception as e:
            logger.error(f"Poster update failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload new poster")

    db.commit()
    db.refresh(db_movie)
    return db_movie

@app.delete("/movies/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_movie(movie_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a movie (restricted to admin/theater_manager)."""
    if current_user.role not in ["admin", "theater_manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    movie = db.query(models.Movie).filter(models.Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    # Delete from Cloudinary
    if movie.poster_public_id:
        try:
            cloudinary.uploader.destroy(movie.poster_public_id)
        except:
            pass
            
    db.delete(movie)
    db.commit()
    return None

def seed_theaters(db: Session):
    """Seed initial theaters if they don't exist."""
    theaters = [
        {"name": "Picture Time", "screens_count": 4},
        {"name": "Pride Cinemas", "screens_count": 9}
    ]
    for t_data in theaters:
        exists = db.query(models.Theater).filter(models.Theater.name == t_data["name"]).first()
        if not exists:
            new_t = models.Theater(name=t_data["name"], screens_count=t_data["screens_count"])
            db.add(new_t)
    db.commit()


# --- Custom Forms API ---

@app.post("/custom-forms", response_model=schemas.CustomFormResponse)
def create_or_update_custom_form(
    form_data: schemas.CustomFormCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create or update a custom form (restricted to admin)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    existing_form = db.query(models.CustomForm).filter(models.CustomForm.slug == form_data.slug).first()
    
    if existing_form:
        existing_form.title = form_data.title
        existing_form.description = form_data.description
        existing_form.fields = form_data.fields
        existing_form.webhook_url = form_data.webhook_url
        db.commit()
        db.refresh(existing_form)
        return existing_form
    else:
        new_form = models.CustomForm(
            title=form_data.title,
            slug=form_data.slug,
            description=form_data.description,
            fields=form_data.fields,
            webhook_url=form_data.webhook_url
        )
        db.add(new_form)
        db.commit()
        db.refresh(new_form)
        return new_form

@app.get("/custom-forms", response_model=List[schemas.CustomFormResponse])
def get_custom_forms(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all custom forms (restricted to admin)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    return db.query(models.CustomForm).order_by(models.CustomForm.created_at.desc()).all()

@app.get("/custom-forms/public/{slug}", response_model=schemas.CustomFormResponse)
def get_custom_form_by_slug(slug: str, db: Session = Depends(get_db)):
    """Fetch a single custom form by slug (public endpoint for frontend)."""
    form = db.query(models.CustomForm).filter(models.CustomForm.slug == slug).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    return form

@app.post("/custom-forms/public/{slug}/submit")
def submit_custom_form(
    slug: str,
    submission_data: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Handle custom form submissions from the frontend (public endpoint)."""
    form = db.query(models.CustomForm).filter(models.CustomForm.slug == slug).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    logger.info(f"Custom form submission for '{form.title}' (slug: {slug}): {submission_data}")
    
    # Forward the submission to Google Sheets using the form's custom webhook URL,
    # falling back to the default GOOGLE_SHEET_WEBHOOK_URL from environment
    webhook_url = form.webhook_url or os.getenv("GOOGLE_SHEET_WEBHOOK_URL")
    if webhook_url:
        background_tasks.add_task(trigger_google_sheet_webhook, submission_data, webhook_url)
        
    return {"message": "Form submitted successfully!", "title": form.title}

@app.delete("/custom-forms/{form_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_form(
    form_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a custom form by ID (restricted to admin)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    form = db.query(models.CustomForm).filter(models.CustomForm.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    db.delete(form)
    db.commit()
    return None


@app.on_event("startup")
async def startup_event():
    db = next(get_db())
    try:
        seed_theaters(db)
        logger.info("Theaters seeded successfully.")
    finally:
        db.close()


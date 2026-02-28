from sqlalchemy import Boolean, Column, Integer, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    nickname = Column(String, nullable=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    role = Column(String, default="admin")
    last_login = Column(DateTime, nullable=True)
    profile_image = Column(String, nullable=True)
    profile_image_public_id = Column(String, nullable=True)

class ContactEnquiry(Base):
    __tablename__ = "contact_enquiries"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, index=True)
    phone = Column(String)
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class BlogPost(Base):
    __tablename__ = "blog_posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    slug = Column(String, unique=True, index=True)
    content = Column(Text)
    excerpt = Column(Text, nullable=True)
    featured_image = Column(String, nullable=True)
    featured_image_alt = Column(String, nullable=True)
    status = Column(String, default="draft", index=True) # draft, published, trash
    author_id = Column(Integer, index=True)
    seo_data = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")

class Comment(Base):
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("blog_posts.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=True)
    message = Column(Text, nullable=False)
    status = Column(String(20), default="pending")  # pending, approved, rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    post = relationship("BlogPost", back_populates="comments")

class Subscriber(Base):
    __tablename__ = "subscribers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class GalleryCollection(Base):
    __tablename__ = "gallery_collections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    date = Column(String, nullable=True)
    type = Column(String, default="photo", index=True) # photo or video
    featured_image = Column(String, nullable=True)
    featured_image_public_id = Column(String, nullable=True)
    order = Column(Integer, default=0, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("GalleryItem", back_populates="collection", cascade="all, delete-orphan")

class GalleryItem(Base):
    __tablename__ = "gallery_items"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("gallery_collections.id", ondelete="CASCADE"), nullable=True)
    type = Column(String, default="photo", index=True)  # photo, video
    url = Column(String, nullable=False)    # Cloudinary URL or Video Link
    public_id = Column(String, nullable=True) # Cloudinary Public ID
    thumbnail_url = Column(String, nullable=True) # For videos
    title = Column(String, nullable=True)
    collection_name = Column(String, nullable=True)
    event_date = Column(String, nullable=True)
    order = Column(Integer, default=0, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    collection = relationship("GalleryCollection", back_populates="items")

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    slug = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    date = Column(String, nullable=True) # Keeping for backward compatibility if needed
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    start_time = Column(String, nullable=True)
    end_time = Column(String, nullable=True)
    time = Column(String, nullable=True)
    location = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    map_url = Column(Text, nullable=True)
    featured_image = Column(String, nullable=True)
    featured_image_public_id = Column(String, nullable=True)
    organizer_name = Column(String, nullable=True)
    organizer_phone = Column(String, nullable=True)
    organizer_email = Column(String, nullable=True)
    category = Column(String, default="ENTERTAINMENT", index=True)
    order = Column(Integer, default=0, index=True)
    
    # Registration Settings
    is_registration_enabled = Column(Boolean, default=False)
    registration_fee = Column(String, nullable=True, default="0")
    child_registration_fee = Column(String, nullable=True, default="0")
    child_age_limit = Column(String, nullable=True)
    registration_start_date = Column(String, nullable=True)
    registration_end_date = Column(String, nullable=True)
    max_attendees = Column(Integer, nullable=True)
    external_registration_url = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    registrations = relationship("EventRegistration", back_populates="event", cascade="all, delete-orphan")

class EventRegistration(Base):
    __tablename__ = "event_registrations"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    full_name = Column(String, index=True)
    email = Column(String, index=True)
    phone = Column(String)
    ticket_id = Column(String, unique=True, index=True, nullable=True)
    ticket_count = Column(Integer, default=1)
    child_ticket_count = Column(Integer, default=0)
    status = Column(String, default="confirmed") # confirmed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    event = relationship("Event", back_populates="registrations")
    attendees = relationship("Attendee", back_populates="registration", cascade="all, delete-orphan")

class Attendee(Base):
    __tablename__ = "event_attendees"

    id = Column(Integer, primary_key=True, index=True)
    registration_id = Column(Integer, ForeignKey("event_registrations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String)
    dob = Column(String)
    category = Column(String) # 'adult' or 'child'
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    registration = relationship("EventRegistration", back_populates="attendees")

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, date

class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    nickname: Optional[str] = None
    password: str
    role: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

class UserResponse(BaseModel):
    username: str
    nickname: Optional[str] = None
    role: str
    is_active: bool
    last_login: Optional[datetime] = None
    profile_image: Optional[str] = None

    class Config:
        from_attributes = True

class ContactEnquiryBase(BaseModel):
    name: str
    email: str
    phone: str
    message: str

class ContactEnquiryCreate(ContactEnquiryBase):
    pass

class ContactEnquiryResponse(ContactEnquiryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class BlogPostBase(BaseModel):
    title: str
    content: str
    excerpt: Optional[str] = None
    featured_image: Optional[str] = None
    featured_image_alt: Optional[str] = None
    status: Optional[str] = "draft"
    slug: Optional[str] = None
    tags: Optional[List[str]] = []
    seo: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

class BlogPostCreate(BlogPostBase):
    pass

class BlogPostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    excerpt: Optional[str] = None
    featured_image: Optional[str] = None
    featured_image_alt: Optional[str] = None
    status: Optional[str] = None
    slug: Optional[str] = None
    tags: Optional[List[str]] = None
    seo: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

class BlogPostResponse(BlogPostBase):
    id: int
    author_id: int
    created_at: datetime
    updated_at: datetime
    seo: Optional[Dict[str, Any]] = Field(None, alias="seo_data")
    tags: Optional[List[str]] = []

    class Config:
        from_attributes = True
        populate_by_name = True

# Comment Schemas
class CommentBase(BaseModel):
    name: str
    email: str
    phone_number: Optional[str] = None # Make optional as we removed it from frontend
    message: str

class CommentCreate(CommentBase):
    post_id: int

class CommentUpdate(BaseModel):
    status: str  # pending, approved, rejected

class BlogPostSummary(BaseModel):
    title: str
    slug: Optional[str] = None
    
    class Config:
        from_attributes = True

class CommentResponse(CommentBase):
    id: int
    post_id: int
    status: str
    created_at: datetime
    post: Optional[BlogPostSummary] = None

    class Config:
        from_attributes = True


# Subscriber Schemas
class SubscriberBase(BaseModel):
    name: str = Field(..., min_length=1)
    email: str = Field(..., pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    phone: Optional[str] = None

class SubscriberCreate(SubscriberBase):
    pass

class SubscriberResponse(SubscriberBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Gallery Schemas
class GalleryCollectionBase(BaseModel):
    name: str
    description: Optional[str] = None
    date: Optional[str] = None
    type: str = "photo" # photo, video
    featured_image: Optional[str] = None
    featured_image_public_id: Optional[str] = None
    order: int = 0

class GalleryCollectionCreate(GalleryCollectionBase):
    pass

class GalleryCollectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None
    type: Optional[str] = None
    featured_image: Optional[str] = None
    featured_image_public_id: Optional[str] = None
    order: Optional[int] = None

class GalleryCollectionResponse(GalleryCollectionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class GalleryItemBase(BaseModel):
    type: str = "photo" # photo, video
    url: str
    public_id: Optional[str] = None
    thumbnail_url: Optional[str] = None # For videos
    title: Optional[str] = None
    collection_id: Optional[int] = None
    collection_name: Optional[str] = None
    event_date: Optional[str] = None
    order: int = 0

class GalleryItemCreate(GalleryItemBase):
    pass

class GalleryItemUpdate(BaseModel):
    title: Optional[str] = None
    collection_id: Optional[int] = None
    collection_name: Optional[str] = None
    event_date: Optional[str] = None
    url: Optional[str] = None
    public_id: Optional[str] = None
    crop_data: Optional[dict] = None # {x, y, width, height}

class GalleryItemResponse(GalleryItemBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class GalleryCollectionWithItems(GalleryCollectionResponse):
    items: List[GalleryItemResponse] = []

    class Config:
        from_attributes = True

# Event Schemas
class EventBase(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    featured_image: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    location: Optional[str] = None
    address: Optional[str] = None
    map_url: Optional[str] = None
    featured_image_public_id: Optional[str] = None
    featured_image_alt: Optional[str] = None
    organizer_name: Optional[str] = None
    organizer_phone: Optional[str] = None
    organizer_email: Optional[str] = None
    category: Optional[str] = "ENTERTAINMENT"
    order: Optional[int] = 0
    is_registration_enabled: Optional[bool] = False
    registration_fee: Optional[str] = "0"
    child_registration_fee: Optional[str] = "0"
    child_age_limit: Optional[str] = None
    registration_start_date: Optional[str] = None
    registration_end_date: Optional[str] = None
    max_attendees: Optional[int] = None
    external_registration_url: Optional[str] = None

class EventCreate(EventBase):
    title: str
    description: str
    start_date: str
    end_date: Optional[str] = None
    featured_image: str

class EventUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    featured_image: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    location: Optional[str] = None
    address: Optional[str] = None
    map_url: Optional[str] = None
    featured_image_public_id: Optional[str] = None
    featured_image_alt: Optional[str] = None
    organizer_name: Optional[str] = None
    organizer_phone: Optional[str] = None
    organizer_email: Optional[str] = None
    category: Optional[str] = None
    order: Optional[int] = None
    is_registration_enabled: Optional[bool] = None
    registration_fee: Optional[str] = None
    child_registration_fee: Optional[str] = None
    child_age_limit: Optional[str] = None
    registration_start_date: Optional[str] = None
    registration_end_date: Optional[str] = None
    max_attendees: Optional[int] = None
    external_registration_url: Optional[str] = None

class EventResponse(EventBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Attendee Schemas
class AttendeeBase(BaseModel):
    name: str
    dob: str
    category: str # 'adult' or 'child'

class AttendeeCreate(AttendeeBase):
    pass

class AttendeeResponse(AttendeeBase):
    id: int
    registration_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Event Registration Schemas
class EventRegistrationBase(BaseModel):
    full_name: str
    email: str
    phone: str
    ticket_count: Optional[int] = 1
    child_ticket_count: Optional[int] = 0

class EventRegistrationCreate(EventRegistrationBase):
    attendees: Optional[List[AttendeeCreate]] = []

class EventRegistrationResponse(EventRegistrationBase):
    id: int
    event_id: int
    ticket_id: Optional[str] = None
    status: str
    created_at: datetime
    attendees: List[AttendeeResponse] = []

    class Config:
        from_attributes = True

class EventRegistrationListResponse(EventRegistrationResponse):
    event_title: Optional[str] = None

class DashboardStats(BaseModel):
    total_posts: int
    published_posts: int
    total_events: int
    total_subscribers: int
    total_enquiries: int
    total_registrations: int

# Theater & Movie Schemas
class TheaterBase(BaseModel):
    name: str
    screens_count: int

class TheaterResponse(TheaterBase):
    id: int

    class Config:
        from_attributes = True

class MovieBase(BaseModel):
    theater_id: int
    title: str
    poster_url: Optional[str] = None
    poster_public_id: Optional[str] = None
    screen_number: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    show_timings: List[str] = []
    booking_link: Optional[str] = None
    status: str = "active"

class MovieCreate(MovieBase):
    pass

class MovieUpdate(BaseModel):
    title: Optional[str] = None
    poster_url: Optional[str] = None
    poster_public_id: Optional[str] = None
    screen_number: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    show_timings: Optional[List[str]] = None
    booking_link: Optional[str] = None
    status: Optional[str] = None

class MovieResponse(MovieBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

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
    seo: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

class BlogPostResponse(BlogPostBase):
    id: int
    author_id: int
    created_at: datetime
    updated_at: datetime
    seo: Optional[Dict[str, Any]] = Field(None, alias="seo_data")

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


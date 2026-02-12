from pydantic import BaseModel
from typing import Optional
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

    class Config:
        orm_mode = True

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
        orm_mode = True

class BlogPostBase(BaseModel):
    title: str
    content: str
    excerpt: Optional[str] = None
    featured_image: Optional[str] = None
    status: Optional[str] = "draft"
    slug: Optional[str] = None
    created_at: Optional[datetime] = None

class BlogPostCreate(BlogPostBase):
    pass

class BlogPostUpdate(BlogPostBase):
    title: Optional[str] = None
    content: Optional[str] = None

class BlogPostResponse(BlogPostBase):
    id: int
    author_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

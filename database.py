from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Default to a local postgres url if not set in .env
# format: postgresql://user:password@server/db
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be set in environment variables")

# Optimization: Connection pooling limits to prevent backend from overwhelming the DB
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,      # Maintain 20 connections in the pool
    max_overflow=10,   # Allow 10 extra connections during spikes
    pool_pre_ping=True # Verify connection before usage (prevents stale connection errors)
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

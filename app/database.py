from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from typing import Generator
from app.core.config import Settings

# Database configuration with smart environment detection
settings = Settings()
DATABASE_URL = os.getenv("DATABASE_URL") or settings.default_database_url

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """Tables are created by init-db.sql during container startup"""
    pass


def get_db() -> Generator:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
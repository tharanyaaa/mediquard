"""
Database configuration for Fake Medicine Checker MVP.
Using SQLite for lightweight, standalone operation.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Database file in the backend directory
DB_PATH = os.path.join(os.path.dirname(__file__), "medicines.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# connect_args={"check_same_thread": False} is required for SQLite in multithreaded FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for getting a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""
SQLAlchemy database models for Fake Medicine Checker.
All sample medicine records are fake/demonstration records.
"""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from .database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Medicine(Base):
    """
    Verified medicine registry table.
    Stores manufacturer-approved batch numbers and product specifications.
    """
    __tablename__ = "medicines"

    id = Column(Integer, primary_key=True, index=True)
    brand_name = Column(String(100), index=True, nullable=False)
    salt_composition = Column(String(200), nullable=False)
    manufacturer = Column(String(150), nullable=False)
    # Comma-separated list of valid batch numbers produced by this manufacturer
    valid_batches = Column(Text, nullable=False)
    # Standard official expiry date for current batches (YYYY-MM-DD)
    expiry_date = Column(String(20), nullable=False)
    mrp = Column(Float, nullable=False, default=0.0)
    generic_name = Column(String(150), nullable=True)
    generic_price = Column(Float, nullable=True, default=0.0)
    
    # Medicine card info (no dosage information per safety guidelines)
    uses = Column(Text, nullable=True)
    side_effects = Column(Text, nullable=True)
    avoid_mix = Column(Text, nullable=True)
    storage_tips = Column(Text, nullable=True)
    
    is_flagged_fake = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)


class CommunityReport(Base):
    """
    Reports submitted by citizens, patients, and pharmacists for suspicious batches.
    """
    __tablename__ = "community_reports"

    id = Column(Integer, primary_key=True, index=True)
    batch_number = Column(String(100), index=True, nullable=False)
    brand_name = Column(String(100), nullable=True)
    manufacturer = Column(String(150), nullable=True)
    district = Column(String(100), nullable=False)
    note = Column(Text, nullable=True)
    photo_url = Column(String(255), nullable=True)
    reported_at = Column(DateTime, default=utc_now)


class CabinetItem(Base):
    """
    Personal medicine cabinet for user's verified or saved medicines.
    """
    __tablename__ = "cabinet_items"

    id = Column(Integer, primary_key=True, index=True)
    brand_name = Column(String(100), nullable=False)
    batch_number = Column(String(100), nullable=False)
    expiry_date = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="GREEN")
    user_note = Column(String(255), nullable=True)
    added_at = Column(DateTime, default=utc_now)

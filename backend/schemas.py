"""
Pydantic schemas for request validation and response serialization.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class MedicineCheckRequest(BaseModel):
    """
    Payload for POST /api/check
    Accepts typed data or OCR-extracted data.
    """
    batch_number: str = Field(..., min_length=1, description="Batch / Lot number from medicine packaging")
    brand_name: Optional[str] = Field(None, description="Brand name if visible")
    expiry_date: Optional[str] = Field(None, description="Expiry date string (e.g. 2026-10-31 or 10/26)")
    manufacturer: Optional[str] = Field(None, description="Manufacturer name if visible")


class MedicineDetails(BaseModel):
    """Product specifications and safety info."""
    brand_name: str
    salt_composition: str
    manufacturer: str
    official_expiry: str
    mrp: float
    generic_name: Optional[str] = None
    generic_price: Optional[float] = None
    uses: Optional[str] = None
    side_effects: Optional[str] = None
    avoid_mix: Optional[str] = None
    storage_tips: Optional[str] = None


class MedicineCheckResponse(BaseModel):
    """
    Standardized verdict output: GREEN, YELLOW, or RED.
    Always includes clear reasons and safe next steps.
    """
    status: str = Field(..., description="GREEN | YELLOW | RED")
    title: str
    reasons: List[str]
    next_steps: str
    report_count: int = 0
    medicine_details: Optional[MedicineDetails] = None
    checked_at: str


class OCRResultResponse(BaseModel):
    """Response returned when an image is processed for text extraction."""
    raw_text: str
    extracted_batch: Optional[str] = None
    extracted_expiry: Optional[str] = None
    extracted_mrp: Optional[str] = None
    extracted_brand: Optional[str] = None
    ocr_available: bool = True
    notice: Optional[str] = None


class ReportCreate(BaseModel):
    """Report submission payload."""
    batch_number: str
    brand_name: Optional[str] = None
    manufacturer: Optional[str] = None
    district: str
    note: Optional[str] = None


class ReportResponse(BaseModel):
    """Response after reporting suspicious medicine."""
    id: int
    message: str
    inspector_email_link: str
    inspector_whatsapp_link: str


class CabinetCreate(BaseModel):
    """Saving to medicine cabinet."""
    brand_name: str
    batch_number: str
    expiry_date: str
    status: str
    user_note: Optional[str] = None


class CabinetResponse(BaseModel):
    """Cabinet item with calculated expiry days remaining."""
    id: int
    brand_name: str
    batch_number: str
    expiry_date: str
    status: str
    user_note: Optional[str] = None
    days_until_expiry: int
    is_expired: bool
    added_at: str

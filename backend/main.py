"""
FastAPI Backend for Fake Medicine Checker MVP.

Target Users: Rural, elders, low literacy.
Goal: Provide clear, non-technical GREEN / YELLOW / RED verdicts within seconds.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import CommunityReport, Medicine
from .ocr import extract_text_from_image, parse_medicine_text
from .rules import (
    compute_final_verdict,
    evaluate_community_reports,
    evaluate_expiry,
    evaluate_registry,
    parse_expiry_date,
)
from .schemas import (
    MedicineCheckRequest,
    MedicineCheckResponse,
    MedicineDetails,
    OCRResultResponse,
)
from .seed import seed_database


# Initialize database schema and ensure initial demo data is present
Base.metadata.create_all(bind=engine)
seed_database()

app = FastAPI(
    title="Fake Medicine Checker API",
    description="Mobile-friendly hackathon MVP to check whether a medicine looks genuine, suspicious, or likely fake.",
    version="1.0.0",
)

# Enable CORS for frontend Vite development and cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    """Health check endpoint."""
    return {
        "app": "Fake Medicine Checker API",
        "status": "online",
        "version": "1.0.0",
        "disclaimer": "This application does not replace a doctor or pharmacist. All demo data is fictional."
    }


@app.post("/api/seed")
def trigger_seed():
    """Admin endpoint to re-seed or reset demo data."""
    seed_database()
    return {"message": "Demo database successfully re-seeded with 30 sample medicines and reports."}


@app.get("/api/medicines")
def list_medicines(db: Session = Depends(get_db)):
    """Returns list of registered demo medicines (useful for demo buttons & autocompletion)."""
    meds = db.query(Medicine).all()
    return [
        {
            "id": m.id,
            "brand_name": m.brand_name,
            "salt_composition": m.salt_composition,
            "manufacturer": m.manufacturer,
            "valid_batches": [b.strip() for b in m.valid_batches.split(",")],
            "expiry_date": m.expiry_date,
            "mrp": m.mrp,
            "generic_name": m.generic_name,
            "generic_price": m.generic_price,
            "is_flagged_fake": m.is_flagged_fake,
        }
        for m in meds
    ]


@app.post("/api/ocr", response_model=OCRResultResponse)
async def process_ocr(file: UploadFile = File(...)):
    """
    Upload an image of a medicine blister pack or packaging.
    Extracts text using Tesseract (with graceful fallback if not installed).
    """
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image uploaded.")

    success, raw_text, notice = extract_text_from_image(image_bytes)
    parsed = parse_medicine_text(raw_text)

    return OCRResultResponse(
        raw_text=raw_text,
        extracted_batch=parsed.get("batch_number"),
        extracted_expiry=parsed.get("expiry_date"),
        extracted_mrp=parsed.get("mrp"),
        extracted_brand=parsed.get("brand_name"),
        ocr_available=success,
        notice=notice,
    )


@app.post("/api/check", response_model=MedicineCheckResponse)
def check_medicine(req: MedicineCheckRequest, db: Session = Depends(get_db)):
    """
    Core verification endpoint.
    Accepts: batch_number (required), brand_name, expiry_date, manufacturer.
    
    Evaluates:
    1. Expiry check against current date
    2. Batch & manufacturer match against official registry
    3. Community report count for this batch
    
    Returns:
    - GREEN: Looks genuine
    - YELLOW: Suspicious, verify with pharmacist
    - RED: Expired or likely fake
    """
    clean_batch = req.batch_number.strip().upper()
    reasons: List[str] = []

    # 1. Lookup medicine in DB if brand provided, or search by batch number across all medicines
    medicine: Optional[Medicine] = None
    if req.brand_name and req.brand_name.strip():
        search_brand = req.brand_name.strip()
        # Case-insensitive search
        medicine = db.query(Medicine).filter(
            Medicine.brand_name.ilike(f"%{search_brand}%")
        ).first()

    # Fallback: if brand not provided or not found, try to locate medicine by batch number in registry
    if not medicine:
        all_meds = db.query(Medicine).all()
        for m in all_meds:
            valid_list = [b.strip().upper() for b in m.valid_batches.split(",")]
            if clean_batch in valid_list:
                medicine = m
                break

    # 2. Evaluate Expiry
    # If user provided expiry date, parse it; otherwise fallback to DB record expiry if available
    expiry_input = req.expiry_date or (medicine.expiry_date if medicine else None)
    parsed_exp = parse_expiry_date(expiry_input)
    is_expired, is_expiring_soon, days_diff, exp_reason = evaluate_expiry(parsed_exp)
    if exp_reason:
        reasons.append(exp_reason)

    # 3. Evaluate Registry & Batch Match
    brand_found, batch_matched, mfg_matched, reg_reasons = evaluate_registry(
        medicine=medicine,
        batch_number=clean_batch,
        manufacturer_input=req.manufacturer,
    )
    reasons.extend(reg_reasons)

    # 4. Check Community Reports
    reports = db.query(CommunityReport).filter(
        CommunityReport.batch_number == clean_batch
    ).all()
    report_count = len(reports)
    has_rep, is_rep_high, rep_reason = evaluate_community_reports(report_count)
    if rep_reason:
        reasons.append(rep_reason)

    # 5. Compute Final Verdict
    is_flagged = medicine.is_flagged_fake if medicine else False
    status_code, title, next_steps = compute_final_verdict(
        is_expired=is_expired,
        is_expiring_soon=is_expiring_soon,
        brand_found=brand_found,
        batch_matched=batch_matched,
        mfg_matched=mfg_matched,
        report_count=report_count,
        is_flagged_fake=is_flagged,
    )

    # 6. Format details for UI
    details = None
    if medicine:
        details = MedicineDetails(
            brand_name=medicine.brand_name,
            salt_composition=medicine.salt_composition,
            manufacturer=medicine.manufacturer,
            official_expiry=medicine.expiry_date,
            mrp=medicine.mrp,
            generic_name=medicine.generic_name,
            generic_price=medicine.generic_price,
            uses=medicine.uses,
            side_effects=medicine.side_effects,
            avoid_mix=medicine.avoid_mix,
            storage_tips=medicine.storage_tips,
        )

    return MedicineCheckResponse(
        status=status_code,
        title=title,
        reasons=reasons,
        next_steps=next_steps,
        report_count=report_count,
        medicine_details=details,
        checked_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )

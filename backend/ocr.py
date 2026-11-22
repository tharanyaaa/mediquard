"""
OCR Processing Module.
Extracts batch numbers, expiry dates, MRP, and brand names from medicine strip images.
Provides graceful fallback if Tesseract binary is not installed on the host.
"""

import io
import re
from typing import Dict, Optional, Tuple
from PIL import Image

try:
    import pytesseract
    PYTESSERACT_INSTALLED = True
except ImportError:
    PYTESSERACT_INSTALLED = False


def extract_text_from_image(image_bytes: bytes) -> Tuple[bool, str, Optional[str]]:
    """
    Attempts to run Tesseract OCR on provided image bytes.
    Returns (success: bool, raw_text: str, error_or_notice: Optional[str]).
    """
    if not PYTESSERACT_INSTALLED:
        return False, "", "pytesseract library is not installed."

    try:
        image = Image.open(io.BytesIO(image_bytes))
        # Convert to grayscale to improve contrast for tablet strips
        gray = image.convert("L")
        text = pytesseract.image_to_string(gray)
        if not text.strip():
            return False, "", "OCR completed but no readable text was detected on the package."
        return True, text, None
    except Exception as exc:
        err_msg = str(exc)
        if "tesseract is not installed" in err_msg.lower() or "not found" in err_msg.lower():
            return (
                False,
                "",
                "Tesseract OCR executable is not installed on system. Please enter the details manually below."
            )
        return False, "", f"Unable to process image: {err_msg}"


def parse_medicine_text(text: str) -> Dict[str, Optional[str]]:
    """
    Uses regular expressions to extract structured fields from scanned text.
    Searches for: Batch Number, Expiry Date, MRP, and potential Brand Name.
    """
    result: Dict[str, Optional[str]] = {
        "batch_number": None,
        "expiry_date": None,
        "mrp": None,
        "brand_name": None,
    }

    if not text:
        return result

    # 1. Batch Number regex
    # Matches: B.No. XYZ123, Batch No: AB-990, Lot No: 4421, B/N: 2024-01
    batch_pattern = re.compile(
        r"(?:B(?:\.|\s)?(?:No|N)\.?|Batch(?:\s?No)?\.?|Lot(?:\s?No)?\.?|B\.N\.)\s*[:.\-]?\s*([A-Za-z0-9\-_/]+)",
        re.IGNORECASE
    )
    batch_match = batch_pattern.search(text)
    if batch_match:
        result["batch_number"] = batch_match.group(1).strip()

    # 2. Expiry Date regex
    # Matches: Exp. Date: 10/26, Expiry: 2026-10-31, Use Before: 11/2026
    expiry_pattern = re.compile(
        r"(?:Exp(?:\.|iry)?(?:\s?Date)?\.?|Use\s*Before|Expiry)\s*[:.\-]?\s*([0-9]{1,2}[/-][0-9]{2,4}|[0-9]{4}[/-][0-9]{1,2}(?:[/-][0-9]{1,2})?)",
        re.IGNORECASE
    )
    expiry_match = expiry_pattern.search(text)
    if expiry_match:
        result["expiry_date"] = expiry_match.group(1).strip()

    # 3. MRP regex
    # Matches: M.R.P. Rs. 45.00, MRP: 120, Rs 50
    mrp_pattern = re.compile(
        r"(?:M\.?R\.?P\.?|Rs\.?|₹)\s*[:.\-]?\s*([0-9]+(?:\.[0-9]{1,2})?)",
        re.IGNORECASE
    )
    mrp_match = mrp_pattern.search(text)
    if mrp_match:
        result["mrp"] = mrp_match.group(1).strip()

    return result

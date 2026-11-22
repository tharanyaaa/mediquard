"""
Rule Engine for Fake Medicine Checker.

Rules:
1. Expiry check (Expired -> RED, Expiring soon -> YELLOW, Active -> GREEN)
2. Batch & Manufacturer match against registered records
3. Community report count (3+ reports -> RED, 1-2 reports -> YELLOW)

Verdict statuses:
- GREEN: Looks genuine (based on registered batch data)
- YELLOW: Suspicious, verify with a pharmacist
- RED: Expired or likely fake
"""

import re
from datetime import date, datetime
from typing import List, Optional, Tuple
from .models import Medicine


def parse_expiry_date(date_str: Optional[str]) -> Optional[date]:
    """
    Parses various date formats commonly printed on medicine packaging.
    Supports: YYYY-MM-DD, MM/YYYY, MM/YY, MM-YYYY, MM-YY, YYYY-MM.
    Defaults to last day of the expiry month if day is omitted.
    """
    if not date_str:
        return None

    clean = date_str.strip()

    # Try ISO YYYY-MM-DD
    try:
        return datetime.strptime(clean, "%Y-%m-%d").date()
    except ValueError:
        pass

    # Try MM/YYYY or MM-YYYY
    match_m_yyyy = re.match(r"^(\d{1,2})[/\-](\d{4})$", clean)
    if match_m_yyyy:
        month = int(match_m_yyyy.group(1))
        year = int(match_m_yyyy.group(2))
        if 1 <= month <= 12:
            next_month = month + 1 if month < 12 else 1
            next_year = year if month < 12 else year + 1
            # Day before the 1st of next month = last day of current month
            from datetime import timedelta
            return date(next_year, next_month, 1) - timedelta(days=1)

    # Try MM/YY or MM-YY (e.g. 10/26 -> 2026-10-31)
    match_m_yy = re.match(r"^(\d{1,2})[/\-](\d{2})$", clean)
    if match_m_yy:
        month = int(match_m_yy.group(1))
        year = 2000 + int(match_m_yy.group(2))
        if 1 <= month <= 12:
            next_month = month + 1 if month < 12 else 1
            next_year = year if month < 12 else year + 1
            from datetime import timedelta
            return date(next_year, next_month, 1) - timedelta(days=1)

    # Try YYYY-MM
    match_yyyy_m = re.match(r"^(\d{4})[/\-](\d{1,2})$", clean)
    if match_yyyy_m:
        year = int(match_yyyy_m.group(1))
        month = int(match_yyyy_m.group(2))
        if 1 <= month <= 12:
            next_month = month + 1 if month < 12 else 1
            next_year = year if month < 12 else year + 1
            from datetime import timedelta
            return date(next_year, next_month, 1) - timedelta(days=1)

    return None


def evaluate_expiry(
    parsed_date: Optional[date],
    reference_date: Optional[date] = None
) -> Tuple[bool, bool, Optional[int], Optional[str]]:
    """
    Evaluates expiry date against reference date (defaults to today).
    Returns (is_expired, is_expiring_soon, days_diff, explanation).
    """
    if not parsed_date:
        return False, False, None, "No expiry date provided or readable from packaging."

    today = reference_date or date.today()
    days_diff = (parsed_date - today).days

    if days_diff < 0:
        days_ago = abs(days_diff)
        return (
            True,
            False,
            days_diff,
            f"EXPIRED: Medicine expired on {parsed_date.strftime('%d %b %Y')} ({days_ago} days ago). Do not consume."
        )
    elif days_diff <= 45:
        return (
            False,
            True,
            days_diff,
            f"EXPIRING SOON: Medicine expires on {parsed_date.strftime('%d %b %Y')} (in {days_diff} days)."
        )
    else:
        return (
            False,
            False,
            days_diff,
            f"Expiry date valid: {parsed_date.strftime('%d %b %Y')} ({days_diff} days remaining)."
        )


def evaluate_registry(
    medicine: Optional[Medicine],
    batch_number: str,
    manufacturer_input: Optional[str] = None
) -> Tuple[bool, bool, bool, List[str]]:
    """
    Checks if medicine brand exists, batch matches valid list, and manufacturer matches.
    Returns (brand_found, batch_matched, mfg_matched, reasons).
    """
    reasons: List[str] = []
    clean_batch = batch_number.strip().upper()

    if not medicine:
        reasons.append("Brand not found in verified pharmaceutical database. Verification needed.")
        return False, False, True, reasons

    brand_found = True

    # 1. Check batch against manufacturer's registered valid batches
    valid_batches_list = [b.strip().upper() for b in medicine.valid_batches.split(",") if b.strip()]
    if clean_batch in valid_batches_list:
        batch_matched = True
        reasons.append(f"Batch '{batch_number}' matches registered production records for {medicine.brand_name}.")
    else:
        batch_matched = False
        reasons.append(f"UNRECOGNIZED BATCH: Batch '{batch_number}' was not found in registered records for {medicine.brand_name}.")

    # 2. Check manufacturer if provided
    mfg_matched = True
    if manufacturer_input and manufacturer_input.strip():
        input_mfg = manufacturer_input.strip().lower()
        reg_mfg = medicine.manufacturer.strip().lower()
        # Allow partial contains match (e.g. "Arogya" in "Arogya Pharma Labs Ltd.")
        if input_mfg not in reg_mfg and reg_mfg not in input_mfg:
            mfg_matched = False
            reasons.append(
                f"MANUFACTURER MISMATCH: Packaging says '{manufacturer_input}', but official registration is '{medicine.manufacturer}'."
            )
        else:
            reasons.append(f"Manufacturer matches official registry: '{medicine.manufacturer}'.")

    # 3. Known flagged fake check
    if medicine.is_flagged_fake:
        reasons.append("ALERT: Regulatory notice indicates high counterfeit circulation for this product.")

    return brand_found, batch_matched, mfg_matched, reasons


def evaluate_community_reports(report_count: int) -> Tuple[bool, bool, Optional[str]]:
    """
    Evaluates community suspicion reports for this batch.
    Returns (has_reports, is_high_risk, reason).
    """
    if report_count >= 3:
        return (
            True,
            True,
            f"HIGH RISK: {report_count} suspicious batch reports logged by consumers/pharmacists in recent days."
        )
    elif report_count > 0:
        return (
            True,
            False,
            f"COMMUNITY ALERT: {report_count} report(s) recently flagged for this batch number."
        )
    return False, False, None


def compute_final_verdict(
    is_expired: bool,
    is_expiring_soon: bool,
    brand_found: bool,
    batch_matched: bool,
    mfg_matched: bool,
    report_count: int,
    is_flagged_fake: bool = False
) -> Tuple[str, str, str]:
    """
    Calculates final status (GREEN / YELLOW / RED), title, and safe next-step message.
    """
    # RED conditions:
    # 1. Expired
    # 2. Flagged fake
    # 3. Batch not recognized in official manufacturer records (when brand is known)
    # 4. Manufacturer mismatch
    # 5. 3 or more community complaints
    if is_expired:
        status = "RED"
        title = "Expired Medicine"
    elif is_flagged_fake:
        status = "RED"
        title = "Likely Counterfeit Alert"
    elif brand_found and not batch_matched:
        status = "RED"
        title = "Unverified Batch - Likely Fake"
    elif not mfg_matched:
        status = "RED"
        title = "Manufacturer Mismatch - Likely Fake"
    elif report_count >= 3:
        status = "RED"
        title = "High Risk - Multiple Community Reports"
    # YELLOW conditions:
    # 1. Brand not found in registry (cannot confirm, but not known fake)
    # 2. Expiring soon (within 45 days)
    # 3. 1 or 2 community reports
    elif not brand_found:
        status = "YELLOW"
        title = "Suspicious - Unregistered Brand"
    elif is_expiring_soon:
        status = "YELLOW"
        title = "Expiring Soon - Verify"
    elif report_count > 0:
        status = "YELLOW"
        title = "Suspicious - Community Flagged"
    # GREEN:
    else:
        status = "GREEN"
        title = "Looks Genuine"

    # Next steps per product rules:
    if status in ("YELLOW", "RED"):
        next_steps = "Don't take it. Show it to a pharmacist. Report it."
    else:
        next_steps = (
            "Looks genuine based on registered batch data. Always check intact packaging seal before use. "
            "If in doubt, show it to a pharmacist."
        )

    return status, title, next_steps

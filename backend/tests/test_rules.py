"""
Pytest unit tests for the Rule Engine of Fake Medicine Checker.
Tests expiry evaluation, registry verification, community reports, and verdict calculation.
"""

from datetime import date
from backend.models import Medicine
from backend.rules import (
    compute_final_verdict,
    evaluate_community_reports,
    evaluate_expiry,
    evaluate_registry,
    parse_expiry_date,
)


def test_parse_expiry_date_formats():
    """Verify various packaging date formats are parsed correctly."""
    # YYYY-MM-DD
    assert parse_expiry_date("2026-10-31") == date(2026, 10, 31)

    # MM/YY (e.g. 10/26 -> 2026-10-31)
    d_mmyy = parse_expiry_date("10/26")
    assert d_mmyy is not None
    assert d_mmyy.year == 2026
    assert d_mmyy.month == 10
    assert d_mmyy.day == 31

    # MM/YYYY
    d_mmyyyy = parse_expiry_date("05/2027")
    assert d_mmyyyy is not None
    assert d_mmyyyy.year == 2027
    assert d_mmyyyy.month == 5
    assert d_mmyyyy.day == 31

    # Invalid / empty
    assert parse_expiry_date("") is None
    assert parse_expiry_date(None) is None
    assert parse_expiry_date("INVALID-DATE") is None


def test_evaluate_expiry_states():
    """Verify expired, expiring soon, and active date evaluations."""
    ref_date = date(2026, 6, 1)

    # 1. Expired date
    exp_past = date(2025, 12, 31)
    is_exp, is_soon, diff, reason = evaluate_expiry(exp_past, reference_date=ref_date)
    assert is_exp is True
    assert is_soon is False
    assert diff < 0
    assert "EXPIRED" in reason

    # 2. Expiring soon (within 45 days)
    exp_soon = date(2026, 6, 20)  # 19 days away
    is_exp, is_soon, diff, reason = evaluate_expiry(exp_soon, reference_date=ref_date)
    assert is_exp is False
    assert is_soon is True
    assert diff == 19
    assert "EXPIRING SOON" in reason

    # 3. Active valid date (>45 days)
    exp_future = date(2027, 6, 1)
    is_exp, is_soon, diff, reason = evaluate_expiry(exp_future, reference_date=ref_date)
    assert is_exp is False
    assert is_soon is False
    assert diff > 45
    assert "valid" in reason.lower()


def test_evaluate_registry_checks():
    """Verify registry checks for brand, batch, and manufacturer."""
    dummy_med = Medicine(
        brand_name="Paracool 500",
        salt_composition="Paracetamol 500mg",
        manufacturer="Arogya Pharma Labs Ltd.",
        valid_batches="PARA-01,PARA-02,PARA-03",
        expiry_date="2027-10-31",
        mrp=40.0,
        is_flagged_fake=False
    )

    # Valid batch & matching manufacturer
    brand_found, batch_ok, mfg_ok, reasons = evaluate_registry(
        medicine=dummy_med,
        batch_number="PARA-01",
        manufacturer_input="Arogya Pharma Labs Ltd."
    )
    assert brand_found is True
    assert batch_ok is True
    assert mfg_ok is True

    # Case-insensitive valid batch
    _, batch_ok_ci, _, _ = evaluate_registry(
        medicine=dummy_med,
        batch_number="para-02",
        manufacturer_input=None
    )
    assert batch_ok_ci is True

    # Unrecognized batch
    _, batch_bad, _, bad_reasons = evaluate_registry(
        medicine=dummy_med,
        batch_number="UNKNOWN-99",
        manufacturer_input=None
    )
    assert batch_bad is False
    assert any("UNRECOGNIZED BATCH" in r for r in bad_reasons)

    # Manufacturer mismatch
    _, _, mfg_bad, mfg_reasons = evaluate_registry(
        medicine=dummy_med,
        batch_number="PARA-01",
        manufacturer_input="Counterfeit Pharma Inc"
    )
    assert mfg_bad is False
    assert any("MANUFACTURER MISMATCH" in r for r in mfg_reasons)


def test_community_reports():
    """Verify community suspicion report weighting."""
    # 0 reports
    has_rep, is_high, _ = evaluate_community_reports(0)
    assert has_rep is False
    assert is_high is False

    # 1 report (Alert)
    has_rep, is_high, _ = evaluate_community_reports(1)
    assert has_rep is True
    assert is_high is False

    # 3+ reports (High risk)
    has_rep, is_high, r = evaluate_community_reports(5)
    assert has_rep is True
    assert is_high is True
    assert "HIGH RISK" in r


def test_compute_final_verdict_outcomes():
    """Verify GREEN, YELLOW, and RED outcomes per product rules."""
    # 1. GREEN outcome: genuine, valid, 0 reports
    status, title, next_step = compute_final_verdict(
        is_expired=False,
        is_expiring_soon=False,
        brand_found=True,
        batch_matched=True,
        mfg_matched=True,
        report_count=0
    )
    assert status == "GREEN"
    assert "Genuine" in title
    assert "show it to a pharmacist" in next_step.lower()

    # 2. RED outcome: expired
    status, title, next_step = compute_final_verdict(
        is_expired=True,
        is_expiring_soon=False,
        brand_found=True,
        batch_matched=True,
        mfg_matched=True,
        report_count=0
    )
    assert status == "RED"
    assert "Expired" in title
    assert "Don't take it. Show it to a pharmacist. Report it." in next_step

    # 3. RED outcome: unrecognized batch
    status, title, next_step = compute_final_verdict(
        is_expired=False,
        is_expiring_soon=False,
        brand_found=True,
        batch_matched=False,
        mfg_matched=True,
        report_count=0
    )
    assert status == "RED"
    assert "Likely Fake" in title
    assert "Don't take it. Show it to a pharmacist. Report it." in next_step

    # 4. RED outcome: 3+ reports
    status, title, _ = compute_final_verdict(
        is_expired=False,
        is_expiring_soon=False,
        brand_found=True,
        batch_matched=True,
        mfg_matched=True,
        report_count=4
    )
    assert status == "RED"

    # 5. YELLOW outcome: unknown brand (needs manual verification)
    status, title, next_step = compute_final_verdict(
        is_expired=False,
        is_expiring_soon=False,
        brand_found=False,
        batch_matched=False,
        mfg_matched=True,
        report_count=0
    )
    assert status == "YELLOW"
    assert "Suspicious" in title
    assert "Don't take it. Show it to a pharmacist. Report it." in next_step

    # 6. YELLOW outcome: expiring soon
    status, title, _ = compute_final_verdict(
        is_expired=False,
        is_expiring_soon=True,
        brand_found=True,
        batch_matched=True,
        mfg_matched=True,
        report_count=0
    )
    assert status == "YELLOW"
    assert "Expiring Soon" in title

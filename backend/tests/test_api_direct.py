"""
Unit and functional tests for API route logic.
Calls API handlers directly with database session.
"""

from backend.database import SessionLocal
from backend.main import check_medicine, list_medicines, read_root, trigger_seed
from backend.schemas import MedicineCheckRequest
from backend.seed import seed_database


def setup_module(module):
    """Seed test database."""
    seed_database()


def test_read_root():
    """Verify healthcheck payload."""
    res = read_root()
    assert res["status"] == "online"
    assert "Fake Medicine Checker" in res["app"]


def test_check_safe_medicine_green():
    """Valid medicine (Paracool 500) returns GREEN."""
    db = SessionLocal()
    try:
        req = MedicineCheckRequest(
            batch_number="PARA-2024-01",
            brand_name="Paracool 500",
            expiry_date="2027-10-31",
            manufacturer="Arogya Pharma Labs Ltd."
        )
        res = check_medicine(req, db=db)
        assert res.status == "GREEN"
        assert "Genuine" in res.title
        assert res.medicine_details is not None
        assert res.medicine_details.brand_name == "Paracool 500"
    finally:
        db.close()


def test_check_expired_medicine_red():
    """Expired medicine (Ranitide-150) returns RED."""
    db = SessionLocal()
    try:
        req = MedicineCheckRequest(
            batch_number="RAN-151",
            brand_name="Ranitide-150",
            expiry_date="2023-04-30",
            manufacturer="Sunrise Medicare India"
        )
        res = check_medicine(req, db=db)
        assert res.status == "RED"
        assert "Expired" in res.title
        assert "Don't take it. Show it to a pharmacist. Report it." in res.next_steps
    finally:
        db.close()


def test_check_fake_batch_and_community_reports_red():
    """Fake batch (DLQ-FAKE) with community reports returns RED."""
    db = SessionLocal()
    try:
        req = MedicineCheckRequest(
            batch_number="DLQ-FAKE",
            brand_name="DoloQuick 650",
            expiry_date="2027-08-31",
            manufacturer="Vedic Life Sciences"
        )
        res = check_medicine(req, db=db)
        assert res.status == "RED"
        assert res.report_count >= 3
        assert any("UNRECOGNIZED BATCH" in r for r in res.reasons)
        assert any("HIGH RISK" in r for r in res.reasons)
        assert "Don't take it. Show it to a pharmacist. Report it." in res.next_steps
    finally:
        db.close()


def test_check_unknown_brand_yellow():
    """Unknown brand returns YELLOW (Suspicious - Verify)."""
    db = SessionLocal()
    try:
        req = MedicineCheckRequest(
            batch_number="UNK-8888",
            brand_name="UnregisteredPharmaX",
            expiry_date="2027-12-31"
        )
        res = check_medicine(req, db=db)
        assert res.status == "YELLOW"
        assert "Suspicious" in res.title
        assert "Don't take it. Show it to a pharmacist. Report it." in res.next_steps
    finally:
        db.close()


def test_list_medicines():
    """Verify list of registered demo medicines."""
    db = SessionLocal()
    try:
        meds = list_medicines(db=db)
        assert len(meds) >= 30
    finally:
        db.close()


def test_trigger_seed():
    """Verify seed endpoint reset logic."""
    res = trigger_seed()
    assert "successfully" in res["message"]

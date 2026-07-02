"""
Comprehensive tests for Payment Ledger and Payment Rules validation.
Tests verify:
- Joining maximum (₹1200)
- 180 days maximum (₹600)
- Annual maximum (₹1800)
- Kit quantity limits (3 Shirts, 3 Jeans)
- Excess kit flagging (5 Shirts, 4 Jeans threshold)
- Running totals and remaining balance calculations
"""

import unittest
import datetime
import io
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.db import Base
from backend.app.models.models import Trainee, InvoiceRecord, PaymentLedger, ValidationResult
from backend.app.services.ledger_service import LedgerService
from backend.app.services.validation_service import ValidationService
from backend.app.services.rules import RuleKitLimit, RuleAnnualLimit, RuleJoiningLimit, Rule180Days


class TestPaymentLedger(unittest.TestCase):
    """Test suite for payment ledger and payment rules."""
    
    def setUp(self):
        """Initialize in-memory SQLite database for testing."""
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()

    def tearDown(self):
        """Clean up database after each test."""
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_payment_rule_joining_maximum(self):
        """Joining payment should not exceed ₹1200."""
        trainee = Trainee(
            id="T001",
            name="John Doe",
            doj=datetime.date(2025, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(trainee)
        
        # Invoice with joining claim exceeding ₹1200
        invoice = InvoiceRecord(
            invoice_number="INV001",
            invoice_date=datetime.date(2025, 6, 1),
            trainee_id="T001",
            billed_joining_amount=1500.0,  # Exceeds ₹1200
            billed_180_days_amount=0.0,
            billed_total_amount=1500.0,
            approved_joining_amount=1200.0,  # Capped at ₹1200
            approved_180_days_amount=0.0,
            approved_total_amount=1200.0,
            status="PENDING",
            file_name="test.xlsx"
        )
        self.db.add(invoice)
        self.db.commit()

        # Post to ledger
        LedgerService.approve_invoice_and_post_to_ledger(self.db, "INV001")
        
        # Verify ledger entry
        ledger_entry = self.db.query(PaymentLedger).filter_by(
            trainee_id="T001",
            payment_type="JOINING"
        ).first()
        
        self.assertIsNotNone(ledger_entry)
        self.assertEqual(ledger_entry.amount_paid, 1200.0)
        self.assertEqual(ledger_entry.extra_data["rejected"], 300.0)
        self.assertEqual(ledger_entry.extra_data["running_total"], 1200.0)
        self.assertEqual(ledger_entry.extra_data["remaining_balance"], 600.0)

    def test_payment_rule_180_days_maximum(self):
        """180 days payment should not exceed ₹600."""
        trainee = Trainee(
            id="T002",
            name="Jane Smith",
            doj=datetime.date(2024, 1, 1),  # More than 180 days old
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(trainee)
        
        # Invoice with 180 days claim exceeding ₹600
        invoice = InvoiceRecord(
            invoice_number="INV002",
            invoice_date=datetime.date(2025, 6, 1),
            trainee_id="T002",
            billed_joining_amount=0.0,
            billed_180_days_amount=800.0,  # Exceeds ₹600
            billed_total_amount=800.0,
            approved_joining_amount=0.0,
            approved_180_days_amount=600.0,  # Capped at ₹600
            approved_total_amount=600.0,
            status="PENDING",
            file_name="test.xlsx"
        )
        self.db.add(invoice)
        self.db.commit()

        # Post to ledger
        LedgerService.approve_invoice_and_post_to_ledger(self.db, "INV002")
        
        # Verify ledger entry
        ledger_entry = self.db.query(PaymentLedger).filter_by(
            trainee_id="T002",
            payment_type="180_DAYS"
        ).first()
        
        self.assertIsNotNone(ledger_entry)
        self.assertEqual(ledger_entry.amount_paid, 600.0)
        self.assertEqual(ledger_entry.extra_data["rejected"], 200.0)
        self.assertEqual(ledger_entry.extra_data["running_total"], 600.0)
        self.assertEqual(ledger_entry.extra_data["remaining_balance"], 1200.0)

    def test_annual_maximum_not_exceeded(self):
        """Total payments should not exceed annual maximum of ₹1800."""
        trainee = Trainee(
            id="T003",
            name="Bob Wilson",
            doj=datetime.date(2024, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(trainee)
        
        # First invoice: Joining ₹1200 + 180 Days ₹600 = ₹1800
        invoice1 = InvoiceRecord(
            invoice_number="INV003",
            invoice_date=datetime.date(2025, 3, 1),
            trainee_id="T003",
            billed_joining_amount=1200.0,
            billed_180_days_amount=600.0,
            billed_total_amount=1800.0,
            approved_joining_amount=1200.0,
            approved_180_days_amount=600.0,
            approved_total_amount=1800.0,
            status="PENDING",
            file_name="test.xlsx"
        )
        self.db.add(invoice1)
        self.db.commit()

        # Post first invoice
        LedgerService.approve_invoice_and_post_to_ledger(self.db, "INV003")
        
        # Verify running total is ₹1800
        running_total = self.db.query(PaymentLedger).filter_by(
            trainee_id="T003"
        )
        total = sum(e.amount_paid for e in running_total)
        self.assertEqual(total, 1800.0)
        
        # Second invoice: Additional ₹500 should be rejected (exceeds annual cap)
        invoice2 = InvoiceRecord(
            invoice_number="INV004",
            invoice_date=datetime.date(2025, 6, 1),
            trainee_id="T003",
            billed_joining_amount=500.0,
            billed_180_days_amount=0.0,
            billed_total_amount=500.0,
            approved_joining_amount=500.0,
            approved_180_days_amount=0.0,
            approved_total_amount=500.0,
            status="PENDING",
            file_name="test.xlsx"
        )
        self.db.add(invoice2)
        self.db.commit()

        # Post second invoice - should not exceed ₹1800 annual cap
        LedgerService.approve_invoice_and_post_to_ledger(self.db, "INV004")
        
        # Verify total still ₹1800 (cap enforced)
        ledger_entries = self.db.query(PaymentLedger).filter_by(
            trainee_id="T003"
        ).all()
        total_paid = sum(e.amount_paid for e in ledger_entries)
        self.assertEqual(total_paid, 1800.0)
        
        # Verify remaining balance is 0
        last_entry = ledger_entries[-1]
        self.assertEqual(last_entry.extra_data["remaining_balance"], 0.0)

    def test_kit_quantity_limits(self):
        """Kit quantities should not exceed 3 Shirts and 3 Jeans."""
        trainee = Trainee(
            id="T004",
            name="Alice Johnson",
            doj=datetime.date(2025, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(trainee)
        
        # Invoice with valid kit quantities
        invoice = InvoiceRecord(
            invoice_number="INV005",
            invoice_date=datetime.date(2025, 6, 1),
            trainee_id="T004",
            billed_joining_amount=1200.0,
            billed_180_days_amount=0.0,
            billed_total_amount=1200.0,
            approved_joining_amount=1200.0,
            approved_180_days_amount=0.0,
            approved_total_amount=1200.0,
            status="PENDING",
            file_name="test.xlsx",
            extra_data={
                "shirt_quantity": 3.0,
                "jean_quantity": 3.0
            }
        )
        self.db.add(invoice)
        self.db.commit()

        # Validate with kit limit rule
        rule = RuleKitLimit()
        result = rule.evaluate(
            record=invoice,
            trainee=trainee,
            history=[],
            config={"max_shirts": 3.0, "max_jeans": 3.0},
            state={},
            current_joining=1200.0,
            current_180=0.0
        )
        
        self.assertTrue(result.passed)
        self.assertEqual(result.approved_amount, 1200.0)

    def test_kit_excess_threshold_flagged(self):
        """Excess kit quantities (>5 Shirts, >4 Jeans) should be flagged and capped at ₹1200."""
        trainee = Trainee(
            id="T005",
            name="Charlie Brown",
            doj=datetime.date(2025, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(trainee)
        
        # Invoice with excessive kit quantities
        invoice = InvoiceRecord(
            invoice_number="INV006",
            invoice_date=datetime.date(2025, 6, 1),
            trainee_id="T005",
            billed_joining_amount=1500.0,  # Exceeds ₹1200
            billed_180_days_amount=0.0,
            billed_total_amount=1500.0,
            approved_joining_amount=1500.0,
            approved_180_days_amount=0.0,
            approved_total_amount=1500.0,
            status="PENDING",
            file_name="test.xlsx",
            extra_data={
                "shirt_quantity": 6.0,  # Exceeds 5 threshold
                "jean_quantity": 5.0    # Exceeds 4 threshold
            }
        )
        self.db.add(invoice)
        self.db.commit()

        # Validate with kit limit rule
        rule = RuleKitLimit()
        result = rule.evaluate(
            record=invoice,
            trainee=trainee,
            history=[],
            config={
                "max_shirts": 3.0,
                "max_jeans": 3.0,
                "invoice_threshold_shirts": 5.0,
                "invoice_threshold_jeans": 4.0,
                "kit_approval_cap": 1200.0
            },
            state={},
            current_joining=1500.0,
            current_180=0.0
        )
        
        self.assertFalse(result.passed)
        self.assertEqual(result.severity, "WARNING")
        # Should cap at ₹1200 due to excess kit
        self.assertEqual(result.approved_amount, 1200.0)

    def test_ledger_running_total_calculation(self):
        """Running total should accumulate correctly across multiple invoices."""
        trainee = Trainee(
            id="T006",
            name="Diana Prince",
            doj=datetime.date(2024, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(trainee)
        self.db.commit()

        # Invoice 1: ₹1200 (Joining)
        invoice1 = InvoiceRecord(
            invoice_number="INV007",
            invoice_date=datetime.date(2025, 1, 1),
            trainee_id="T006",
            billed_joining_amount=1200.0,
            billed_180_days_amount=0.0,
            billed_total_amount=1200.0,
            approved_joining_amount=1200.0,
            approved_180_days_amount=0.0,
            approved_total_amount=1200.0,
            status="PENDING",
            file_name="test.xlsx"
        )
        self.db.add(invoice1)
        self.db.commit()

        LedgerService.approve_invoice_and_post_to_ledger(self.db, "INV007")
        
        # Invoice 2: ₹400 (180 Days, less than max ₹600)
        invoice2 = InvoiceRecord(
            invoice_number="INV008",
            invoice_date=datetime.date(2025, 2, 1),
            trainee_id="T006",
            billed_joining_amount=0.0,
            billed_180_days_amount=400.0,
            billed_total_amount=400.0,
            approved_joining_amount=0.0,
            approved_180_days_amount=400.0,
            approved_total_amount=400.0,
            status="PENDING",
            file_name="test.xlsx"
        )
        self.db.add(invoice2)
        self.db.commit()

        LedgerService.approve_invoice_and_post_to_ledger(self.db, "INV008")
        
        # Verify running totals
        ledger_entries = self.db.query(PaymentLedger).filter_by(
            trainee_id="T006"
        ).order_by(PaymentLedger.payment_date).all()
        
        self.assertEqual(len(ledger_entries), 2)
        
        # First entry: ₹1200
        self.assertEqual(ledger_entries[0].amount_paid, 1200.0)
        self.assertEqual(ledger_entries[0].extra_data["running_total"], 1200.0)
        self.assertEqual(ledger_entries[0].extra_data["remaining_balance"], 600.0)
        
        # Second entry: ₹400, running total ₹1600
        self.assertEqual(ledger_entries[1].amount_paid, 400.0)
        self.assertEqual(ledger_entries[1].extra_data["running_total"], 1600.0)
        self.assertEqual(ledger_entries[1].extra_data["remaining_balance"], 200.0)

    def test_ledger_invoice_month_tracking(self):
        """Invoice month should be correctly tracked in ledger."""
        trainee = Trainee(
            id="T007",
            name="Edward Norton",
            doj=datetime.date(2024, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(trainee)
        
        invoice = InvoiceRecord(
            invoice_number="INV009",
            invoice_date=datetime.date(2025, 3, 15),  # March 2025
            trainee_id="T007",
            billed_joining_amount=1000.0,
            billed_180_days_amount=0.0,
            billed_total_amount=1000.0,
            approved_joining_amount=1000.0,
            approved_180_days_amount=0.0,
            approved_total_amount=1000.0,
            status="PENDING",
            file_name="test.xlsx"
        )
        self.db.add(invoice)
        self.db.commit()

        LedgerService.approve_invoice_and_post_to_ledger(self.db, "INV009")
        
        ledger_entry = self.db.query(PaymentLedger).filter_by(
            trainee_id="T007"
        ).first()
        
        self.assertIsNotNone(ledger_entry)
        self.assertEqual(ledger_entry.extra_data["invoice_month"], "March 2025")


if __name__ == "__main__":
    unittest.main()

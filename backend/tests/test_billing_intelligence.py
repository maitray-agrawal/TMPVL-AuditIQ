import unittest
import datetime
import uuid
import openpyxl
from io import BytesIO
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models.models import Trainee, Invoice, InvoiceItem, PaymentLedger, ValidationResult
from backend.app.services.import_service import ImportService
from backend.app.services.validation_service import ValidationService
from backend.app.services.ledger_service import LedgerService
from backend.app.core.db import Base

class TestBillingIntelligence(unittest.TestCase):
    def setUp(self):
        # Configure in-memory database for testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def _create_mock_excel(self, sheets_data: dict) -> bytes:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # Remove default sheet
        for sheet_name, rows in sheets_data.items():
            ws = wb.create_sheet(title=sheet_name)
            for r in rows:
                ws.append(r)
            if "Hidden" in sheet_name:
                ws.sheet_state = 'hidden'
        out = BytesIO()
        wb.save(out)
        return out.getvalue()

    def test_multi_sheet_and_metadata_ingestion(self):
        """Verify visible sheet detection and metadata parsing (Invoice No, Date, Vendor Name)."""
        # Create a mock trainee in the master list
        t = Trainee(
            id="T001",
            name="Alice Smith",
            doj=datetime.date(2026, 1, 1),
            status="ACTIVE",
            scheme="NAPS",
            batch="Batch-A"
        )
        self.db.add(t)
        self.db.commit()

        # Multi-sheet workbook content
        sheets_data = {
            "Vendor Invoice": [
                ["Invoice No: INV-2026-001"],
                ["Invoice Date: 2026-02-15"],
                ["Vendor Name: Tata Projects Ltd"],
                ["Billing Month: February 2026"],
                [],
                ["Trainee ID", "Employee Name", "Joining Amount", "180 Days Amount", "Amount", "Jeans", "Shirt", "Distribution Date"],
                ["T001", "Alice Smith", 1200.0, 0.0, 1200.0, 1, 2, "2026-02-10"]
            ],
            "HiddenSheet": [
                ["Trainee ID", "Employee Name", "Amount"],
                ["T002", "Bob Jones", 1200.0]
            ]
        }
        excel_bytes = self._create_mock_excel(sheets_data)

        # Ingest workbook (HiddenSheet should be ignored since only Vendor Invoice has valid headers/records)
        res = ImportService.import_invoice_workbook(self.db, excel_bytes, "tata_invoice.xlsx")
        
        self.assertEqual(res["success_count"], 1)
        
        # Verify Invoice Parent record
        inv = self.db.query(Invoice).filter(Invoice.invoice_number == "INV-2026-001").first()
        self.assertIsNotNone(inv)
        self.assertEqual(inv.vendor_name, "Tata Projects Ltd")
        self.assertEqual(inv.billing_month, "February")
        self.assertEqual(inv.billing_year, 2026)
        self.assertEqual(inv.status, "ACTIVE")
        self.assertEqual(inv.total_amount, 1200.0)

        # Verify InvoiceItems
        items = self.db.query(InvoiceItem).filter(InvoiceItem.invoice_number == "INV-2026-001").all()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].trainee_id, "T001")
        self.assertEqual(items[0].claimed_amount, 1200.0)
        self.assertEqual(items[0].jeans_count, 1)
        self.assertEqual(items[0].shirt_count, 2)
        self.assertEqual(items[0].distribution_date, datetime.date(2026, 2, 10))

    def test_superseding_invoices(self):
        """Verify that importing an invoice with the same number marks the old one as SUPERSEDED."""
        # Setup Trainee
        t = Trainee(
            id="T001",
            name="Alice Smith",
            doj=datetime.date(2026, 1, 1),
            status="ACTIVE",
            scheme="NAPS",
            batch="Batch-A"
        )
        self.db.add(t)
        self.db.commit()

        sheets_data_1 = {
            "Sheet1": [
                ["Invoice No: INV-DUP"],
                ["Invoice Date: 2026-02-15"],
                ["Trainee ID", "Employee Name", "Joining Amount", "180 Days Amount", "Amount", "Jeans", "Shirt", "Distribution Date"],
                ["T001", "Alice Smith", 1200.0, 0.0, 1200.0, 1, 2, "2026-02-10"]
            ]
        }
        excel_bytes_1 = self._create_mock_excel(sheets_data_1)
        ImportService.import_invoice_workbook(self.db, excel_bytes_1, "tata_invoice_1.xlsx")

        inv_old = self.db.query(Invoice).filter(Invoice.invoice_number == "INV-DUP").first()
        self.assertIsNotNone(inv_old)
        self.assertEqual(inv_old.status, "ACTIVE")

        # Import again
        sheets_data_2 = {
            "Sheet1": [
                ["Invoice No: INV-DUP"],
                ["Invoice Date: 2026-02-20"],
                ["Trainee ID", "Employee Name", "Joining Amount", "180 Days Amount", "Amount", "Jeans", "Shirt", "Distribution Date"],
                ["T001", "Alice Smith", 1200.0, 0.0, 1200.0, 1, 2, "2026-02-10"]
            ]
        }
        excel_bytes_2 = self._create_mock_excel(sheets_data_2)
        ImportService.import_invoice_workbook(self.db, excel_bytes_2, "tata_invoice_2.xlsx")

        self.db.refresh(inv_old)
        self.assertEqual(inv_old.status, "SUPERSEDED")

        inv_new = self.db.query(Invoice).filter(Invoice.status == "ACTIVE").first()
        self.assertIsNotNone(inv_new)
        self.assertEqual(inv_new.invoice_number, "INV-DUP")

    def test_validation_rules_and_scores(self):
        """Verify fraud detection engine calculates risk scores, categories, and aggregates invoice parent values."""
        # 1. Setup Master Trainees
        t_alice = Trainee(id="T001", name="Alice Smith", doj=datetime.date(2026, 1, 1), status="ACTIVE", scheme="NAPS")
        t_bob = Trainee(id="T002", name="Bob Jones", doj=datetime.date(2026, 1, 1), status="INACTIVE", scheme="NAPS")
        self.db.add_all([t_alice, t_bob])
        self.db.commit()

        # 2. Add Invoice parent & items
        invoice_uuid = str(uuid.uuid4())
        inv = Invoice(
            invoice_id=invoice_uuid,
            invoice_number="INV-VALIDATE",
            invoice_date=datetime.date(2026, 2, 15),
            status="ACTIVE",
            total_amount=3600.0,
            approved_amount=0.0,
            rejected_amount=0.0,
            fraud_amount=0.0
        )
        self.db.add(inv)
        
        # Item 1: Bob (Separated/INACTIVE employee claim) -> RuleInactiveEmployee
        item_bob = InvoiceItem(
            invoice_id=invoice_uuid,
            invoice_number="INV-VALIDATE",
            invoice_date=datetime.date(2026, 2, 15),
            trainee_id="T002",
            candidate_name="Bob Jones",
            claimed_amount=1200.0,
            billed_joining_amount=1200.0,
            status="PENDING"
        )
        # Item 2: Alice (Metadata mismatch: Name similarity is off, e.g. "Aliz Smeeth") -> RuleMetadataMismatch
        item_mismatch = InvoiceItem(
            invoice_id=invoice_uuid,
            invoice_number="INV-VALIDATE",
            invoice_date=datetime.date(2026, 2, 15),
            trainee_id="T001",
            candidate_name="Aliz Smeeth",
            claimed_amount=1200.0,
            billed_joining_amount=1200.0,
            status="PENDING"
        )
        # Item 3: Alice (Chronological error: Distribution date 2025-12-01 is before DOJ 2026-01-01) -> RuleChronology
        item_chrono = InvoiceItem(
            invoice_id=invoice_uuid,
            invoice_number="INV-VALIDATE",
            invoice_date=datetime.date(2026, 2, 15),
            trainee_id="T001",
            candidate_name="Alice Smith",
            claimed_amount=1200.0,
            billed_joining_amount=1200.0,
            distribution_date=datetime.date(2025, 12, 1),
            status="PENDING"
        )
        self.db.add_all([item_bob, item_mismatch, item_chrono])
        self.db.commit()

        # Run validation
        ValidationService.validate_invoice(self.db, "INV-VALIDATE")

        self.db.refresh(item_bob)
        self.db.refresh(item_mismatch)
        self.db.refresh(item_chrono)
        self.db.refresh(inv)

        # Check Bob (should be flagged as FRAUD / Inactive employee)
        self.assertEqual(item_bob._status, "FRAUD")
        self.assertTrue(item_bob.fraud_score > 50)
        self.assertEqual(item_bob.fraud_category, "High")
        self.assertEqual(item_bob.approved_amount, 0.0)

        # Check Mismatch (should be flagged as approved with warnings, status APPROVED)
        self.assertEqual(item_mismatch._status, "APPROVED")
        self.assertEqual(item_mismatch.approved_amount, 1200.0) 

        # Check Chronological violation (FRAUD, approved=0)
        self.assertEqual(item_chrono._status, "FRAUD")
        self.assertEqual(item_chrono.approved_amount, 0.0)

        # Verify parent invoice aggregates
        self.assertEqual(inv.approved_amount, 1200.0)
        self.assertEqual(inv.fraud_amount, 2400.0)
        self.assertEqual(inv.rejected_amount, 2400.0)
        self.assertEqual(inv.status, "ACTIVE")

    def test_cross_invoice_duplication(self):
        """Verify cross-invoice duplicate billing rules reject repeated claims in separate invoices."""
        t = Trainee(id="T001", name="Alice Smith", doj=datetime.date(2026, 1, 1), status="ACTIVE", scheme="NAPS")
        self.db.add(t)

        # Invoice 1
        invoice_uuid_1 = str(uuid.uuid4())
        inv1 = Invoice(invoice_id=invoice_uuid_1, invoice_number="INV-1", invoice_date=datetime.date(2026, 2, 1), status="ACTIVE", total_amount=1200.0)
        item1 = InvoiceItem(
            invoice_id=invoice_uuid_1,
            invoice_number="INV-1",
            invoice_date=datetime.date(2026, 2, 1),
            trainee_id="T001",
            candidate_name="Alice Smith",
            claimed_amount=1200.0,
            billed_joining_amount=1200.0,
            status="APPROVED",
            approved_joining_amount=1200.0,
            approved_amount=1200.0
        )
        self.db.add_all([inv1, item1])
        
        # Post to ledger so it represents a real paid entry
        ledger = PaymentLedger(
            trainee_id="T001",
            invoice_number="INV-1",
            payment_type="JOINING",
            amount_paid=1200.0,
            payment_date=datetime.date(2026, 2, 1)
        )
        self.db.add(ledger)
        self.db.commit()

        # Invoice 2
        invoice_uuid_2 = str(uuid.uuid4())
        inv2 = Invoice(invoice_id=invoice_uuid_2, invoice_number="INV-2", invoice_date=datetime.date(2026, 3, 1), status="ACTIVE", total_amount=1200.0)
        item2 = InvoiceItem(
            invoice_id=invoice_uuid_2,
            invoice_number="INV-2",
            invoice_date=datetime.date(2026, 3, 1),
            trainee_id="T001",
            candidate_name="Alice Smith",
            claimed_amount=1200.0,
            billed_joining_amount=1200.0,
            status="PENDING"
        )
        self.db.add_all([inv2, item2])
        self.db.commit()

        # Validate Invoice 2
        ValidationService.validate_invoice(self.db, "INV-2")
        self.db.refresh(item2)

        # Verify duplicate claim rejected as FRAUD
        self.assertEqual(item2._status, "FRAUD")
        self.assertEqual(item2.approved_amount, 0.0)
        
        flags = self.db.query(ValidationResult).filter(ValidationResult.invoice_record_id == item2.id).all()
        reason_codes = [f.reason_code for f in flags]
        self.assertIn("REPEATED_MONTHLY_BILLING", reason_codes)

    def test_ledger_posting_restrictions(self):
        """Verify that only APPROVED or PARTIALLY_APPROVED invoice items get posted to PaymentLedger."""
        t = Trainee(id="T001", name="Alice Smith", doj=datetime.date(2026, 1, 1), status="ACTIVE", scheme="NAPS")
        self.db.add(t)

        invoice_uuid = str(uuid.uuid4())
        inv = Invoice(invoice_id=invoice_uuid, invoice_number="INV-LEDGER", invoice_date=datetime.date(2026, 2, 15), status="ACTIVE", total_amount=2400.0)
        # Item 1: Valid and Approved
        item1 = InvoiceItem(
            invoice_id=invoice_uuid,
            invoice_number="INV-LEDGER",
            invoice_date=datetime.date(2026, 2, 15),
            trainee_id="T001",
            candidate_name="Alice Smith",
            claimed_amount=1200.0,
            billed_joining_amount=1200.0,
            status="APPROVED",
            approved_joining_amount=1200.0,
            approved_amount=1200.0
        )
        # Item 2: Flagged as FRAUD
        item2 = InvoiceItem(
            invoice_id=invoice_uuid,
            invoice_number="INV-LEDGER",
            invoice_date=datetime.date(2026, 2, 15),
            trainee_id="T001",
            candidate_name="Alice Smith",
            claimed_amount=1200.0,
            billed_joining_amount=1200.0,
            status="FRAUD",
            approved_joining_amount=0.0,
            approved_amount=0.0
        )
        self.db.add_all([inv, item1, item2])
        self.db.commit()

        # Approve and post to ledger
        success = LedgerService.approve_invoice_and_post_to_ledger(self.db, "INV-LEDGER")
        self.assertTrue(success)

        # Verify only Item 1 posted to ledger
        ledger_entries = self.db.query(PaymentLedger).filter(PaymentLedger.invoice_number == "INV-LEDGER").all()
        self.assertEqual(len(ledger_entries), 1)
        self.assertEqual(ledger_entries[0].trainee_id, "T001")
        self.assertEqual(ledger_entries[0].amount_paid, 1200.0)

if __name__ == "__main__":
    unittest.main()

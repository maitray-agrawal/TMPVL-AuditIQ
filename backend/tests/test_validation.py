import unittest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.db import Base
from backend.app.models.models import Trainee, InvoiceRecord, PaymentLedger, ValidationResult
from backend.app.repositories.repositories import TraineeRepository, InvoiceRepository, LedgerRepository
from backend.app.services.validation_service import ValidationService
from backend.app.services.ledger_service import LedgerService
from backend.app.services.import_service import ImportService
import io
import pandas as pd

class TestValidationEngine(unittest.TestCase):
    def setUp(self):
        # Configure in-memory database for testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_rule_1_leave_before_30_days(self):
        """Trainee leaving before 30 days gets ₹0 approved, is permanently blocked, and triggers ERROR."""
        # 1. Create a trainee who joined 2026-01-01 and left 2026-01-20 (19 days tenure)
        trainee = Trainee(
            id="T001",
            name="Alice",
            doj=datetime.date(2026, 1, 1),
            dol=datetime.date(2026, 1, 20),
            scheme="NAPS",
            status="SEPARATED"
        )
        self.db.add(trainee)
        self.db.commit()

        # 2. Add an invoice record billing joining payment of 1200
        inv = InvoiceRecord(
            invoice_number="INV-01",
            invoice_date=datetime.date(2026, 2, 1),
            trainee_id="T001",
            billed_name="Alice",
            billed_joining_amount=1200.0,
            billed_180_days_amount=0.0,
            billed_other_amount=0.0,
            billed_total_amount=1200.0,
            status="PENDING",
            file_name="invoice.xlsx"
        )
        self.db.add(inv)
        self.db.commit()

        # Run validation
        res = ValidationService.validate_invoice(self.db, "INV-01")
        self.assertEqual(res["error_count"], 1)

        # Reload invoice and trainee
        self.db.refresh(inv)
        self.db.refresh(trainee)

        # Alice should be blocked and approved amount is 0
        self.assertEqual(inv.approved_joining_amount, 0.0)
        self.assertEqual(inv.status, "EXCEPTION")
        self.assertEqual(trainee.status, "BLOCKED")
        self.assertIn("Resigned before 30 days", trainee.blocked_reason)

    def test_rule_2_leave_before_180_days_no_prior_approval(self):
        """Trainee leaving before 180 days with NO prior approval has joining reimbursement rejected and ₹600 rejected."""
        # 1. Create trainee: DOJ 2026-01-01, DOL 2026-03-01 (60 days tenure)
        trainee = Trainee(
            id="T002",
            name="Bob",
            doj=datetime.date(2026, 1, 1),
            dol=datetime.date(2026, 3, 1),
            scheme="B.Tech",
            status="SEPARATED"
        )
        self.db.add(trainee)
        self.db.commit()

        # Billed for joining (1200) and 180 days (600)
        inv = InvoiceRecord(
            invoice_number="INV-02",
            invoice_date=datetime.date(2026, 3, 15),
            trainee_id="T002",
            billed_name="Bob",
            billed_joining_amount=1200.0,
            billed_180_days_amount=600.0,
            status="PENDING",
            file_name="invoice.xlsx"
        )
        self.db.add(inv)
        self.db.commit()

        ValidationService.validate_invoice(self.db, "INV-02")
        self.db.refresh(inv)

        # Both should be rejected (joining was not already approved)
        self.assertEqual(inv.approved_joining_amount, 0.0)
        self.assertEqual(inv.approved_180_days_amount, 0.0)
        self.assertEqual(inv.status, "EXCEPTION")

    def test_rule_2_leave_before_180_days_with_prior_approval(self):
        """Trainee leaving before 180 days WITH prior approval allows keeping joining payment, but rejects ₹600."""
        # 1. Create trainee: DOJ 2026-01-01, DOL 2026-03-01 (60 days tenure)
        trainee = Trainee(
            id="T003",
            name="Charlie",
            doj=datetime.date(2026, 1, 1),
            dol=datetime.date(2026, 3, 1),
            scheme="M.Tech",
            status="SEPARATED"
        )
        self.db.add(trainee)

        # Charlie already had his joining payment approved in a previous ledger entry
        ledger = PaymentLedger(
            trainee_id="T003",
            invoice_number="INV-PREV",
            payment_type="JOINING",
            amount_paid=1200.0,
            payment_date=datetime.date(2026, 2, 1)
        )
        self.db.add(ledger)
        self.db.commit()

        # Current invoice billing joining (1200, which is a duplicate/redundant request) and 180 days (600)
        inv = InvoiceRecord(
            invoice_number="INV-03",
            invoice_date=datetime.date(2026, 3, 15),
            trainee_id="T003",
            billed_name="Charlie",
            billed_joining_amount=1200.0,
            billed_180_days_amount=600.0,
            status="PENDING",
            file_name="invoice.xlsx"
        )
        self.db.add(inv)
        self.db.commit()

        ValidationService.validate_invoice(self.db, "INV-03")
        self.db.refresh(inv)

        # Approved joining should be 0 because it's a historical double claim, approved 180 should be 0 (tenure < 180)
        self.assertEqual(inv.approved_joining_amount, 0.0)
        self.assertEqual(inv.approved_180_days_amount, 0.0)
        self.assertEqual(inv.status, "EXCEPTION")

    def test_rule_3_max_payable_cap(self):
        """Never approve payout beyond ₹1800 across both payments."""
        trainee = Trainee(
            id="T004",
            name="David",
            doj=datetime.date(2026, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(trainee)
        
        # Already paid 1200 joining in previous invoice
        ledger = PaymentLedger(
            trainee_id="T004",
            invoice_number="INV-PREV",
            payment_type="JOINING",
            amount_paid=1200.0,
            payment_date=datetime.date(2026, 2, 1)
        )
        self.db.add(ledger)
        self.db.commit()

        # Billed for 180 days (800) -> should cap at 600
        inv = InvoiceRecord(
            invoice_number="INV-04",
            invoice_date=datetime.date(2026, 7, 5), # > 180 days later
            trainee_id="T004",
            billed_name="David",
            billed_joining_amount=0.0,
            billed_180_days_amount=800.0,
            status="PENDING",
            file_name="invoice.xlsx"
        )
        self.db.add(inv)
        self.db.commit()

        ValidationService.validate_invoice(self.db, "INV-04")
        self.db.refresh(inv)

        # Should cap 180 days at 600. Billed 800 is capped.
        self.assertEqual(inv.approved_180_days_amount, 600.0)
        self.assertEqual(inv.approved_total_amount, 600.0)

    def test_rule_6_ignore_excess_items(self):
        """Uniform / excess garments billed by vendor are ignored and approved amount is 0."""
        trainee = Trainee(
            id="T005",
            name="Eva",
            doj=datetime.date(2026, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(trainee)
        
        inv = InvoiceRecord(
            invoice_number="INV-05",
            invoice_date=datetime.date(2026, 2, 1),
            trainee_id="T005",
            billed_name="Eva",
            billed_joining_amount=1200.0,
            billed_180_days_amount=0.0,
            billed_other_amount=450.0, # Billed for shirts/jeans
            billed_total_amount=1650.0,
            status="PENDING",
            file_name="invoice.xlsx"
        )
        self.db.add(inv)
        self.db.commit()

        ValidationService.validate_invoice(self.db, "INV-05")
        self.db.refresh(inv)

        # Approved joining = 1200, approved other = 0 (ignored), approved total = 1200
        self.assertEqual(inv.approved_joining_amount, 1200.0)
        self.assertEqual(inv.approved_total_amount, 1200.0)
        # Should have a warning flag about excess items
        flags = self.db.query(ValidationResult).filter(ValidationResult.invoice_record_id == inv.id).all()
        rules = [f.rule_name for f in flags]
        self.assertIn("Excess Items Ignored", rules)

    def test_rule_8_double_claiming_same_cycle(self):
        """Billing the same trainee twice in the same invoice triggers FRAUD flag."""
        trainee = Trainee(
            id="T006",
            name="Frank",
            doj=datetime.date(2026, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(trainee)

        # Two invoice rows for T006 in same invoice INV-06
        inv1 = InvoiceRecord(
            invoice_number="INV-06",
            invoice_date=datetime.date(2026, 2, 1),
            trainee_id="T006",
            billed_name="Frank",
            billed_joining_amount=1200.0,
            status="PENDING",
            file_name="invoice.xlsx"
        )
        inv2 = InvoiceRecord(
            invoice_number="INV-06",
            invoice_date=datetime.date(2026, 2, 1),
            trainee_id="T006",
            billed_name="Frank",
            billed_joining_amount=1200.0,
            status="PENDING",
            file_name="invoice.xlsx"
        )
        self.db.add_all([inv1, inv2])
        self.db.commit()

        ValidationService.validate_invoice(self.db, "INV-06")
        self.db.refresh(inv1)
        self.db.refresh(inv2)

        # One of them will be flagged as duplicate
        flags = self.db.query(ValidationResult).filter(ValidationResult.rule_name == "Double Claiming (Same Cycle)").all()
        self.assertEqual(len(flags), 1)

        # Verify that the duplicate record (inv2) has its approved amount set to 0.0
        self.assertEqual(inv1.approved_joining_amount, 1200.0)
        self.assertEqual(inv2.approved_joining_amount, 0.0)
        self.assertEqual(inv2.status, "EXCEPTION")

    def test_get_unique_invoices_aggregation(self):
        """Verify that get_unique_invoices correctly aggregates billed/approved amounts and resolves statuses."""
        inv1 = InvoiceRecord(
            invoice_number="INV-100",
            invoice_date=datetime.date(2026, 5, 1),
            trainee_id="T001",
            billed_total_amount=5000.0,
            approved_total_amount=4000.0,
            status="APPROVED",
            file_name="invoice_100.xlsx"
        )
        inv2 = InvoiceRecord(
            invoice_number="INV-100",
            invoice_date=datetime.date(2026, 5, 1),
            trainee_id="T002",
            billed_total_amount=3000.0,
            approved_total_amount=3000.0,
            status="EXCEPTION",  # EXCEPTION status should bubble up
            file_name="invoice_100.xlsx"
        )
        inv3 = InvoiceRecord(
            invoice_number="INV-200",
            invoice_date=datetime.date(2026, 5, 2),
            trainee_id="T003",
            billed_total_amount=1500.0,
            approved_total_amount=1500.0,
            status="VALIDATED",
            file_name="invoice_200.xlsx"
        )
        self.db.add_all([inv1, inv2, inv3])
        self.db.commit()

        uniques = InvoiceRepository.get_unique_invoices(self.db)
        
        inv100_data = [u for u in uniques if u["invoice_number"] == "INV-100"]
        inv200_data = [u for u in uniques if u["invoice_number"] == "INV-200"]

        self.assertEqual(len(inv100_data), 1)
        self.assertEqual(len(inv200_data), 1)

        u100 = inv100_data[0]
        self.assertEqual(u100["billed_amount"], 8000.0)
        self.assertEqual(u100["approved_amount"], 7000.0)
        self.assertEqual(u100["record_count"], 2)
        self.assertEqual(u100["status"], "EXCEPTION")

        u200 = inv200_data[0]
        self.assertEqual(u200["billed_amount"], 1500.0)
        self.assertEqual(u200["approved_amount"], 1500.0)
        self.assertEqual(u200["record_count"], 1)
        self.assertEqual(u200["status"], "VALIDATED")

    def test_rule_15_multiple_invoice_submission(self):
        """Billing the same trainee in two different invoices (different invoice numbers) flags Multiple Invoice Submission."""
        trainee = Trainee(
            id="T007",
            name="Grace",
            doj=datetime.date(2026, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(trainee)
        self.db.commit()

        # Prior invoice record in database
        inv_old = InvoiceRecord(
            invoice_number="INV-OLD",
            invoice_date=datetime.date(2026, 2, 1),
            trainee_id="T007",
            billed_name="Grace",
            billed_joining_amount=1200.0,
            billed_total_amount=1200.0,
            status="APPROVED",
            file_name="invoice_old.xlsx"
        )
        self.db.add(inv_old)
        self.db.commit()

        # New invoice record for the same trainee under a different invoice number
        inv_new = InvoiceRecord(
            invoice_number="INV-NEW",
            invoice_date=datetime.date(2026, 3, 1),
            trainee_id="T007",
            billed_name="Grace",
            billed_joining_amount=1200.0,
            billed_total_amount=1200.0,
            status="PENDING",
            file_name="invoice_new.xlsx"
        )
        self.db.add(inv_new)
        self.db.commit()

        # Run validation
        ValidationService.validate_invoice(self.db, "INV-NEW")
        self.db.refresh(inv_new)

        self.assertEqual(inv_new.approved_joining_amount, 0.0)
        self.assertEqual(inv_new.status, "EXCEPTION")

        # Check that validation result flags Multiple Invoice Submission
        results = self.db.query(ValidationResult).filter(
            ValidationResult.invoice_record_id == inv_new.id
        ).all()
        reason_codes = [r.reason_code for r in results]
        self.assertIn("MULTIPLE_INVOICES", reason_codes)

    def test_rule_16_duplicate_invoice_same_month(self):
        """Billing the same trainee in two different invoices in the same calendar month flags Duplicate Invoice in Same Month."""
        trainee = Trainee(
            id="T008",
            name="Heidi",
            doj=datetime.date(2026, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(trainee)
        self.db.commit()

        # Prior invoice record in database (same month: Feb 2026)
        inv_old = InvoiceRecord(
            invoice_number="INV-OLD-FEB",
            invoice_date=datetime.date(2026, 2, 1),
            trainee_id="T008",
            billed_name="Heidi",
            billed_joining_amount=1200.0,
            billed_total_amount=1200.0,
            status="APPROVED",
            file_name="invoice_old.xlsx"
        )
        self.db.add(inv_old)
        self.db.commit()

        # New invoice record for the same trainee (same month: Feb 28, 2026)
        inv_new = InvoiceRecord(
            invoice_number="INV-NEW-FEB",
            invoice_date=datetime.date(2026, 2, 28),
            trainee_id="T008",
            billed_name="Heidi",
            billed_joining_amount=1200.0,
            billed_total_amount=1200.0,
            status="PENDING",
            file_name="invoice_new.xlsx"
        )
        self.db.add(inv_new)
        self.db.commit()

        # Run validation
        ValidationService.validate_invoice(self.db, "INV-NEW-FEB")
        self.db.refresh(inv_new)

        self.assertEqual(inv_new.approved_joining_amount, 0.0)
        self.assertEqual(inv_new.status, "EXCEPTION")

        # Check that validation result flags DUP_INVOICE_SAME_MONTH
        results = self.db.query(ValidationResult).filter(
            ValidationResult.invoice_record_id == inv_new.id
        ).all()
        reason_codes = [r.reason_code for r in results]
        self.assertIn("DUP_INVOICE_SAME_MONTH", reason_codes)

    def test_rule_18_amount_mismatch(self):
        """Invoice amount mismatch flags ERROR status and rejects approval amounts."""
        trainee = Trainee(
            id="T009",
            name="Ivan",
            doj=datetime.date(2026, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(trainee)
        self.db.commit()

        # Invoice record where Joining (1200) + 180 (600) + Other (100) = 1900, but Billed Total = 2000
        inv = InvoiceRecord(
            invoice_number="INV-MISMATCH",
            invoice_date=datetime.date(2026, 2, 1),
            trainee_id="T009",
            billed_name="Ivan",
            billed_joining_amount=1200.0,
            billed_180_days_amount=600.0,
            billed_other_amount=100.0,
            billed_total_amount=2000.0,
            status="PENDING",
            file_name="invoice_mismatch.xlsx"
        )
        self.db.add(inv)
        self.db.commit()

        # Run validation
        ValidationService.validate_invoice(self.db, "INV-MISMATCH")
        self.db.refresh(inv)

        self.assertEqual(inv.approved_joining_amount, 0.0)
        self.assertEqual(inv.approved_180_days_amount, 0.0)
        self.assertEqual(inv.status, "EXCEPTION")

        # Check that validation result flags AMOUNT_MISMATCH
        results = self.db.query(ValidationResult).filter(
            ValidationResult.invoice_record_id == inv.id
        ).all()
        reason_codes = [r.reason_code for r in results]
        self.assertIn("AMOUNT_MISMATCH", reason_codes)


class TestBDCImporter(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def _create_excel_bytes(self, data: list, columns: list) -> bytes:
        df = pd.DataFrame(data, columns=columns)
        out = io.BytesIO()
        df.to_excel(out, index=False)
        return out.getvalue()

    def test_bdc_import_basic_and_incremental(self):
        """Verify normal creation, no update if unchanged, and update on changes."""
        cols = ['Trainee ID', 'Name', 'DOJ', 'Scheme', 'Aadhaar', 'Ticket']
        data1 = [
            ['T001', 'Alice', '2026-01-01', 'NAPS', '111122223333', 'TKT100'],
            ['T002', 'Bob', '2026-01-02', 'B.Tech', '222233334444', 'TKT101']
        ]
        excel_bytes = self._create_excel_bytes(data1, cols)
        
        # 1. First import (all new trainees)
        res = ImportService.import_bdc_workbook(self.db, excel_bytes, "bdc_master.xlsx")
        self.assertEqual(res["created_count"], 2)
        self.assertEqual(res["updated_count"], 0)
        self.assertEqual(res["success_count"], 2)
        self.assertEqual(res["skipped_count"], 0)

        # Verify DB records
        t1 = self.db.query(Trainee).filter(Trainee.id == 'T001').first()
        self.assertIsNotNone(t1)
        self.assertEqual(t1.name, 'Alice')
        self.assertEqual(t1.aadhaar, '111122223333')
        self.assertEqual(t1.ticket_number, 'TKT100')

        # 2. Second import (unchanged data)
        res = ImportService.import_bdc_workbook(self.db, excel_bytes, "bdc_master.xlsx")
        self.assertEqual(res["created_count"], 0)
        self.assertEqual(res["updated_count"], 0) # Update only when changed!
        self.assertEqual(res["success_count"], 2)

        # 3. Third import (changed name, Aadhaar, and Ticket)
        data2 = [
            ['T001', 'Alice Cooper', '2026-01-01', 'NAPS', '111122225555', 'TKT999'], # Changed name, Aadhaar, Ticket
            ['T002', 'Bob', '2026-01-02', 'B.Tech', '222233334444', 'TKT101'] # Unchanged
        ]
        excel_bytes2 = self._create_excel_bytes(data2, cols)
        res = ImportService.import_bdc_workbook(self.db, excel_bytes2, "bdc_master.xlsx")
        self.assertEqual(res["created_count"], 0)
        self.assertEqual(res["updated_count"], 1)
        self.assertEqual(res["success_count"], 2)
        # Verify DB updates
        self.db.refresh(t1)
        self.assertEqual(t1.name, 'Alice Cooper')
        self.assertEqual(t1.aadhaar, '111122225555')
        self.assertEqual(t1.ticket_number, 'TKT999')

    def test_bdc_import_in_sheet_duplicates(self):
        """Verify that duplicate Trainee ID, Aadhaar, or Ticket in the same sheet update the existing trainee or skip on conflict."""
        cols = ['Trainee ID', 'Name', 'DOJ', 'Scheme', 'Aadhaar', 'Ticket']
        data = [
            ['T001', 'Alice', '2026-01-01', 'NAPS', '111122223333', 'TKT100'],
            ['T002', 'Bob', '2026-01-02', 'B.Tech', '111122223333', 'TKT101'], # Duplicate Aadhaar -> skip
            ['T003', 'Charlie', '2026-01-03', 'M.Tech', '222233334444', 'TKT100'], # Duplicate Ticket -> updates Alice
            ['T001', 'Alice Dupe', '2026-01-01', 'NAPS', '222233334445', 'TKT102'] # Duplicate Trainee ID -> updates Alice
        ]
        excel_bytes = self._create_excel_bytes(data, cols)
        res = ImportService.import_bdc_workbook(self.db, excel_bytes, "bdc_master.xlsx")
        
        self.assertEqual(res["success_count"], 3)
        self.assertEqual(res["skipped_count"], 1)

    def test_bdc_import_in_db_duplicates(self):
        """Verify that duplicates against existing database records update the trainee or skip on conflict."""
        # 1. Insert existing trainee
        t_exist = Trainee(
            id="T001",
            name="Alice",
            doj=datetime.date(2026, 1, 1),
            scheme="NAPS",
            aadhaar="111122223333",
            ticket_number="TKT100",
            status="ACTIVE"
        )
        self.db.add(t_exist)
        self.db.commit()

        cols = ['Trainee ID', 'Name', 'DOJ', 'Scheme', 'Aadhaar', 'Ticket']
        data = [
            ['T002', 'Bob', '2026-01-02', 'B.Tech', '111122223333', 'TKT101'], # Aadhaar already belongs to T001 -> skip
            ['T003', 'Charlie', '2026-01-03', 'M.Tech', '222233334444', 'TKT100'] # Ticket already belongs to T001 -> updates T001
        ]
        excel_bytes = self._create_excel_bytes(data, cols)
        res = ImportService.import_bdc_workbook(self.db, excel_bytes, "bdc_master.xlsx")

        self.assertEqual(res["success_count"], 1)
        self.assertEqual(res["skipped_count"], 1)

    def test_bdc_import_dynamic_column_and_robust_date(self):
        """Verify dynamic header keyword matching and robust Indian & Excel serial date parsing."""
        cols = ['reg no', 'employee name', 'date of joining', 'program', 'uid', 'boarding ticket']
        data = [
            ['T001', 'Alice', '25/06/2026', 'NAPS', '111122223333', 'TKT100'],
            ['T002', 'Bob', '2026-06-25', 'B.Tech', '222233334444', 'TKT101'],
            ['T003', 'Charlie', 46198, 'M.Tech', '333344445555', 'TKT102'] # 46198 is Excel serial for 2026-06-25
        ]
        excel_bytes = self._create_excel_bytes(data, cols)
        res = ImportService.import_bdc_workbook(self.db, excel_bytes, "bdc_master.xlsx")
        
        self.assertEqual(res["success_count"], 3)
        self.assertEqual(res["skipped_count"], 0)

        # Check that dates were parsed correctly
        t1 = self.db.query(Trainee).filter(Trainee.id == 'T001').first()
        t2 = self.db.query(Trainee).filter(Trainee.id == 'T002').first()
        t3 = self.db.query(Trainee).filter(Trainee.id == 'T003').first()

        expected_date = datetime.date(2026, 6, 25)
        self.assertEqual(t1.doj, expected_date)
        self.assertEqual(t2.doj, expected_date)
        self.assertEqual(t3.doj, expected_date)

    def test_bdc_import_missing_columns(self):
        """Verify error is raised if key columns are missing."""
        cols = ['Trainee ID', 'Name']
        data = [['T001', 'Alice']]
        excel_bytes = self._create_excel_bytes(data, cols)
        with self.assertRaises(ValueError):
            ImportService.import_bdc_workbook(self.db, excel_bytes, "bdc_master.xlsx")


class TestValidationRules(unittest.TestCase):
    def test_trainee_not_found_rule(self):
        from backend.app.services.validation_service import TraineeNotFoundRule
        rule = TraineeNotFoundRule()
        class MockRecord:
            trainee_id = "T001"
            extra_data = {"trainee_id": "T001"}
        
        app_j, app_180, results, stop = rule.evaluate(
            record=MockRecord(),
            trainee=None,
            history=[],
            config={},
            state={},
            app_joining=1200.0,
            app_180=600.0
        )
        self.assertEqual(app_j, 0.0)
        self.assertEqual(app_180, 0.0)
        self.assertTrue(stop)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["rule_name"], "Trainee Not Found")

    def test_blocked_trainee_rule(self):
        from backend.app.services.validation_service import BlockedTraineeRule
        rule = BlockedTraineeRule()
        class MockTrainee:
            id = "T001"
            status = "BLOCKED"
            blocked_reason = "Test Blocked"
        
        app_j, app_180, results, stop = rule.evaluate(
            record=None,
            trainee=MockTrainee(),
            history=[],
            config={},
            state={},
            app_joining=1200.0,
            app_180=600.0
        )
        self.assertEqual(app_j, 0.0)
        self.assertEqual(app_180, 0.0)
        self.assertTrue(stop)
        self.assertEqual(results[0]["rule_name"], "Blocked Trainee Billing")

    def test_excess_items_ignored_rule(self):
        from backend.app.services.validation_service import ExcessItemsIgnoredRule
        rule = ExcessItemsIgnoredRule()
        class MockRecord:
            billed_other_amount = 500.0
        
        app_j, app_180, results, stop = rule.evaluate(
            record=MockRecord(),
            trainee=None,
            history=[],
            config={},
            state={},
            app_joining=1200.0,
            app_180=600.0
        )
        self.assertEqual(app_j, 1200.0)
        self.assertEqual(app_180, 600.0)
        self.assertFalse(stop)
        self.assertEqual(results[0]["rule_name"], "Excess Items Ignored")


if __name__ == "__main__":
    unittest.main()

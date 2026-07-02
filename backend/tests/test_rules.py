import unittest
import datetime
import io
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.db import Base
from backend.app.models.models import Trainee, InvoiceRecord, PaymentLedger, ValidationResult, SeparationRecord
from backend.app.services.import_service import ImportService
from backend.app.services.validation_service import ValidationService
from backend.app.services.rules import (
    Rule30Days,
    Rule180Days,
    RuleJoiningLimit,
    RuleAnnualLimit,
    RuleDuplicateBilling,
    RuleDuplicateTicket,
    RuleDuplicateAadhaar,
    RuleBlockedEmployee,
    RuleKitLimit,
    RuleTraineeNotFound,
    RuleSeparationChecks
)

class TestTMPVLBusinessEngine(unittest.TestCase):
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

    def test_rule_left_less_than_30_days(self):
        """Trainee left < 30 days must be blocked and joining/180-days rejected."""
        trainee = Trainee(
            id="T001",
            name="Alice",
            doj=datetime.date(2026, 1, 1),
            dol=datetime.date(2026, 1, 15), # 14 days tenure
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(trainee)
        self.db.commit()

        record = InvoiceRecord(
            invoice_number="INV-001",
            invoice_date=datetime.date(2026, 2, 1),
            trainee_id="T001",
            billed_name="Alice",
            billed_joining_amount=1200.0,
            billed_180_days_amount=600.0,
            status="PENDING",
            file_name="invoice.xlsx"
        )
        self.db.add(record)
        self.db.commit()

        # Run validation
        ValidationService.validate_invoice(self.db, "INV-001")
        self.db.refresh(trainee)
        self.db.refresh(record)

        self.assertEqual(trainee.status, "BLOCKED")
        self.assertIn("Resigned before 30 days", trainee.blocked_reason)
        self.assertEqual(record.approved_joining_amount, 0.0)
        self.assertEqual(record.approved_180_days_amount, 0.0)
        self.assertEqual(record.status, "EXCEPTION")

    def test_rule_left_less_than_180_days(self):
        """Trainee left < 180 days has post-180 days payment rejected."""
        trainee = Trainee(
            id="T002",
            name="Bob",
            doj=datetime.date(2026, 1, 1),
            dol=datetime.date(2026, 4, 1), # 90 days tenure
            scheme="B.Tech",
            status="SEPARATED"
        )
        self.db.add(trainee)
        self.db.commit()

        record = InvoiceRecord(
            invoice_number="INV-002",
            invoice_date=datetime.date(2026, 5, 1),
            trainee_id="T002",
            billed_name="Bob",
            billed_joining_amount=1200.0,
            billed_180_days_amount=600.0,
            status="PENDING",
            file_name="invoice.xlsx"
        )
        self.db.add(record)
        self.db.commit()

        ValidationService.validate_invoice(self.db, "INV-002")
        self.db.refresh(record)

        # Billed 180 days is rejected. Billed joining is also rejected since it wasn't approved prior to separation.
        self.assertEqual(record.approved_joining_amount, 0.0)
        self.assertEqual(record.approved_180_days_amount, 0.0)

    def test_rule_duplicate_billing(self):
        """Duplicate billing in the same cycle must flag FRAUD and reject duplicate amounts."""
        trainee = Trainee(
            id="T003",
            name="Charlie",
            doj=datetime.date(2026, 1, 1),
            scheme="M.Tech",
            status="ACTIVE"
        )
        self.db.add(trainee)
        self.db.commit()

        # Two rows billing joining for Charlie in same invoice
        rec1 = InvoiceRecord(
            invoice_number="INV-003",
            invoice_date=datetime.date(2026, 2, 1),
            trainee_id="T003",
            billed_name="Charlie",
            billed_joining_amount=1200.0,
            status="PENDING",
            file_name="invoice.xlsx"
        )
        rec2 = InvoiceRecord(
            invoice_number="INV-003",
            invoice_date=datetime.date(2026, 2, 1),
            trainee_id="T003",
            billed_name="Charlie",
            billed_joining_amount=1200.0,
            status="PENDING",
            file_name="invoice.xlsx"
        )
        self.db.add_all([rec1, rec2])
        self.db.commit()

        ValidationService.validate_invoice(self.db, "INV-003")
        self.db.refresh(rec1)
        self.db.refresh(rec2)

        self.assertEqual(rec1.approved_joining_amount, 1200.0)
        self.assertEqual(rec2.approved_joining_amount, 0.0)
        self.assertEqual(rec2.status, "EXCEPTION")

    def test_rule_duplicate_ticket(self):
        """Duplicate ticket in same invoice or DB is rejected as FRAUD."""
        rule = RuleDuplicateTicket()
        class MockRecord:
            billed_joining_amount = 1200.0
            billed_180_days_amount = 0.0
        class MockTrainee:
            id = "T004A"
            ticket_number = "TKT007"
        
        # 1. First evaluation: should pass and add to seen_tickets
        state = {"seen_tickets": {}, "db_tickets": {}}
        res1 = rule.evaluate(MockRecord(), MockTrainee(), [], {}, state, 1200.0, 0.0)
        self.assertTrue(res1.passed)
        self.assertEqual(state["seen_tickets"]["TKT007"], "T004A")
        
        # 2. Second evaluation with different trainee ID but same ticket: should fail
        class MockTrainee2:
            id = "T004B"
            ticket_number = "TKT007"
        res2 = rule.evaluate(MockRecord(), MockTrainee2(), [], {}, state, 1200.0, 0.0)
        self.assertFalse(res2.passed)
        self.assertEqual(res2.severity, "FRAUD")
        self.assertIn("Duplicate ticket", res2.reason)

    def test_rule_duplicate_aadhaar(self):
        """Duplicate Aadhaar in same invoice or DB is rejected as FRAUD."""
        rule = RuleDuplicateAadhaar()
        class MockRecord:
            billed_joining_amount = 1200.0
            billed_180_days_amount = 0.0
        class MockTrainee:
            id = "T005A"
            aadhaar = "123456789012"
        
        # 1. First evaluation: should pass
        state = {"seen_aadhaars": {}, "db_aadhaars": {}}
        res1 = rule.evaluate(MockRecord(), MockTrainee(), [], {}, state, 1200.0, 0.0)
        self.assertTrue(res1.passed)
        self.assertEqual(state["seen_aadhaars"]["123456789012"], "T005A")
        
        # 2. Second evaluation with different trainee ID but same Aadhaar: should fail
        class MockTrainee2:
            id = "T005B"
            aadhaar = "1234-5678-9012"
        res2 = rule.evaluate(MockRecord(), MockTrainee2(), [], {}, state, 1200.0, 0.0)
        self.assertFalse(res2.passed)
        self.assertEqual(res2.severity, "FRAUD")
        self.assertIn("Duplicate Aadhaar", res2.reason)

    def test_rule_kit_limit(self):
        """Uniform / garment / kit billed by vendor must be ignored/rejected, causing warning."""
        t = Trainee(
            id="T006",
            name="Frank",
            doj=datetime.date(2026, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(t)
        self.db.commit()

        rec = InvoiceRecord(
            invoice_number="INV-006",
            invoice_date=datetime.date(2026, 2, 1),
            trainee_id="T006",
            billed_name="Frank",
            billed_joining_amount=1200.0,
            billed_other_amount=500.0, # uniformity kit billed
            status="PENDING",
            file_name="invoice.xlsx"
        )
        self.db.add(rec)
        self.db.commit()

        ValidationService.validate_invoice(self.db, "INV-006")
        self.db.refresh(rec)

        self.assertEqual(rec.approved_joining_amount, 1200.0)
        self.assertEqual(rec.approved_total_amount, 1200.0)
        self.assertEqual(rec.status, "VALIDATED") # remains validated, but warning exists
        flags = self.db.query(ValidationResult).filter(ValidationResult.invoice_record_id == rec.id).all()
        self.assertTrue(any(f.rule_name == "Excess Items Ignored" for f in flags))

    def test_rule_joining_cap(self):
        """Joining cap at ₹1200 limit."""
        t = Trainee(
            id="T007",
            name="Gary",
            doj=datetime.date(2026, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(t)
        
        # Already paid ₹800 joining
        ledger = PaymentLedger(
            trainee_id="T007",
            invoice_number="INV-PREV",
            payment_type="JOINING",
            amount_paid=800.0,
            payment_date=datetime.date(2026, 2, 1)
        )
        self.db.add(ledger)
        self.db.commit()

        rec = InvoiceRecord(
            invoice_number="INV-007",
            invoice_date=datetime.date(2026, 3, 1),
            trainee_id="T007",
            billed_name="Gary",
            billed_joining_amount=1200.0,
            status="PENDING",
            file_name="invoice.xlsx"
        )
        self.db.add(rec)
        self.db.commit()

        ValidationService.validate_invoice(self.db, "INV-007")
        self.db.refresh(rec)

        # Capped at remaining ₹400
        self.assertEqual(rec.approved_joining_amount, 400.0)
        self.assertEqual(rec.status, "VALIDATED")

    def test_rule_six_month_payment(self):
        """Six-month payment cap at ₹600."""
        t = Trainee(
            id="T008",
            name="Harry",
            doj=datetime.date(2026, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(t)
        
        # Already paid ₹400 for 180_DAYS
        ledger = PaymentLedger(
            trainee_id="T008",
            invoice_number="INV-PREV",
            payment_type="180_DAYS",
            amount_paid=400.0,
            payment_date=datetime.date(2026, 7, 1)
        )
        self.db.add(ledger)
        self.db.commit()

        rec = InvoiceRecord(
            invoice_number="INV-008",
            invoice_date=datetime.date(2026, 8, 1),
            trainee_id="T008",
            billed_name="Harry",
            billed_joining_amount=0.0,
            billed_180_days_amount=600.0,
            status="PENDING",
            file_name="invoice.xlsx"
        )
        self.db.add(rec)
        self.db.commit()

        ValidationService.validate_invoice(self.db, "INV-008")
        self.db.refresh(rec)

        # Capped at remaining ₹200
        self.assertEqual(rec.approved_180_days_amount, 200.0)

    def test_rule_annual_cap(self):
        """Never allow total payout to exceed ₹1800 cap per trainee."""
        t = Trainee(
            id="T009",
            name="Ian",
            doj=datetime.date(2026, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add(t)

        # Paid ₹1200 joining and ₹500 180_DAYS historically (Total = ₹1700)
        l1 = PaymentLedger(
            trainee_id="T009",
            invoice_number="INV-PREV1",
            payment_type="JOINING",
            amount_paid=1200.0,
            payment_date=datetime.date(2026, 2, 1)
        )
        l2 = PaymentLedger(
            trainee_id="T009",
            invoice_number="INV-PREV2",
            payment_type="180_DAYS",
            amount_paid=500.0,
            payment_date=datetime.date(2026, 7, 1)
        )
        self.db.add_all([l1, l2])
        self.db.commit()

        rec = InvoiceRecord(
            invoice_number="INV-009",
            invoice_date=datetime.date(2026, 8, 1),
            trainee_id="T009",
            billed_name="Ian",
            billed_joining_amount=0.0,
            billed_180_days_amount=600.0, # billed for remaining 180_days amount
            status="PENDING",
            file_name="invoice.xlsx"
        )
        self.db.add(rec)
        self.db.commit()

        ValidationService.validate_invoice(self.db, "INV-009")
        self.db.refresh(rec)

        # Capped at remaining ₹100 (₹1800 - ₹1700)
        self.assertEqual(rec.approved_180_days_amount, 100.0)
        self.assertEqual(rec.approved_total_amount, 100.0)

    def test_bdc_incremental_sync_stats(self):
        """Test BDC sync returns insert_count, update_count, skip_count, and error_count."""
        cols = ['Trainee ID', 'Name', 'DOJ', 'Scheme', 'Aadhaar', 'Ticket']
        
        # 1. First import: Jack (new insertion)
        data1 = [
            ['T100', 'Jack', '2026-01-01', 'NAPS', '111111111111', 'TKT100']
        ]
        excel_bytes1 = self._create_excel_bytes(data1, cols)
        res1 = ImportService.import_bdc_workbook(self.db, excel_bytes1, "bdc_master.xlsx")
        self.assertEqual(res1["insert_count"], 1)
        self.assertEqual(res1["update_count"], 0)
        self.assertEqual(res1["skip_count"], 0)

        # 2. Second import: Update Jack, Insert Karen, Error Leo (ticket conflict)
        data2 = [
            ['T100', 'Jack New', '2026-01-01', 'NAPS', '111111111111', 'TKT100'],
            ['T101', 'Karen', '2026-01-02', 'B.Tech', '222222222222', 'TKT101'],
            ['T102', 'Leo', '2026-01-03', 'M.Tech', '333333333333', 'TKT100'] # ticket duplicate
        ]
        excel_bytes2 = self._create_excel_bytes(data2, cols)
        res2 = ImportService.import_bdc_workbook(self.db, excel_bytes2, "bdc_master.xlsx")
        self.assertEqual(res2["insert_count"], 1)
        self.assertEqual(res2["update_count"], 1)
        self.assertEqual(res2["error_count"], 1)

        # 3. Third import: Karen unchanged (skip)
        data3 = [
            ['T101', 'Karen', '2026-01-02', 'B.Tech', '222222222222', 'TKT101']
        ]
        excel_bytes3 = self._create_excel_bytes(data3, cols)
        res3 = ImportService.import_bdc_workbook(self.db, excel_bytes3, "bdc_master.xlsx")
        self.assertEqual(res3["skip_count"], 1)
        self.assertEqual(res3["insert_count"], 0)
        self.assertEqual(res3["update_count"], 0)

    def test_separation_early_exit_block_and_history(self):
        """Separation processing must calculate days worked, block early exits (< 30 days) and record history."""
        t1 = Trainee(
            id="T200",
            name="Mike",
            doj=datetime.date(2026, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        t2 = Trainee(
            id="T201",
            name="Nancy",
            doj=datetime.date(2026, 1, 1),
            scheme="B.Tech",
            status="ACTIVE"
        )
        self.db.add_all([t1, t2])
        self.db.commit()

        # Excel file for separation using multiple sheets
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df1 = pd.DataFrame([['T200', '15/01/2026', 'Personal reasons']], columns=['Trainee ID', 'Date of Leaving', 'Reason'])
            df1.to_excel(writer, sheet_name='NAPS', index=False)
            df2 = pd.DataFrame([['T201', '15/02/2026', 'Completed term']], columns=['Trainee ID', 'Date of Leaving', 'Reason'])
            df2.to_excel(writer, sheet_name='B.Tech', index=False)
        excel_bytes = out.getvalue()

        ImportService.import_separation_workbook(self.db, excel_bytes, "separations.xlsx")

        self.db.refresh(t1)
        self.db.refresh(t2)

        # Check statuses
        self.assertEqual(t1.status, "BLOCKED")
        self.assertIn("Resigned before 30 days", t1.blocked_reason)
        self.assertEqual(t2.status, "SEPARATED")

        # Check SeparationRecord entries are recorded
        s1 = self.db.query(SeparationRecord).filter(SeparationRecord.trainee_id == "T200").first()
        s2 = self.db.query(SeparationRecord).filter(SeparationRecord.trainee_id == "T201").first()

        self.assertIsNotNone(s1)
        self.assertEqual(s1.extra_data["days_worked"], 14)
        self.assertTrue(s1.extra_data["early_exit"])

        self.assertIsNotNone(s2)
        self.assertEqual(s2.extra_data["days_worked"], 45)
        self.assertFalse(s2.extra_data["early_exit"])

    def test_bdc_rehire_detection(self):
        """Test that importing a BDC record with doj > dol reactivates separated/blocked trainees."""
        trainee = Trainee(
            id="T300",
            name="John Rehire",
            doj=datetime.date(2026, 1, 1),
            dol=datetime.date(2026, 2, 1),
            scheme="NAPS",
            status="SEPARATED",
            ticket_number="TKT300",
            aadhaar="333333333330"
        )
        self.db.add(trainee)
        self.db.commit()

        cols = ['Trainee ID', 'Name', 'DOJ', 'Scheme', 'Aadhaar', 'Ticket']
        data = [
            ['T300', 'John Rehire', '2026-03-01', 'NAPS', '333333333330', 'TKT300']
        ]
        excel_bytes = self._create_excel_bytes(data, cols)
        res = ImportService.import_bdc_workbook(self.db, excel_bytes, "bdc_rehires.xlsx")

        self.db.refresh(trainee)
        self.assertEqual(res["update_count"], 1)
        self.assertEqual(trainee.status, "ACTIVE")
        self.assertEqual(trainee.doj, datetime.date(2026, 3, 1))
        self.assertIsNone(trainee.dol)
        
        # Verify previous lifecycle saved in extra_data
        lifecycles = trainee.extra_data.get("lifecycles", [])
        self.assertEqual(len(lifecycles), 1)
        self.assertEqual(lifecycles[0]["lifecycle_number"], 1)
        self.assertEqual(lifecycles[0]["doj"], "2026-01-01")
        self.assertEqual(lifecycles[0]["dol"], "2026-02-01")

    def test_append_only_separation_history(self):
        """Test that multiple separation events for a trainee enrich separation history instead of replacing it."""
        trainee = Trainee(
            id="T400",
            name="Alice History",
            doj=datetime.date(2026, 1, 1),
            scheme="NAPS",
            status="ACTIVE",
            ticket_number="TKT400",
            aadhaar="444444444440"
        )
        self.db.add(trainee)
        self.db.commit()

        # 1. First separation (tenure 14 days)
        out1 = io.BytesIO()
        df1 = pd.DataFrame([['T400', '15/01/2026', 'Left early']], columns=['Trainee ID', 'Date of Leaving', 'Reason'])
        df1.to_excel(out1, index=False)
        ImportService.import_separation_workbook(self.db, out1.getvalue(), "separation_v1.xlsx")

        # Refresh and verify
        self.db.refresh(trainee)
        self.assertEqual(trainee.status, "BLOCKED")
        self.assertEqual(trainee.dol, datetime.date(2026, 1, 15))
        self.assertEqual(len(trainee.separation_records), 1)

        # 2. Rehire trainee
        cols = ['Trainee ID', 'Name', 'DOJ', 'Scheme', 'Aadhaar', 'Ticket']
        data = [['T400', 'Alice History', '2026-02-01', 'NAPS', '444444444440', 'TKT400']]
        ImportService.import_bdc_workbook(self.db, self._create_excel_bytes(data, cols), "bdc_rehire.xlsx")

        # 3. Second separation (tenure 27 days)
        out2 = io.BytesIO()
        df2 = pd.DataFrame([['T400', '28/02/2026', 'Left early again']], columns=['Trainee ID', 'Date of Leaving', 'Reason'])
        df2.to_excel(out2, index=False)
        ImportService.import_separation_workbook(self.db, out2.getvalue(), "separation_v2.xlsx")

        # Refresh and verify
        self.db.refresh(trainee)
        self.assertEqual(len(trainee.separation_records), 2)
        # Verify chronological sorting order and details
        records = sorted(trainee.separation_records, key=lambda x: x.dol)
        self.assertEqual(records[0].dol, datetime.date(2026, 1, 15))
        self.assertEqual(records[1].dol, datetime.date(2026, 2, 28))

    def test_sheet_level_fault_tolerance(self):
        """Test that if one sheet fails to process, other sheets in the workbook still process successfully."""
        t1 = Trainee(
            id="T500",
            name="John Sheet1",
            doj=datetime.date(2026, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        t2 = Trainee(
            id="T501",
            name="Jane Sheet2",
            doj=datetime.date(2026, 1, 1),
            scheme="NAPS",
            status="ACTIVE"
        )
        self.db.add_all([t1, t2])
        self.db.commit()

        # Excel file where Sheet 1 succeeds and Sheet 2 raises an error (missing Trainee ID)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df1 = pd.DataFrame([['T500', '15/02/2026', 'Terminated']], columns=['Trainee ID', 'Date of Leaving', 'Reason'])
            df1.to_excel(writer, sheet_name='Sheet1', index=False)
            df2 = pd.DataFrame([['', '15/02/2026', 'Terminated']], columns=['Trainee ID', 'Date of Leaving', 'Reason'])
            df2.to_excel(writer, sheet_name='Sheet2', index=False)
        excel_bytes = out.getvalue()

        res = ImportService.import_separation_workbook(self.db, excel_bytes, "separations_multi.xlsx")

        self.db.refresh(t1)
        self.db.refresh(t2)

        # Sheet 1 processed, Sheet 2 failed
        self.assertEqual(t1.status, "SEPARATED")
        self.assertEqual(t2.status, "ACTIVE")
        self.assertIn("Sheet1", res["processed_sheets"])
        self.assertEqual(res["failed_records"], 1)
        self.assertTrue(len(res["errors"]) > 0)


class TestSeparationRuleAndReasonCodes(unittest.TestCase):
    """Tests for RuleSeparationChecks and reason_code/recommended_action persistence."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def _make_record(self, trainee_id: str, invoice_date: datetime.date,
                     joining: float = 1200.0, days180: float = 600.0) -> InvoiceRecord:
        record = InvoiceRecord(
            invoice_number="INV-SEP-001",
            invoice_date=invoice_date,
            trainee_id=trainee_id,
            billed_name="Test Trainee",
            billed_joining_amount=joining,
            billed_180_days_amount=days180,
            billed_total_amount=joining + days180,
            status="PENDING",
            file_name="invoice.xlsx"
        )
        self.db.add(record)
        self.db.commit()
        return record

    def _make_trainee(self, trainee_id: str, doj: datetime.date,
                      dol: datetime.date = None, status: str = "ACTIVE") -> Trainee:
        trainee = Trainee(
            id=trainee_id,
            name="Test Trainee",
            doj=doj,
            dol=dol,
            scheme="NAPS",
            status=status
        )
        self.db.add(trainee)
        self.db.commit()
        return trainee

    # ------------------------------------------------------------------ #
    #  RuleSeparationChecks – Unit Level                                  #
    # ------------------------------------------------------------------ #

    def test_sep_before_invoice_raises_error(self):
        """SEP_BEFORE_INVOICE: trainee DOL month is strictly before invoice month."""
        trainee = self._make_trainee("T-SEP1", datetime.date(2025, 8, 1),
                                     dol=datetime.date(2026, 1, 15))
        record = self._make_record("T-SEP1", datetime.date(2026, 3, 1))

        rule = RuleSeparationChecks()
        result = rule.evaluate(
            record=record, trainee=trainee, history=[],
            config={}, state={},
            current_joining=1200.0, current_180=600.0
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.severity, "ERROR")
        self.assertEqual(result.approved_joining, 0.0)
        self.assertEqual(result.approved_180, 0.0)
        self.assertTrue(any(f["reason_code"] == "SEP_BEFORE_INVOICE" for f in result.failures))
        self.assertTrue(any("Reject invoice payouts" in f["recommended_action"] for f in result.failures))

    def test_invoice_after_separation_same_month(self):
        """INVOICE_AFTER_SEPARATION: billing date strictly after DOL in same month."""
        trainee = self._make_trainee("T-SEP2", datetime.date(2025, 6, 1),
                                     dol=datetime.date(2026, 3, 10))
        record = self._make_record("T-SEP2", datetime.date(2026, 3, 20))

        rule = RuleSeparationChecks()
        result = rule.evaluate(
            record=record, trainee=trainee, history=[],
            config={}, state={},
            current_joining=1200.0, current_180=600.0
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.severity, "ERROR")
        self.assertEqual(result.approved_joining, 0.0)
        self.assertEqual(result.approved_180, 0.0)
        self.assertTrue(any(f["reason_code"] == "INVOICE_AFTER_SEPARATION" for f in result.failures))
        self.assertTrue(any("Do not approve payouts" in f["recommended_action"] for f in result.failures))

    def test_no_separation_passes(self):
        """No DOL on trainee — separation rule should pass without penalty."""
        trainee = self._make_trainee("T-SEP3", datetime.date(2025, 6, 1))
        record = self._make_record("T-SEP3", datetime.date(2026, 3, 20))

        rule = RuleSeparationChecks()
        result = rule.evaluate(
            record=record, trainee=trainee, history=[],
            config={}, state={},
            current_joining=1200.0, current_180=600.0
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.approved_joining, 1200.0)
        self.assertEqual(result.approved_180, 600.0)
        self.assertFalse(result.failures)

    def test_invoice_on_same_day_as_dol_passes(self):
        """Invoice exactly on DOL date should pass (not strictly after)."""
        trainee = self._make_trainee("T-SEP4", datetime.date(2025, 6, 1),
                                     dol=datetime.date(2026, 3, 15))
        record = self._make_record("T-SEP4", datetime.date(2026, 3, 15))

        rule = RuleSeparationChecks()
        result = rule.evaluate(
            record=record, trainee=trainee, history=[],
            config={}, state={},
            current_joining=1200.0, current_180=600.0
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.approved_joining, 1200.0)

    # ------------------------------------------------------------------ #
    #  Reason Code Persistence – Integration Level                         #
    # ------------------------------------------------------------------ #

    def test_reason_code_persisted_for_emp_not_found(self):
        """EMP_NOT_FOUND reason_code must be stored in validation_results table."""
        # No trainee added — record references a non-existent trainee
        record = InvoiceRecord(
            invoice_number="INV-NOFOUND",
            invoice_date=datetime.date(2026, 3, 1),
            trainee_id=None,
            billed_name="Ghost Employee",
            billed_joining_amount=1200.0,
            billed_180_days_amount=0.0,
            billed_total_amount=1200.0,
            status="PENDING",
            file_name="invoice.xlsx"
        )
        self.db.add(record)
        self.db.commit()

        ValidationService.validate_invoice(self.db, "INV-NOFOUND")

        results = self.db.query(ValidationResult).filter(
            ValidationResult.invoice_record_id == record.id
        ).all()

        self.assertTrue(len(results) > 0)
        emp_not_found = next((r for r in results if r.reason_code == "EMP_NOT_FOUND"), None)
        self.assertIsNotNone(emp_not_found, "EMP_NOT_FOUND reason_code not persisted")
        self.assertIsNotNone(emp_not_found.recommended_action)
        self.assertIn("Reject payment", emp_not_found.recommended_action)

    def test_reason_code_persisted_for_sep_before_invoice(self):
        """SEP_BEFORE_INVOICE reason_code and recommended_action must be persisted."""
        trainee = self._make_trainee("T-PERSIST", datetime.date(2025, 8, 1),
                                     dol=datetime.date(2026, 1, 10),
                                     status="SEPARATED")
        record = self._make_record("T-PERSIST", datetime.date(2026, 4, 1))

        ValidationService.validate_invoice(self.db, "INV-SEP-001")

        results = self.db.query(ValidationResult).filter(
            ValidationResult.invoice_record_id == record.id
        ).all()

        sep_result = next((r for r in results if r.reason_code == "SEP_BEFORE_INVOICE"), None)
        self.assertIsNotNone(sep_result, "SEP_BEFORE_INVOICE reason_code not persisted to DB")
        self.assertIsNotNone(sep_result.recommended_action)
        self.assertIn("separated prior", sep_result.recommended_action)

    def test_recommended_action_not_null_for_blocked_employee(self):
        """EMP_BLOCKED recommended_action must be non-null and meaningful."""
        trainee = self._make_trainee("T-BLOCK", datetime.date(2025, 1, 1),
                                     status="BLOCKED")
        trainee.blocked_reason = "Policy violation"
        self.db.commit()

        record = self._make_record("T-BLOCK", datetime.date(2026, 3, 1))
        ValidationService.validate_invoice(self.db, "INV-SEP-001")

        results = self.db.query(ValidationResult).filter(
            ValidationResult.invoice_record_id == record.id
        ).all()

        blocked_result = next((r for r in results if r.reason_code == "EMP_BLOCKED"), None)
        self.assertIsNotNone(blocked_result, "EMP_BLOCKED reason_code not persisted")
        self.assertIsNotNone(blocked_result.recommended_action)
        self.assertIn("Reject all payments", blocked_result.recommended_action)

    def test_reason_code_not_null_for_30_day_rule(self):
        """LEFT_WITHIN_30_DAYS reason_code must be persisted after validation."""
        trainee = self._make_trainee("T-30D", datetime.date(2026, 1, 1),
                                     dol=datetime.date(2026, 1, 10))
        record = self._make_record("T-30D", datetime.date(2026, 3, 1))

        ValidationService.validate_invoice(self.db, "INV-SEP-001")

        results = self.db.query(ValidationResult).filter(
            ValidationResult.invoice_record_id == record.id
        ).all()
        reason_codes = [r.reason_code for r in results]
        self.assertIn("LEFT_WITHIN_30_DAYS", reason_codes)

        thirty_day_result = next(r for r in results if r.reason_code == "LEFT_WITHIN_30_DAYS")
        self.assertIsNotNone(thirty_day_result.recommended_action)


if __name__ == "__main__":
    unittest.main()

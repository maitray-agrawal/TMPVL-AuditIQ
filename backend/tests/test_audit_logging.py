import unittest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.db import Base
from backend.app.models.models import AuditLog, Trainee
from backend.app.repositories.repositories import AuditLogRepository

class TestAuditLoggingSystem(unittest.TestCase):
    def setUp(self):
        # Configure in-memory database for testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_audit_log_fields_persistence(self):
        """Verify that AuditLog fields persist correctly including JSON structures."""
        # 1. Create a rich log entry
        log_entry = AuditLog(
            action="IMPORT_BDC_WORKBOOK",
            module="BDC_UPLOAD",
            details="Imported BDC Master sheet with 2 trainees.",
            operator="Admin",
            workbook="bdc_master_2026.xlsx",
            sheet="Trainees",
            rows_count=2,
            duration=1.45,
            inserted=2,
            updated=0,
            failed=0,
            warnings=1,
            errors=0,
            before_state={"trainees": []},
            after_state={"trainees": [{"id": "T001", "name": "Alice"}]},
            invoice_number="INV-2026",
            employee_id="T001"
        )
        self.db.add(log_entry)
        self.db.commit()

        # 2. Query the log entry back
        queried = self.db.query(AuditLog).filter_by(action="IMPORT_BDC_WORKBOOK").first()
        self.assertIsNotNone(queried)
        self.assertEqual(queried.operator, "Admin")
        self.assertEqual(queried.workbook, "bdc_master_2026.xlsx")
        self.assertEqual(queried.sheet, "Trainees")
        self.assertEqual(queried.rows_count, 2)
        self.assertEqual(queried.duration, 1.45)
        self.assertEqual(queried.inserted, 2)
        self.assertEqual(queried.updated, 0)
        self.assertEqual(queried.failed, 0)
        self.assertEqual(queried.warnings, 1)
        self.assertEqual(queried.errors, 0)
        self.assertEqual(queried.before_state, {"trainees": []})
        self.assertEqual(queried.after_state, {"trainees": [{"id": "T001", "name": "Alice"}]})
        self.assertEqual(queried.invoice_number, "INV-2026")
        self.assertEqual(queried.employee_id, "T001")

    def test_audit_log_repository_add_and_filters(self):
        """Verify repository add_log wrapper and multi-criteria query filtering."""
        # Add a couple logs with different properties
        AuditLogRepository.add_log(
            db=self.db,
            action="RUN_VALIDATION",
            module="VALIDATION",
            details="Validated Quess invoice.",
            operator="System",
            workbook="quess_invoice.xlsx",
            sheet="Sheet1",
            rows_count=100,
            duration=0.5,
            inserted=0,
            updated=100,
            failed=0,
            warnings=5,
            errors=0,
            invoice_number="INV-QUESS-01"
        )

        AuditLogRepository.add_log(
            db=self.db,
            action="BLOCK_TRAINEE",
            module="EMPLOYEE_MASTER",
            details="Blocked trainee due to separation.",
            operator="Admin",
            employee_id="T1001",
            workbook="separations.xlsx",
            invoice_number="INV-QUESS-02"
        )

        # 1. Filter by employee_id
        logs_emp = AuditLogRepository.get_logs(self.db, employee_id="T1001")
        self.assertEqual(len(logs_emp), 1)
        self.assertEqual(logs_emp[0].action, "BLOCK_TRAINEE")

        # 2. Filter by invoice_number
        logs_inv = AuditLogRepository.get_logs(self.db, invoice_number="INV-QUESS-01")
        self.assertEqual(len(logs_inv), 1)
        self.assertEqual(logs_inv[0].action, "RUN_VALIDATION")

        # 3. Filter by workbook
        logs_wb = AuditLogRepository.get_logs(self.db, workbook="separations.xlsx")
        self.assertEqual(len(logs_wb), 1)
        self.assertEqual(logs_wb[0].action, "BLOCK_TRAINEE")

        # 4. Filter by date range (using string timestamps)
        today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        logs_date = AuditLogRepository.get_logs(self.db, date_from=today_str, date_to=today_str)
        self.assertEqual(len(logs_date), 2)

        # 5. Filter by action
        logs_act = AuditLogRepository.get_logs(self.db, action="RUN_VALIDATION")
        self.assertEqual(len(logs_act), 1)
        self.assertEqual(logs_act[0].action, "RUN_VALIDATION")

    def test_audit_log_append_only_nature(self):
        """Verify that logs cannot be deleted or modified through Repository layer (no deletion methods exposed)."""
        # Ensure there are no delete methods on AuditLogRepository
        self.assertFalse(hasattr(AuditLogRepository, 'delete_log'))
        self.assertFalse(hasattr(AuditLogRepository, 'clear_logs'))
        self.assertFalse(hasattr(AuditLogRepository, 'delete_by_id'))

if __name__ == "__main__":
    unittest.main()

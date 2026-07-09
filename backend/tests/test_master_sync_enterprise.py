import unittest
import datetime
import io
import os
import openpyxl
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.db import Base, get_db
from backend.main import app
from backend.app.models.models import Trainee, BDCRecord, SeparationRecord, UploadHistory, TraineeLifecycle, ValidationResult, InvoiceRecord
from backend.app.services.import_service import ImportService

class TestMasterSyncEnterprise(unittest.TestCase):
    def setUp(self):
        # 1. Setup SQLite file DB for tests to allow multi-connection visibility
        self.db_path = "/home/ubuntu/Desktop/Tata Projects/TMPVL AuditIQ/test_db.sqlite"
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass
                
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        Base.metadata.create_all(self.engine)
        
        # 2. Init Session
        self.TestSession = sessionmaker(bind=self.engine)
        self.db = self.TestSession()
        
        # 3. Setup FastAPI TestClient with DB overrides
        def override_get_db():
            db = self.TestSession()
            try:
                yield db
            finally:
                db.close()
                
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        # Clean up database sessions and file
        self.db.close()
        self.engine.dispose()
        app.dependency_overrides.clear()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def _create_excel_file(self, sheets_data: dict) -> bytes:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # Remove default sheet
        
        for sheet_name, rows in sheets_data.items():
            ws = wb.create_sheet(title=sheet_name)
            for row in rows:
                ws.append(row)
                
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()

    def test_duplicate_hash_checks(self):
        # Generate BDC sheet
        data = {
            "ITI Master": [
                ["Pers No", "Complete Name", "Date of Joining", "Aadhaar Card", "Ticket Number", "Mobile", "Email", "Offer Letter ID"],
                ["E101", "Alice Doe", "2024-07-15", "1111-2222-3333", "TKT101", "9876543210", "alice@example.com", "OFF101"]
            ]
        }
        excel_bytes = self._create_excel_file(data)
        
        # 1. Upload first time
        resp = self.client.post(
            "/api/uploads/bdc",
            files={"file": ("master.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"upload_mode": "INCREMENTAL"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["is_duplicate"])
        self.assertEqual(resp.json()["inserted_records"], 1)
        
        # 2. Upload the exact same file content again
        resp = self.client.post(
            "/api/uploads/bdc",
            files={"file": ("master.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"upload_mode": "INCREMENTAL"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["is_duplicate"])
        self.assertEqual(resp.json()["skipped_records"], 1) # no changes, skipped

    def test_rehire_ingestion_sync(self):
        # First Hire
        data1 = {
            "NAPS Master": [
                ["Pers No", "Complete Name", "Date of Joining", "Aadhaar Card", "Ticket Number", "Offer Letter ID"],
                ["N101", "Bob Smith", "2024-07-15", "1111-2222-3333", "TKT101", "OFF201"]
            ]
        }
        excel_bytes1 = self._create_excel_file(data1)
        self.client.post(
            "/api/uploads/bdc",
            files={"file": ("master1.xlsx", excel_bytes1, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        
        # Verify first hire Active
        trainee = self.db.query(Trainee).filter(Trainee.id == "N101").first()
        self.assertIsNotNone(trainee)
        self.assertEqual(trainee.status, "ACTIVE")
        self.assertEqual(trainee.doj, datetime.date(2024, 7, 15))
        
        # Separation Upload
        sep_data = {
            "NAPS Separation": [
                ["Personnel No", "End Date", "Reason"],
                ["N101", "2025-01-15", "Resigned"]
            ]
        }
        excel_bytes_sep = self._create_excel_file(sep_data)
        self.client.post(
            "/api/uploads/separation",
            files={"file": ("sep.xlsx", excel_bytes_sep, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        
        # Verify status is now SEPARATED
        self.db.refresh(trainee)
        self.assertEqual(trainee.status, "SEPARATED")
        self.assertEqual(trainee.dol, datetime.date(2025, 1, 15))
        
        # Rehire Upload
        data2 = {
            "NAPS Master": [
                ["Pers No", "Complete Name", "Date of Joining", "Aadhaar Card", "Ticket Number", "Offer Letter ID"],
                ["N101", "Bob Smith", "2025-06-01", "1111-2222-3333", "TKT101", "OFF202"]
            ]
        }
        excel_bytes2 = self._create_excel_file(data2)
        resp = self.client.post(
            "/api/uploads/bdc",
            files={"file": ("master2.xlsx", excel_bytes2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"upload_mode": "INCREMENTAL"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["rows_rehired"], 1)
        
        # Refresh and verify db state
        self.db.refresh(trainee)
        self.assertEqual(trainee.status, "ACTIVE")
        self.assertEqual(trainee.doj, datetime.date(2025, 6, 1))
        self.assertIsNone(trainee.dol)
        
        # Check that previous lifecycle is archived in TraineeLifecycle table
        lifecycles = self.db.query(TraineeLifecycle).filter(TraineeLifecycle.trainee_id == "N101").all()
        self.assertEqual(len(lifecycles), 1)
        self.assertEqual(lifecycles[0].joining_date, datetime.date(2024, 7, 15))
        self.assertEqual(lifecycles[0].leaving_date, datetime.date(2025, 1, 15))
        self.assertEqual(lifecycles[0].status, "SEPARATED")

    def test_incremental_vs_full_sync_modes(self):
        # 1. Upload Master with 2 employees
        data1 = {
            "ITI Master": [
                ["Pers No", "Complete Name", "Date of Joining", "Aadhaar Card", "Ticket Number", "Offer Letter ID"],
                ["E101", "Alice", "2026-01-01", "1111-2222-3333", "TKT101", "OFF101"],
                ["E102", "Charlie", "2026-01-01", "4444-5555-6666", "TKT102", "OFF102"]
            ]
        }
        excel_bytes1 = self._create_excel_file(data1)
        self.client.post(
            "/api/uploads/bdc",
            files={"file": ("master1.xlsx", excel_bytes1, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        
        # Verify both ACTIVE
        alice = self.db.query(Trainee).filter(Trainee.id == "E101").first()
        charlie = self.db.query(Trainee).filter(Trainee.id == "E102").first()
        self.assertEqual(alice.status, "ACTIVE")
        self.assertEqual(charlie.status, "ACTIVE")
        
        # 2. Upload Master in INCREMENTAL mode containing only Alice
        data2 = {
            "ITI Master": [
                ["Pers No", "Complete Name", "Date of Joining", "Aadhaar Card", "Ticket Number", "Offer Letter ID"],
                ["E101", "Alice", "2026-01-01", "1111-2222-3333", "TKT101", "OFF101"]
            ]
        }
        excel_bytes2 = self._create_excel_file(data2)
        self.client.post(
            "/api/uploads/bdc",
            files={"file": ("master2.xlsx", excel_bytes2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"upload_mode": "INCREMENTAL"}
        )
        
        # Verify Charlie is NOT deactivated
        self.db.refresh(charlie)
        self.assertEqual(charlie.status, "ACTIVE")
        
        # 3. Upload Master in FULL_SYNC mode containing only Alice
        self.client.post(
            "/api/uploads/bdc",
            files={"file": ("master2.xlsx", excel_bytes2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"upload_mode": "FULL_SYNC"}
        )
        
        # Verify Charlie IS deactivated (status INACTIVE)
        self.db.refresh(charlie)
        self.assertEqual(charlie.status, "INACTIVE")
        self.assertEqual(charlie.blocked_reason, "Missing from Latest Master")

    def test_row_error_report_download(self):
        # Seed a trainee and trigger validation errors in validation results
        trainee = Trainee(
            id="T999",
            name="Error Prone",
            doj=datetime.date(2026, 1, 1),
            scheme="NAPS",
            status="ACTIVE",
            current_sheet="NAPS Master"
        )
        self.db.add(trainee)
        self.db.commit()
        
        # Add Validation Results
        res = ValidationResult(
            trainee_id="T999",
            rule_name="TENURE_CHECK",
            status="ERROR",
            message="Invalid separation end date",
            recommended_action="Correct date in Separation sheet"
        )
        self.db.add(res)
        self.db.commit()
        
        # Download validation errors report
        resp = self.client.get("/api/reports/validation-errors")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertIn("attachment", resp.headers["content-disposition"])

if __name__ == "__main__":
    unittest.main()

import unittest
import datetime
import io
import openpyxl
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.core.db import Base
from backend.app.services.workbook_parser import WorkbookParser
from backend.app.services.import_service import ImportService
from backend.app.models.models import Trainee, BDCRecord, SeparationRecord

class TestWorkbookParserEnterprise(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def _create_excel_file(self, sheets_data: dict) -> bytes:
        """
        sheets_data: dict of sheet_name -> list of rows (each row is a list/tuple of cell values).
        """
        wb = openpyxl.Workbook()
        wb.remove(wb.active) # Remove default sheet
        
        for sheet_name, rows in sheets_data.items():
            ws = wb.create_sheet(title=sheet_name)
            for row in rows:
                ws.append(row)
                
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()

    def test_name_fallback_and_synonym_mappings(self):
        """Verify synonym mappings work for different column headers and name fallback constructs fullName."""
        data = {
            "Employee List": [
                # Headers with variations of synonyms and name fallback parts
                ["Pers No", "First Name", "Middle Name", "Last Name", "Begda(ddmmyyyy)(M)", "Aadhaar Card"],
                ["E999", "Maitray", "Kumar", "Agrawal", "25-12-2025", "1234-5678-9012"]
            ]
        }
        excel_bytes = self._create_excel_file(data)
        parsed = WorkbookParser.parse_workbook(excel_bytes, "evolving_test.xlsx")
        
        self.assertEqual(len(parsed["sheets"]), 1)
        sheet = parsed["sheets"][0]
        self.assertEqual(sheet["sheet_type"], "Employee Master")
        
        row = sheet["rows"][0]
        # Check synonym mapped standard keys
        self.assertEqual(row["trainee_id"], "E999")
        self.assertEqual(row["joining_date"], datetime.date(2025, 12, 25))
        self.assertEqual(row["aadhaar"], "123456789012")
        # Check name fallback construction
        self.assertEqual(row["candidate_name"], "Maitray Kumar Agrawal")

    def test_auto_category_detection(self):
        """Verify automatic category/scheme detection works based on sheet name and row content."""
        # 1. Category from sheet name
        data_naps = {
            "NAPS Trainees": [
                ["Pers No", "Complete Name", "DOJ"],
                ["N123", "John Doe", "2026-01-01"]
            ]
        }
        excel_naps = self._create_excel_file(data_naps)
        parsed = WorkbookParser.parse_workbook(excel_naps, "naps.xlsx")
        sheet = parsed["sheets"][0]
        row = sheet["rows"][0]
        
        # Test derive_category_and_scheme helper via ImportService
        cat, scheme = ImportService.derive_category_and_scheme(sheet["sheet_name"], row)
        self.assertEqual(cat, "NAPS")
        self.assertEqual(scheme, "NAPS")

        # 2. Evolving custom category from row header mapping
        data_custom = {
            "Trainees": [
                ["Pers No", "Complete Name", "DOJ", "Program / Scheme Type"],
                ["T123", "Jane Doe", "2026-01-01", "B.Tech Program"]
            ]
        }
        excel_custom = self._create_excel_file(data_custom)
        parsed_custom = WorkbookParser.parse_workbook(excel_custom, "custom.xlsx")
        sheet_custom = parsed_custom["sheets"][0]
        row_custom = sheet_custom["rows"][0]
        
        cat_custom, scheme_custom = ImportService.derive_category_and_scheme(sheet_custom["sheet_name"], row_custom)
        # "B.Tech Program" contains "BTECH", so it resolves to B.TECH / B.Tech
        self.assertEqual(cat_custom, "B.TECH")
        self.assertEqual(scheme_custom, "B.Tech")

    def test_mixed_sheet_auto_routing(self):
        """Verify BDC Ingestion routes Employee Master and Separation sheets in a single workbook upload."""
        # Create a workbook with both Master and Separation sheets
        data = {
            "NAPS BDC": [
                ["Trainee ID", "Trainee Name", "Date of Joining", "Aadhaar Card", "Ticket Number"],
                ["N101", "Alice Miller", "2026-01-01", "1111-2222-3333", "TKT101"]
            ],
            "NAPS Separation": [
                ["Personnel No", "End Date", "Reason"],
                ["N101", "2026-01-15", "Resigned"] # 14 days tenure (< 30) -> should trigger block/early exit!
            ]
        }
        excel_bytes = self._create_excel_file(data)
        
        # Ingest BDC Workbook containing both sheets
        res = ImportService.import_bdc_workbook(self.db, excel_bytes, "mixed_bdc.xlsx")
        
        # Check processing stats
        self.assertIn("NAPS BDC", res["employee_sheets"])
        self.assertIn("NAPS Separation", res["separation_sheets"])
        self.assertEqual(res["inserted_records"], 1) # Inserted Alice Miller
        self.assertEqual(res["employees_updated"], 1) # Separated/Blocked Alice Miller (1 update in database)
        self.assertEqual(res["early_separations"], 1) # Alice Miller is < 30 days tenure (early separation)
        self.assertEqual(res["blocked_employees"], 1) # Alice Miller status becomes BLOCKED
        
        # Verify trainee state in db
        trainee = self.db.query(Trainee).filter(Trainee.id == "N101").first()
        self.assertIsNotNone(trainee)
        self.assertEqual(trainee.status, "BLOCKED")
        self.assertEqual(trainee.blocked_reason, "Early Separation - Resigned before 30 days (tenure: 14 days)")

    def test_offer_id_validation_strictness(self):
        """Verify strict offer_id checks when present, and backwards compatibility warning when absent."""
        # 1. offer_id column exists but missing in row -> stored as "MISSING", imported as incomplete
        data_missing = {
            "Master": [
                ["Trainee ID", "Trainee Name", "Date of Joining", "Offer Letter ID"],
                ["T100", "Bob", "2026-01-01", ""] # offer_id is empty
            ]
        }
        excel_missing = self._create_excel_file(data_missing)
        res_missing = ImportService.import_bdc_workbook(self.db, excel_missing, "missing_offer.xlsx")
        self.assertEqual(res_missing["inserted_records"], 1)
        self.assertEqual(res_missing["failed_records"], 0)
        trainee = self.db.query(Trainee).filter(Trainee.id == "T100").first()
        self.assertIsNotNone(trainee)
        self.assertEqual(trainee.offer_id, "MISSING")

        # 2. offer_id column does not exist -> Sheet warning only, record imports successfully
        data_absent = {
            "Master": [
                ["Trainee ID", "Trainee Name", "Date of Joining"], # no offer_id column
                ["T200", "Charlie", "2026-01-01"]
            ]
        }
        excel_absent = self._create_excel_file(data_absent)
        res_absent = ImportService.import_bdc_workbook(self.db, excel_absent, "absent_offer.xlsx")
        self.assertEqual(res_absent["inserted_records"], 1)
        self.assertEqual(res_absent["failed_records"], 0)
        self.assertEqual(len(res_absent["warnings"]), 1)
        self.assertIn("Missing optional/historical column 'offer_id'", res_absent["warnings"][0])

if __name__ == "__main__":
    unittest.main()

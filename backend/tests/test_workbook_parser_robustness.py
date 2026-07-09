import unittest
import io
import openpyxl
from backend.app.services.workbook_parser import WorkbookParser

class TestWorkbookParserRobustness(unittest.TestCase):
    
    def _create_mock_excel(self, sheets_data: dict) -> bytes:
        """
        sheets_data is a dict of sheet_name -> list of rows (each row is a list of cell values).
        To mock hidden sheets, sheet name starting with 'hidden_' will be set to hidden.
        """
        wb = openpyxl.Workbook()
        # Remove default sheet
        wb.remove(wb.active)
        
        for name, rows in sheets_data.items():
            is_hidden = name.startswith('hidden_')
            sheet_name = name.replace('hidden_', '')
            ws = wb.create_sheet(title=sheet_name)
            
            for row in rows:
                ws.append(row)
                
            if is_hidden:
                ws.sheet_state = 'hidden'
                
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()

    def test_empty_sheet_detection(self):
        """Verify that empty sheets (even with styled/empty rows) are ignored, but non-empty sheets are processed."""
        data = {
            "EmptySheet": [
                [None, "", None],
                ["", None, "  "]
            ],
            "GenericSheet": [
                ["ColA", "ColB"],
                ["Val1", "Val2"]
            ]
        }
        excel_bytes = self._create_mock_excel(data)
        result = WorkbookParser.parse_workbook(excel_bytes, "test.xlsx")
        
        stats = result["stats"]
        self.assertIn("EmptySheet", stats["skipped_sheets"])
        self.assertIn("GenericSheet", stats["sheets_processed"])

    def test_hidden_sheet_ignored(self):
        """Verify that hidden worksheets are ignored."""
        data = {
            "hidden_HiddenSheet": [
                ["ColA", "ColB"],
                ["Val1", "Val2"]
            ],
            "VisibleSheet": [
                ["ColA", "ColB"],
                ["Val1", "Val2"]
            ]
        }
        excel_bytes = self._create_mock_excel(data)
        result = WorkbookParser.parse_workbook(excel_bytes, "test.xlsx")
        
        stats = result["stats"]
        self.assertIn("HiddenSheet", stats["skipped_sheets"])
        self.assertIn("VisibleSheet", stats["sheets_processed"])

    def test_generic_sheet_auto_detection(self):
        """Verify that generic sheets without specific template keywords are correctly auto-detected and parsed."""
        data = {
            "CustomReport": [
                ["Department", "Expense Code", "Amount Claimed"],
                ["Engineering", "EXP001", "₹ 15,000.50"],
                ["HR", "EXP002", "₹ 5,200.00"]
            ]
        }
        excel_bytes = self._create_mock_excel(data)
        result = WorkbookParser.parse_workbook(excel_bytes, "test.xlsx")
        
        self.assertEqual(len(result["sheets"]), 1)
        parsed = result["sheets"][0]
        self.assertEqual(parsed["sheet_type"], "Unknown")
        self.assertEqual(parsed["normalized_headers"], ["department", "expensecode", "amountclaimed"])
        self.assertEqual(len(parsed["rows"]), 2)
        # Verify float conversion works on generic columns containing 'amount'
        self.assertEqual(parsed["rows"][0]["amountclaimed"], 15000.50)
        self.assertEqual(parsed["rows"][1]["amountclaimed"], 5200.00)

    def test_duplicate_and_blank_headers(self):
        """Verify duplicate headers are resolved with suffixes and empty headers get unique default names."""
        data = {
            "Report": [
                ["Aadhaar", "", "Aadhaar", "Date of Joining", "Date of Joining"],
                ["1111", "SomeValue", "2222", "2026-01-01", "2026-02-01"]
            ]
        }
        excel_bytes = self._create_mock_excel(data)
        result = WorkbookParser.parse_workbook(excel_bytes, "test.xlsx")
        
        parsed = result["sheets"][0]
        # Should resolve duplicates
        self.assertEqual(parsed["normalized_headers"], [
            "aadhaar",
            "empty_col_2",
            "aadhaar_2",
            "dateofjoining",
            "dateofjoining_2"
        ])
        # Verify row dict mapping
        row = parsed["rows"][0]
        self.assertEqual(row["aadhaar"], "1111")
        self.assertEqual(row["empty_col_2"], "SomeValue")
        self.assertEqual(row["aadhaar_2"], "2222")

    def test_numeric_normalization_and_formula_errors(self):
        """Verify that currency symbols and commas are stripped from numbers, and formula errors resolve to defaults."""
        self.assertEqual(WorkbookParser.parse_float("₹ 12,345.67"), 12345.67)
        self.assertEqual(WorkbookParser.parse_float("$ -1,200.50"), -1200.50)
        self.assertEqual(WorkbookParser.parse_float("#DIV/0!"), 0.0)
        self.assertEqual(WorkbookParser.parse_float("#VALUE!"), 0.0)
        self.assertEqual(WorkbookParser.parse_float(None), 0.0)

        # Dates
        self.assertIsNone(WorkbookParser.parse_date("#N/A"))
        self.assertIsNone(WorkbookParser.parse_date("#REF!"))

if __name__ == "__main__":
    unittest.main()

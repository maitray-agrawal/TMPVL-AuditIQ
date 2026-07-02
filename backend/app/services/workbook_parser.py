import re
import io
import datetime
import openpyxl
from typing import Dict, List, Tuple, Any, Optional
import pandas as pd

class WorkbookParser:
    # Header keywords for classification
    ID_KWS = ['traineeid', 'empid', 'employeeid', 'regno', 'persno', 'pno', 'personnelno', 'personnelnumber', 'persnumber', 'employeenumber', 'traineenumber', 'id', 'emp_id', 'employee_id']
    NAME_KWS = ['completename', 'completname', 'traineename', 'employeename', 'name', 'firstname', 'fullname']
    DOJ_KWS = ['doj', 'dateofjoining', 'joiningdate', 'begda', 'begdaddmmyyyym', 'joining']
    DOL_KWS = ['dol', 'dateofleaving', 'leavingdate', 'resignationdate', 'separationdate']
    TICKET_KWS = ['ticket', 'ticketno', 'ticketnumber', 'boardingticket', 'ticketid', 'tktno', 'tktnumber']
    
    # Invoice specific headers
    INVOICE_KWS = [
        'joiningpayment', 'joiningreimbursement', 'joiningamount',
        '180days', '180dayspayment', '180daysreimbursement', '180daysamount',
        'uniform', 'shirt', 'jeans', 'excess', 'billingstage', 'stage',
        'claimedamount', 'billedtotal', 'totalamount', 'shirtquantity',
        'shirtqty', 'jeanquanity', 'jeanqty', 'jeansquantity', 'jeansqty'
    ]

    @staticmethod
    def normalize_header(header: str) -> str:
        """Strip, lowercase, remove leading numbers, remove punctuation and spaces."""
        if header is None:
            return ""
        h = str(header).strip().lower()
        # Remove numbering prefix at the start, e.g. "1. Begda", "02. Name", "3_Ticket", "4-Ticket"
        h = re.sub(r'^\d+[\s\.\-_]*', '', h)
        # Remove all punctuation and spaces
        h = re.sub(r'[^a-z0-9]', '', h)
        return h

    @classmethod
    def _find_column_index(cls, headers: List[str], keywords: List[str]) -> Optional[int]:
        """Dynamically match header column indices based on keywords, prioritizing exact matches."""
        normalized_headers = [cls.normalize_header(h) for h in headers]
        normalized_keywords = [cls.normalize_header(kw) for kw in keywords]
        
        # Check exact matches first
        for idx, norm_h in enumerate(normalized_headers):
            if not norm_h:
                continue
            for norm_kw in normalized_keywords:
                if norm_h == norm_kw:
                    return idx
                    
        # Check substring matches next
        for idx, norm_h in enumerate(normalized_headers):
            if not norm_h:
                continue
            for norm_kw in normalized_keywords:
                if norm_kw and (norm_kw in norm_h or norm_h in norm_kw):
                    return idx
        return None

    @staticmethod
    def parse_date(val: Any) -> Optional[datetime.date]:
        """Convert various date formats into datetime.date, with robustness for Indian format variations and formula errors."""
        if pd.isna(val) or val is None:
            return None
        if isinstance(val, (datetime.datetime, datetime.date)):
            if isinstance(val, datetime.datetime):
                return val.date()
            return val
        
        val_str = str(val).strip()
        if not val_str or val_str.lower() in ('nan', 'nat', 'none', 'null') or val_str.startswith('#'):
            return None
            
        try:
            # Handle float/int Excel serial dates (e.g. 45000 or "46198")
            if isinstance(val, (int, float)) or val_str.isdigit() or (val_str.replace('.', '', 1).isdigit() and '.' in val_str):
                num_val = float(val_str)
                if 30000 < num_val < 60000:
                    return pd.to_datetime(num_val, unit='D', origin='1899-12-30').date()
            
            # Try parsing with explicit format-guessing (preferred in Indian context)
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d%m%Y", "%d%m%y"):
                try:
                    return datetime.datetime.strptime(val_str, fmt).date()
                except ValueError:
                    continue
            
            # Fallback to general pandas parser (dayfirst=True to handle DD/MM/YYYY)
            dt = pd.to_datetime(val_str, errors='coerce', dayfirst=True)
            if pd.notna(dt):
                return dt.date()
        except Exception:
            pass
        return None

    @staticmethod
    def clean_trainee_id(val: Any) -> str:
        """Clean trainee IDs to remove trailing .0 from numerical IDs parsed as floats."""
        if pd.isna(val) or val is None:
            return ""
        val_str = str(val).strip()
        if val_str.endswith(".0"):
            val_str = val_str[:-2]
        if val_str.lower() == "nan" or val_str.startswith('#'):
            return ""
        return val_str

    @staticmethod
    def parse_float(val: Any) -> float:
        """Robust helper to parse numeric/float fields, cleaning commas, currency symbols, and formula errors."""
        if val is None or pd.isna(val):
            return 0.0
        val_str = str(val).strip()
        if not val_str or val_str.lower() in ('nan', 'none', 'null') or val_str.startswith('#'):
            return 0.0
        # Clean currency symbols (₹, $), commas, and spaces
        val_str = re.sub(r'[₹\$,\s]', '', val_str)
        try:
            return float(val_str)
        except ValueError:
            return 0.0

    @classmethod
    def detect_sheet_type_and_header(cls, ws) -> Tuple[Optional[str], Optional[int], List[str]]:
        """
        Scans first 15 rows of worksheet to detect if it is BDC, Separation, or Invoice sheet.
        If not matched, detects first row with at least 2 non-numeric, non-empty text cells as a Generic sheet.
        Returns (sheet_type, header_row_index_0_based, original_headers).
        """
        # Read the first 15 rows
        rows_sample = list(ws.iter_rows(max_row=15, values_only=True))
        
        # 1. Try to detect specific types first
        for idx, row in enumerate(rows_sample):
            if not row or all(c is None or str(c).strip() == "" for c in row):
                continue
            
            # Clean cells in row (resolving formula errors to None)
            row_cleaned = [None if (isinstance(c, str) and c.startswith('#')) else c for c in row]
            if all(c is None or str(c).strip() == "" for c in row_cleaned):
                continue

            headers_normalized = [cls.normalize_header(c) for c in row_cleaned if c is not None]
            if not headers_normalized:
                continue

            # Check matches
            has_id = any(cls.normalize_header(c) in cls.ID_KWS for c in row_cleaned if c)
            has_ticket = any(cls.normalize_header(c) in cls.TICKET_KWS for c in row_cleaned if c)
            has_name = any(cls.normalize_header(c) in cls.NAME_KWS for c in row_cleaned if c)
            has_doj = any(cls.normalize_header(c) in cls.DOJ_KWS for c in row_cleaned if c)
            has_dol = any(cls.normalize_header(c) in cls.DOL_KWS for c in row_cleaned if c)
            has_invoice_marker = any(cls.normalize_header(c) in cls.INVOICE_KWS for c in row_cleaned if c)
            
            original_headers = [str(c).strip() if c is not None else "" for c in row]

            # 1. Separation Checks: Trainee ID/Ticket + DOL
            if (has_id or has_ticket) and has_dol:
                return "Separation", idx, original_headers
                
            # 2. BDC Checks: Trainee ID/Ticket + Name + DOJ
            if (has_id or has_ticket) and has_name and has_doj:
                return "BDC", idx, original_headers

            # 3. Invoice Checks: Trainee ID/Ticket + Invoice Marker or Total
            if (has_id or has_ticket) and (has_invoice_marker or 'total' in headers_normalized):
                return "Invoice", idx, original_headers

        # 2. Fall back to Generic detection
        for idx, row in enumerate(rows_sample):
            if not row:
                continue
            text_cells_count = 0
            original_headers = []
            for cell in row:
                val = str(cell).strip() if cell is not None else ""
                original_headers.append(val)
                if val and not val.startswith('#'):
                    # Check if not numeric
                    try:
                        float(val)
                    except ValueError:
                        text_cells_count += 1
            if text_cells_count >= 2:
                return "Generic", idx, original_headers

        return None, None, []

    @classmethod
    def get_merged_cells_map(cls, ws) -> Dict[Tuple[int, int], Any]:
        """
        Builds a map of (row, col) -> top_left_cell_value for all cells in merged ranges.
        Indices are 1-based to align with openpyxl cells.
        """
        merged_map = {}
        if hasattr(ws, "merged_cells") and ws.merged_cells:
            for merged_range in ws.merged_cells.ranges:
                min_col, min_row, max_col, max_row = merged_range.bounds
                # Fetch top-left cell value
                top_left_val = ws.cell(row=min_row, column=min_col).value
                # Normalize formula errors in merged top-left cell
                if isinstance(top_left_val, str) and top_left_val.startswith('#'):
                    top_left_val = None
                
                # Fill the map for all cells in the range
                for r in range(min_row, max_row + 1):
                    for c in range(min_col, max_col + 1):
                        merged_map[(r, c)] = top_left_val
        return merged_map

    @classmethod
    def parse_workbook(cls, file_content: bytes, file_name: str) -> Dict[str, Any]:
        """
        Main parser entry point.
        Loads workbook, detects types (supporting standard BDC/Separation/Invoice and Generic types),
        normalizes values, ignores empty/hidden worksheets, and returns stats + structured data.
        """
        wb = openpyxl.load_workbook(io.BytesIO(file_content), read_only=False, data_only=True)
        
        stats = {
            "workbook_name": file_name,
            "number_of_sheets": len(wb.sheetnames),
            "sheets_processed": [],
            "skipped_sheets": [],
            "failed_sheets": [],
            "warnings": [],
            "errors": []
        }
        
        parsed_sheets = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            
            # 1. Ignore hidden sheets
            if ws.sheet_state != 'visible':
                stats["skipped_sheets"].append(sheet_name)
                stats["warnings"].append(f"Sheet '{sheet_name}' skipped: Sheet is hidden.")
                continue

            # 2. Check if sheet is empty
            is_empty = True
            for row in ws.iter_rows(values_only=True):
                has_valid_data = False
                for cell in row:
                    if cell is not None:
                        val_str = str(cell).strip()
                        # Ignore empty strings, whitespace, and Excel formula errors
                        if val_str and not val_str.startswith('#'):
                            has_valid_data = True
                            break
                if has_valid_data:
                    is_empty = False
                    break

            if is_empty:
                stats["skipped_sheets"].append(sheet_name)
                stats["warnings"].append(f"Sheet '{sheet_name}' skipped: Sheet is empty.")
                continue

            try:
                # 3. Detect sheet type and header row
                sheet_type, header_idx, original_headers = cls.detect_sheet_type_and_header(ws)
                
                if not sheet_type:
                    stats["skipped_sheets"].append(sheet_name)
                    stats["warnings"].append(f"Sheet '{sheet_name}' skipped: Unknown sheet type (could not detect headers).")
                    continue

                stats["sheets_processed"].append(sheet_name)

                # Get merged cells map
                merged_cells_map = cls.get_merged_cells_map(ws)

                # Setup headers mappings, handling blank/empty headers and duplicate headers
                normalized_headers = []
                seen_headers = {}
                for idx, orig_h in enumerate(original_headers):
                    norm_h = cls.normalize_header(orig_h)
                    if not norm_h:
                        norm_h = f"empty_col_{idx + 1}"
                    
                    if norm_h in seen_headers:
                        seen_headers[norm_h] += 1
                        norm_h = f"{norm_h}_{seen_headers[norm_h]}"
                    else:
                        seen_headers[norm_h] = 1
                    
                    normalized_headers.append(norm_h)
                
                rows_data = []
                blank_rows_count = 0
                valid_rows_count = 0

                # 4. Read all data rows after the header row
                start_row = header_idx + 2  # next row after header row
                max_r = ws.max_row

                for r in range(start_row, max_r + 1):
                    row_cells = []
                    # Get values for row, checking merged cells map first
                    for c in range(1, len(original_headers) + 1):
                        if (r, c) in merged_cells_map:
                            val = merged_cells_map[(r, c)]
                        else:
                            val = ws.cell(row=r, column=c).value
                        row_cells.append(val)

                    # Normalize cell values for formula errors
                    row_cleaned = []
                    for val in row_cells:
                        if isinstance(val, str) and val.startswith('#'):
                            row_cleaned.append(None)
                        else:
                            row_cleaned.append(val)

                    # Ignore blank rows
                    if all(val is None or str(val).strip() == "" for val in row_cleaned):
                        blank_rows_count += 1
                        continue

                    # Create normalized row mapping
                    row_dict = {}
                    for idx, norm_h in enumerate(normalized_headers):
                        if not norm_h:
                            continue
                        val = row_cleaned[idx] if idx < len(row_cleaned) else None
                        
                        # Apply specific normalizations based on column types
                        # ID normalization
                        if any(k in norm_h for k in cls.ID_KWS):
                            row_dict[norm_h] = cls.clean_trainee_id(val)
                        # Ticket normalization
                        elif any(k in norm_h for k in cls.TICKET_KWS):
                            row_dict[norm_h] = str(val).strip() if val is not None else ""
                        # Numeric normalization
                        elif any(k in norm_h for k in ['amount', 'payment', 'reimbursement', 'qty', 'quantity', 'total', 'shirt', 'jeans', 'uniform', 'other']):
                            row_dict[norm_h] = cls.parse_float(val)
                        # Date normalization
                        elif any(k in norm_h for k in cls.DOJ_KWS + cls.DOL_KWS + ['date']):
                            row_dict[norm_h] = cls.parse_date(val)
                        # Default string normalization
                        else:
                            row_dict[norm_h] = str(val).strip() if val is not None else ""

                    # Save raw index and clean values
                    row_dict["_row_num"] = r
                    rows_data.append(row_dict)
                    valid_rows_count += 1

                parsed_sheets.append({
                    "sheet_name": sheet_name,
                    "sheet_type": sheet_type,
                    "original_headers": original_headers,
                    "normalized_headers": normalized_headers,
                    "rows": rows_data,
                    "total_rows": max_r,
                    "valid_rows": valid_rows_count,
                    "blank_rows": blank_rows_count
                })

            except Exception as e:
                stats["failed_sheets"].append(sheet_name)
                stats["errors"].append(f"Failed parsing sheet '{sheet_name}': {str(e)}")

        wb.close()
        
        return {
            "stats": stats,
            "sheets": parsed_sheets
        }

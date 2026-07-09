import re
import io
import datetime
import openpyxl
from typing import Dict, List, Tuple, Any, Optional
import pandas as pd

class WorkbookParser:
    PARSER_VERSION = "2.0.0"

    # Synonym dictionary mapping standard business keys to list of lowercase alphanumeric synonyms
    SYNONYMS = {
        "trainee_id": [
            "traineeid", "empid", "employeeid", "regno", "persno", "pno", "personnelno", 
            "personnelnumber", "persnumber", "employeenumber", "traineenumber", "id", 
            "emp_id", "employee_id", "trainee_id", "reg_no", "regno"
        ],
        "ticket_number": [
            "ticket", "ticketno", "ticketnumber", "boardingticket", "ticketid", "tktno", 
            "tktnumber", "boardingticketno", "ticket_number", "ticket_no"
        ],
        "joining_date": [
            "begdaddmmyyyym", "begda", "joiningdate", "doj", "startdate", 
            "dateofjoining", "joining", "joining_date"
        ],
        "end_date": [
            "enddaddmmyyyym", "leavingdate", "enddate", "dol", "dateofleaving", 
            "resignationdate", "separationdate", "seperationdate", "seperatedate", 
            "separatedate", "lastworkingdate", "lwd", "end_date"
        ],
        "candidate_name": [
            "completename", "employeename", "candidatename", "name", 
            "traineename", "fullname", "candidatesname", "employeename"
        ],
        "first_name": ["firstname", "first_name"],
        "middle_name": ["middlename", "middle_name"],
        "last_name": ["lastname", "last_name"],
        "aadhaar": [
            "aadhaar", "adhaar", "aadhar", "uid", "uidai", "nationalid", 
            "adharcard", "aadharcard", "aadhaarcard"
        ],
        "mobile": [
            "mobile", "mobileno", "mobilenumber", "phone", "phoneno", 
            "contact", "contactno", "contactnumber", "telephoneno", "telephonenumber"
        ],
        "email": ["email", "emailid", "emailaddress", "mail", "mailid"],
        "category": [
            "category", "traineecategory", "empcategory", "employeecategory", 
            "scheme", "program", "course", "type", "schemetype"
        ],
        "batch": ["batch", "group", "batchname", "year", "joiningbatch"],
        "shop": [
            "shop", "department", "dept", "location", "workarea", "area", 
            "unit", "plant", "shopfloor"
        ],
        "reason": [
            "reason", "remarks", "typeofseparation", "reasonforaction", 
            "reasonfortermination", "separationreason"
        ],
        "offer_id": [
            "offerid", "offerletterid", "offerletternumber", "offerno", 
            "offernumber", "offer_id"
        ]
    }

    # Invoice specific headers
    INVOICE_KWS = [
        'joiningpayment', 'joiningreimbursement', 'joiningamount',
        '180days', '180dayspayment', '180daysreimbursement', '180daysamount',
        'uniform', 'shirt', 'jeans', 'excess', 'billingstage', 'stage',
        'claimedamount', 'billedtotal', 'totalamount', 'shirtquantity',
        'shirtqty', 'jeanquanity', 'jeanqty', 'jeansquantity', 'jeansqty',
        'amount', 'billamount', 'billingamount', 'pair', 'uniformpair', 'kitpair',
        'distributiondate', 'issueddate', 'pageno', 'page', 'invoicenumber',
        'invoiceno', 'invoice_number', 'invoice_no', 'invoice'
    ]

    @classmethod
    def _has_synonym(cls, row_cleaned: List[Any], synonym_key: str) -> bool:
        """Robust check if any cell in row matches a synonym key, supporting exact and substring matches."""
        headers = [cls.normalize_header(c) for c in row_cleaned if c is not None]
        keywords = [cls.normalize_header(kw) for kw in cls.SYNONYMS.get(synonym_key, [])]
        
        # Check exact matches first
        for h in headers:
            if not h:
                continue
            if h in keywords:
                return True
                
        # Check substring matches next
        for h in headers:
            if not h:
                continue
            for kw in keywords:
                if kw and (kw in h or h in kw):
                    if kw == "name" and any(p in h for p in ("first", "middle", "last")):
                        continue
                    return True
        return False

    @classmethod
    def _has_invoice_marker(cls, row_cleaned: List[Any]) -> bool:
        """Robust check if any cell in row matches invoice keywords, supporting exact and substring matches."""
        headers = [cls.normalize_header(c) for c in row_cleaned if c is not None]
        keywords = [cls.normalize_header(kw) for kw in cls.INVOICE_KWS]
        for h in headers:
            if not h:
                continue
            for kw in keywords:
                if kw and (kw in h or h in kw):
                    return True
        return False

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
                    # Skip matching generic "name" to specific first/middle/last name fields
                    if norm_kw == "name" and any(p in norm_h for p in ("first", "middle", "last")):
                        continue
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
            
            # Clean string format
            val_str = val_str.split(' ')[0]
            
            # Try parsing with explicit format-guessing (preferred in Indian context)
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d%m%Y", "%d%m%y", "%Y%m%d", "%Y/%m/%d"):
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
    def detect_sheet_type_and_header(cls, ws) -> Tuple[str, float, Optional[int], List[str]]:
        """
        Scans first 50 rows of worksheet to detect if it is Employee Master, Separation, Invoice, or Unknown.
        Scores each row to find the highest confidence header row.
        Returns (sheet_type, confidence, header_row_index_0_based, original_headers).
        """
        # Read the first 50 rows
        rows_sample = list(ws.iter_rows(max_row=50, values_only=True))
        
        best_idx = None
        best_score = -1.0
        best_sheet_type = "Unknown"
        best_confidence = 0.22
        best_headers = []
        best_reason = "No known schema matches."
        
        for idx, row in enumerate(rows_sample):
            if not row or all(c is None or str(c).strip() == "" for c in row):
                continue
            
            # Clean cells in row (resolving formula errors to None)
            row_cleaned = [None if (isinstance(c, str) and c.startswith('#')) else c for c in row]
            non_empty_cells = [c for c in row_cleaned if c is not None and str(c).strip() != ""]
            if len(non_empty_cells) < 2:
                continue
                
            # Count synonym matches using the robust helpers
            has_id = cls._has_synonym(row_cleaned, "trainee_id")
            has_ticket = cls._has_synonym(row_cleaned, "ticket_number")
            has_joining = cls._has_synonym(row_cleaned, "joining_date")
            has_end_date = cls._has_synonym(row_cleaned, "end_date")
            has_name = cls._has_synonym(row_cleaned, "candidate_name") or cls._has_synonym(row_cleaned, "first_name")
            has_reason = cls._has_synonym(row_cleaned, "reason")
            has_batch = cls._has_synonym(row_cleaned, "batch")
            has_category = cls._has_synonym(row_cleaned, "category")
            has_invoice_marker = cls._has_invoice_marker(row_cleaned)
            has_total = any(cls.normalize_header(c) == "total" for c in row_cleaned if c)
            
            # Text cells count (non-numeric)
            text_cells = 0
            for cell in row_cleaned:
                val = str(cell).strip() if cell is not None else ""
                if val:
                    try:
                        float(val)
                    except ValueError:
                        text_cells += 1
                        
            # Determine scores based on weights
            em_score = 0.0
            sep_score = 0.0
            inv_score = 0.0
            
            # Employee Master score details
            em_reasons = []
            if has_id or has_ticket:
                em_score += 10.0
                em_reasons.append("Ticket Number" if has_ticket else "Trainee ID")
            if has_joining:
                em_score += 10.0
                em_reasons.append("Joining Date")
            if has_name:
                em_score += 8.0
                em_reasons.append("Candidate Name" if has_name else "Name")
            if has_batch:
                em_score += 4.0
                em_reasons.append("Batch")
            if has_category:
                em_score += 4.0
                em_reasons.append("Category")
                
            # Separation score details
            sep_reasons = []
            if has_id or has_ticket:
                sep_score += 10.0
                sep_reasons.append("Ticket Number" if has_ticket else "Trainee ID")
            if has_end_date:
                sep_score += 10.0
                sep_reasons.append("Separation Date")
            if has_reason:
                sep_score += 8.0
                sep_reasons.append("Separation Reason")
                
            # Invoice score details
            inv_reasons = []
            if has_id or has_ticket:
                inv_score += 10.0
                inv_reasons.append("Trainee/Ticket ID")
            if has_invoice_marker:
                inv_score += 25.0
                inv_reasons.append("Invoice fields")
            if has_total:
                inv_score += 4.0
                inv_reasons.append("Total fields")
                
            # Hard constraints:
            # 0. A valid sheet must contain Trainee ID or Ticket Number to be classified as Employee Master, Separation, or Invoice.
            if not (has_id or has_ticket):
                em_score = 0.0
                sep_score = 0.0
                inv_score = 0.0
                em_reasons = []
                sep_reasons = []
                inv_reasons = []

            # 0.1 Employee Master sheets must contain Joining Date.
            if not has_joining:
                em_score = 0.0
                em_reasons = []

            # 1. Separation sheets should only be classified when Date of Leaving / DOL / Separation Date columns exist.
            if not has_end_date:
                sep_score = 0.0
                sep_reasons = []
                
            # 2. Invoice sheets should only be classified when Pair, Amount, Distribution Date, Invoice Number, Uniform or similar invoice fields exist.
            if not (has_invoice_marker or has_total):
                inv_score = 0.0
                inv_reasons = []
                
            # 3. Employee Master score must always override Separation when both partially match (meaning both scores > 0).
            # We enforce this if joining_date column is present, which clearly marks it as master ingestion.
            # If both partially match, and has_joining is present, EM overrides.
            if em_score > 0 and sep_score > 0 and has_joining:
                # Override: Employee Master wins
                em_score += 50.0 # Large boost to ensure Employee Master wins
            
            # Determine classification for this row
            row_type = "Unknown"
            row_conf = 0.22
            row_score = 0.0
            reason_str = "No known schema matches."
            
            if em_score > 0 or sep_score > 0 or inv_score > 0:
                if em_score >= sep_score and em_score >= inv_score:
                    row_type = "Employee Master"
                    row_conf = 0.98 if has_joining else 0.85
                    row_score = em_score
                    reason_str = f"Found " + " + ".join(em_reasons) + f" (EM score: {em_score:.1f} vs Sep: {sep_score:.1f})"
                elif sep_score >= em_score and sep_score >= inv_score:
                    row_type = "Separation"
                    row_conf = 0.99
                    row_score = sep_score
                    reason_str = f"Found " + " + ".join(sep_reasons) + f" (Sep score: {sep_score:.1f} vs EM: {em_score:.1f})"
                else:
                    row_type = "Invoice"
                    row_conf = 0.95
                    row_score = inv_score
                    reason_str = f"Found " + " + ".join(inv_reasons) + f" (Invoice score: {inv_score:.1f})"
            else:
                row_score = text_cells * 0.5
                
            # We want to find the header row that maximizes the classification score or general text score
            final_row_score = max(em_score, sep_score, inv_score) if (em_score > 0 or sep_score > 0 or inv_score > 0) else row_score
            
            if final_row_score > best_score:
                best_score = final_row_score
                best_idx = idx
                best_sheet_type = row_type
                best_confidence = row_conf
                best_headers = [str(c).strip() if c is not None else "" for c in row]
                best_reason = reason_str
                
        # Log the classification reason
        import logging
        logger = logging.getLogger("workbook_parser")
        sheet_name_str = ws.title
        logger.info(f"Sheet Classification: Workbook Sheet '{sheet_name_str}' -> Classification: '{best_sheet_type}', Reason: {best_reason}")
        print(f"Sheet Classification: Workbook Sheet '{sheet_name_str}' -> Classification: '{best_sheet_type}', Reason: {best_reason}")
        
        # Attach the classification reason to the class so import_service can fetch it for detailed logs
        if not hasattr(cls, "_CLASSIFICATION_REASONS"):
            cls._CLASSIFICATION_REASONS = {}
        cls._CLASSIFICATION_REASONS[sheet_name_str] = {
            "type": best_sheet_type,
            "score_summary": best_reason,
            "headers": best_headers
        }

        if best_idx is not None and best_score > 0.0:
            return best_sheet_type, best_confidence, best_idx, best_headers
            
        # Fall back to detecting a header row (first row with at least 2 non-numeric text cells)
        for idx, row in enumerate(rows_sample):
            if not row:
                continue
            text_cells_count = 0
            original_headers = []
            for cell in row:
                val = str(cell).strip() if cell is not None else ""
                original_headers.append(val)
                if val and not val.startswith('#'):
                    try:
                        float(val)
                    except ValueError:
                        text_cells_count += 1
            if text_cells_count >= 2:
                # Fallback logging
                logger.info(f"Sheet Classification Fallback: Workbook Sheet '{ws.title}' -> Classification: 'Unknown', Reason: No matching synonym schema, matched on text cells.")
                print(f"Sheet Classification Fallback: Workbook Sheet '{ws.title}' -> Classification: 'Unknown', Reason: No matching synonym schema, matched on text cells.")
                return "Unknown", 0.22, idx, original_headers
                
        logger.info(f"Sheet Classification Fallback: Workbook Sheet '{ws.title}' -> Classification: 'Unknown', Reason: No headers found.")
        return "Unknown", 0.22, None, []


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
        Loads workbook, detects types (supporting standard BDC/Separation/Invoice and Unknown types),
        normalizes values, ignores empty/hidden worksheets, and returns stats + structured data.
        Optimized for memory usage with read_only mode for files > 10MB.
        """
        # Determine if we should load read-only (files larger than 10MB)
        is_large_file = len(file_content) > 10 * 1024 * 1024
        wb = openpyxl.load_workbook(io.BytesIO(file_content), read_only=is_large_file, data_only=True)
        
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
                sheet_type, confidence, header_idx, original_headers = cls.detect_sheet_type_and_header(ws)
                
                stats["sheets_processed"].append(sheet_name)

                # Get merged cells map if not in read_only mode
                merged_cells_map = {} if is_large_file else cls.get_merged_cells_map(ws)

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
                
                # Schema Fingerprinting & Caching column mappings
                import hashlib
                fingerprint = hashlib.sha256(",".join(normalized_headers).encode('utf-8')).hexdigest()
                
                if not hasattr(cls, "_SCHEMA_CACHE"):
                    cls._SCHEMA_CACHE = {}
                col_mapping = cls._SCHEMA_CACHE.get(fingerprint)
                if col_mapping is None:
                    col_mapping = {}
                    for std_key, syn_list in cls.SYNONYMS.items():
                        col_mapping[std_key] = cls._find_column_index(original_headers, syn_list)
                    cls._SCHEMA_CACHE[fingerprint] = col_mapping

                rows_data = []
                blank_rows_count = 0
                valid_rows_count = 0

                # 4. Read all data rows after the header row
                start_row = header_idx + 2  # next row after header row (1-indexed)
                
                # In read_only mode, we can't write, but we can read using ws.iter_rows
                for r_idx, row in enumerate(ws.iter_rows(min_row=start_row, values_only=False), start=start_row):
                    row_cells = []
                    for c_idx, cell in enumerate(row, start=1):
                        val = None
                        if not is_large_file and (r_idx, c_idx) in merged_cells_map:
                            val = merged_cells_map[(r_idx, c_idx)]
                        else:
                            val = cell.value
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

                    # Create row dict
                    row_dict = {}
                    
                    # 1. Put original normalized headers (backward compatibility)
                    for idx, norm_h in enumerate(normalized_headers):
                        if not norm_h:
                            continue
                        val = row_cleaned[idx] if idx < len(row_cleaned) else None
                        
                        # Apply original normalizations
                        if any(k in norm_h for k in cls.SYNONYMS["trainee_id"] + cls.SYNONYMS["ticket_number"]):
                            row_dict[norm_h] = cls.clean_trainee_id(val)
                        elif any(k in norm_h for k in ['amount', 'payment', 'reimbursement', 'qty', 'quantity', 'total', 'shirt', 'jeans', 'uniform', 'other']):
                            row_dict[norm_h] = cls.parse_float(val)
                        elif any(k in norm_h for k in cls.SYNONYMS["joining_date"] + cls.SYNONYMS["end_date"] + ['date']):
                            row_dict[norm_h] = cls.parse_date(val)
                        else:
                            row_dict[norm_h] = str(val).strip() if val is not None else ""

                    # 2. Put standard business keys dynamically based on synonyms using the cached col_mapping
                    for std_key, col_idx in col_mapping.items():
                        if col_idx is not None:
                            matched_val = row_cleaned[col_idx] if col_idx < len(row_cleaned) else None
                            if std_key in ("joining_date", "end_date"):
                                row_dict[std_key] = cls.parse_date(matched_val)
                            elif std_key in ("trainee_id", "ticket_number", "offer_id"):
                                row_dict[std_key] = cls.clean_trainee_id(matched_val)
                            elif std_key in ("aadhaar", "mobile"):
                                val_str = str(matched_val).strip() if matched_val is not None else ""
                                val_str = re.sub(r'[\s\-]', '', val_str)
                                if val_str.endswith(".0"):
                                    val_str = val_str[:-2]
                                row_dict[std_key] = val_str
                            else:
                                row_dict[std_key] = str(matched_val).strip() if matched_val is not None else ""
                        else:
                            if std_key in ("joining_date", "end_date"):
                                row_dict[std_key] = None
                            else:
                                row_dict[std_key] = ""

                    # 3. Complete Name Fallback
                    if not row_dict.get("candidate_name"):
                        first = row_dict.get("first_name", "")
                        middle = row_dict.get("middle_name", "")
                        last = row_dict.get("last_name", "")
                        full_name = " ".join([part for part in [first, middle, last] if part]).strip()
                        if full_name:
                            row_dict["candidate_name"] = full_name
                            # Write back to normalized headers if applicable
                            for name_h in ['completename', 'traineename', 'name', 'employeename']:
                                if name_h in normalized_headers:
                                    row_dict[name_h] = full_name

                    # Raw row index
                    row_dict["_row_num"] = r_idx
                    rows_data.append(row_dict)
                    valid_rows_count += 1

                parsed_sheets.append({
                    "sheet_name": sheet_name,
                    "sheet_type": sheet_type,
                    "confidence": confidence,
                    "original_headers": original_headers,
                    "normalized_headers": normalized_headers,
                    "rows": rows_data,
                    "total_rows": start_row + len(rows_data) + blank_rows_count - 1,
                    "valid_rows": valid_rows_count,
                    "blank_rows": blank_rows_count
                })

            except Exception as e:
                stats["failed_sheets"].append(sheet_name)
                stats["errors"].append(f"Failed parsing sheet '{sheet_name}': {str(e)}")

        wb.close()
        
        return {
            "stats": stats,
            "sheets": parsed_sheets,
            "parser_version": cls.PARSER_VERSION
        }

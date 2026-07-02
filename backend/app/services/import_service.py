import re
import datetime
from typing import Dict, List, Tuple, Any, Optional
from sqlalchemy.orm import Session
from backend.app.repositories.repositories import TraineeRepository, InvoiceRepository, AuditLogRepository
from backend.app.models.models import Trainee, InvoiceRecord, SeparationRecord, BDCRecord, PaymentLedger, ValidationResult
from backend.app.services.workbook_parser import WorkbookParser

class ImportService:
    @staticmethod
    def get_column_value(row: Dict[str, Any], keywords: List[str]) -> Any:
        """Helper to extract normalized value from parsed row using list of alias keywords."""
        for kw in keywords:
            norm_kw = WorkbookParser.normalize_header(kw)
            if norm_kw in row:
                return row[norm_kw]
        return None

    @staticmethod
    def normalize_header(header: str) -> str:
        return WorkbookParser.normalize_header(header)

    @classmethod
    def _serialize_trainee_state(cls, trainee: Optional[Trainee]) -> Dict[str, Any]:
        if not trainee:
            return {}
        return {
            "id": trainee.id,
            "name": trainee.name,
            "doj": trainee.doj.strftime("%Y-%m-%d") if trainee.doj else None,
            "dol": trainee.dol.strftime("%Y-%m-%d") if trainee.dol else None,
            "scheme": trainee.scheme,
            "status": trainee.status,
            "blocked_reason": trainee.blocked_reason,
            "aadhaar": trainee.aadhaar,
            "ticket_number": trainee.ticket_number,
            "category": trainee.category,
            "batch": trainee.batch,
            "shop": trainee.shop,
        }

    @classmethod
    def _parse_sheet_month(cls, sheet_name: str) -> str:
        """Parse a month name or range from sheet name (e.g. 'April 26' -> 'April 2026')"""
        name = sheet_name.strip()
        month_pattern = re.compile(
            r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b[- ]?(\d{2,4})',
            re.IGNORECASE
        )
        matches = list(month_pattern.finditer(name))
        if not matches:
            return name
            
        months_map_full = {
            "jan": "January", "feb": "February", "mar": "March", "apr": "April",
            "may": "May", "jun": "June", "jul": "July", "aug": "August",
            "sep": "September", "oct": "October", "nov": "November", "dec": "December"
        }
        
        def format_match(m):
            mon_raw = m.group(1).lower()[:3]
            mon = months_map_full.get(mon_raw, m.group(1).capitalize())
            yr = m.group(2)
            if len(yr) == 2:
                yr = "20" + yr
            return f"{mon} {yr}"
            
        if len(matches) == 1:
            return format_match(matches[0])
        elif len(matches) >= 2:
            return f"{format_match(matches[0])} to {format_match(matches[-1])}"
        return name

    @classmethod
    def import_bdc_workbook(cls, db: Session, file_content: bytes, file_name: str) -> Dict[str, Any]:
        """Processes the BDC Master Workbook using Universal WorkbookParser."""
        import time
        start_time = time.time()
        
        # Parse workbook automatically
        parsed_wb = WorkbookParser.parse_workbook(file_content, file_name)
        wb_stats = parsed_wb["stats"]
        
        success_count = 0
        skipped_count = 0
        created_count = 0
        updated_count = 0
        skip_count = 0
        error_count = 0
        duplicate_count = 0
        blocked_count = 0
        separated_count = 0
        errors = list(wb_stats["errors"])
        warnings = list(wb_stats["warnings"])
        
        id_kws = ['traineeid', 'empid', 'employeeid', 'regno', 'persno', 'pno', 'personnelno', 'personnelnumber', 'persnumber', 'employeenumber', 'traineenumber', 'id', 'emp_id', 'employee_id']
        name_kws = ['completename', 'completname', 'traineename', 'employeename', 'name', 'firstname', 'fullname']
        doj_kws = ['doj', 'dateofjoining', 'joiningdate', 'begda', 'begdaddmmyyyym', 'joining']
        scheme_kws = ['category', 'traineecategory', 'empcategory', 'employeecategory', 'scheme', 'program', 'course', 'type']
        aadhaar_kws = ['aadhaar', 'adhaar', 'aadhar', 'uid', 'uidai', 'nationalid', 'adharcard', 'aadharcard', 'aadhaarcard']
        ticket_kws = ['ticket', 'ticketno', 'ticketnumber', 'boardingticket', 'ticketid', 'tktno', 'tktnumber']
        batch_kws = ['batch', 'group', 'batchname', 'year', 'joiningbatch']
        shop_kws = ['shop', 'department', 'dept', 'location', 'workarea', 'area', 'unit', 'plant', 'shopfloor']
        
        sheets_processed = []
        skipped_sheets = list(wb_stats["skipped_sheets"])
        failed_sheets = list(wb_stats["failed_sheets"])
        
        BATCH_SIZE = 2000
        
        for sheet in parsed_wb["sheets"]:
            sheet_name = sheet["sheet_name"]
            
            # Process only BDC sheets
            if sheet["sheet_type"] != "BDC":
                skipped_sheets.append(sheet_name)
                warnings.append(f"Sheet '{sheet_name}' skipped: Detected type is '{sheet["sheet_type"]}', expected BDC.")
                continue
                
            sheets_processed.append(sheet_name)
            
            # Setup category based on sheet name
            sheet_upper = sheet_name.strip().upper()
            if "B.TECH" in sheet_upper or "BTECH" in sheet_upper:
                sheet_category = "B.TECH"
            elif "M.TECH" in sheet_upper or "MTECH" in sheet_upper:
                sheet_category = "M.TECH"
            elif "NAPS" in sheet_upper:
                sheet_category = "NAPS"
            else:
                sheet_category = sheet_upper
            
            seen_trainee_ids = set()
            seen_aadhaars = set()
            seen_tickets = set()
            
            batch_rows = []
            sheet_inserted = 0
            sheet_updated = 0
            sheet_failed = 0
            sheet_start_time = time.time()
            sheet_before_state = {}
            sheet_after_state = {}
            
            def process_batch(rows_to_process, current_sheet):
                nonlocal success_count, skipped_count, created_count, updated_count, skip_count, error_count, duplicate_count, blocked_count, separated_count
                nonlocal sheet_inserted, sheet_updated, sheet_failed
                nonlocal sheet_before_state, sheet_after_state
                
                valid_rows = []
                batch_trainee_ids = set()
                batch_aadhaars = set()
                batch_tickets = set()
                
                for row in rows_to_process:
                    row_num = row["_row_num"]
                    try:
                        r_id = cls.get_column_value(row, id_kws) or ""
                        r_name = str(cls.get_column_value(row, name_kws) or "").strip()
                        r_doj = cls.get_column_value(row, doj_kws)
                        
                        r_category = str(cls.get_column_value(row, scheme_kws) or "").strip().upper() or sheet_category
                        if "B.TECH" in r_category or "BTECH" in r_category:
                            r_category = "B.TECH"
                        elif "M.TECH" in r_category or "MTECH" in r_category:
                            r_category = "M.TECH"
                        elif "NAPS" in r_category:
                            r_category = "NAPS"
                            
                        r_aadhaar = str(cls.get_column_value(row, aadhaar_kws) or "").strip()
                        r_aadhaar = r_aadhaar.replace(" ", "").replace("-", "") if r_aadhaar else ""
                        
                        r_ticket = str(cls.get_column_value(row, ticket_kws) or "").strip()
                        r_batch = str(cls.get_column_value(row, batch_kws) or "").strip()
                        r_shop = str(cls.get_column_value(row, shop_kws) or "").strip()
                        
                        if not r_name or r_name.lower() == 'nan' or not r_doj:
                            skipped_count += 1
                            error_count += 1
                            sheet_failed += 1
                            errors.append(f"Sheet '{current_sheet}', Row {row_num}: Missing Name or Date of Joining.")
                            continue
                            
                        if not r_id and not r_ticket:
                            skipped_count += 1
                            error_count += 1
                            sheet_failed += 1
                            errors.append(f"Sheet '{current_sheet}', Row {row_num}: Missing both Trainee ID and Ticket Number.")
                            continue
                            
                        if r_id:
                            if r_id in seen_trainee_ids:
                                skipped_count += 1
                                duplicate_count += 1
                                error_count += 1
                                sheet_failed += 1
                                errors.append(f"Sheet '{current_sheet}', Row {row_num}: Duplicate Trainee ID '{r_id}' within the sheet.")
                                continue
                            seen_trainee_ids.add(r_id)
                            
                        if r_aadhaar:
                            if r_aadhaar in seen_aadhaars:
                                skipped_count += 1
                                duplicate_count += 1
                                error_count += 1
                                sheet_failed += 1
                                errors.append(f"Sheet '{current_sheet}', Row {row_num}: Duplicate Aadhaar '{r_aadhaar}' within the sheet.")
                                continue
                            seen_aadhaars.add(r_aadhaar)
                            batch_aadhaars.add(r_aadhaar)
                            
                        if r_ticket:
                            if r_ticket in seen_tickets:
                                skipped_count += 1
                                duplicate_count += 1
                                error_count += 1
                                sheet_failed += 1
                                errors.append(f"Sheet '{current_sheet}', Row {row_num}: Duplicate Ticket '{r_ticket}' within the sheet.")
                                continue
                            seen_tickets.add(r_ticket)
                            batch_tickets.add(r_ticket)
                            
                        if r_id:
                            batch_trainee_ids.add(r_id)
                            
                        valid_rows.append({
                            "row_num": row_num,
                            "id": r_id,
                            "name": r_name,
                            "doj": r_doj,
                            "category": r_category,
                            "aadhaar": r_aadhaar,
                            "ticket": r_ticket,
                            "batch": r_batch,
                            "shop": r_shop
                        })
                    except Exception as e:
                        skipped_count += 1
                        error_count += 1
                        sheet_failed += 1
                        errors.append(f"Sheet '{current_sheet}', Row {row_num}: Error parsing columns: {str(e)}")
                        
                if not valid_rows:
                    return
                    
                existing_by_id = {}
                if batch_trainee_ids:
                    res_ids = db.query(Trainee).filter(Trainee.id.in_(batch_trainee_ids)).all()
                    existing_by_id = {t.id: t for t in res_ids}
                existing_by_ticket = {}
                if batch_tickets:
                    res_tickets = db.query(Trainee).filter(Trainee.ticket_number.in_(batch_tickets)).all()
                    existing_by_ticket = {t.ticket_number: t for t in res_tickets}
                existing_by_aadhaar = {}
                if batch_aadhaars:
                    res_aadhaars = db.query(Trainee).filter(Trainee.aadhaar.in_(batch_aadhaars)).all()
                    existing_by_aadhaar = {t.aadhaar: t for t in res_aadhaars}
                    
                for item in valid_rows:
                    row_num = item["row_num"]
                    try:
                        r_id = item["id"]
                        r_name = item["name"]
                        r_doj = item["doj"]
                        r_category = item["category"]
                        r_aadhaar = item["aadhaar"]
                        r_ticket = item["ticket"]
                        r_batch = item["batch"]
                        r_shop = item["shop"]
                        
                        if r_ticket and r_ticket in existing_by_ticket:
                            ticket_owner = existing_by_ticket[r_ticket]
                            if r_id and ticket_owner.id != r_id:
                                skipped_count += 1
                                error_count += 1
                                sheet_failed += 1
                                errors.append(f"Sheet '{current_sheet}', Row {row_num}: Ticket '{r_ticket}' already exists for another trainee '{ticket_owner.id}' in database.")
                                continue
                                
                        if r_aadhaar and r_aadhaar in existing_by_aadhaar:
                            aadhaar_owner = existing_by_aadhaar[r_aadhaar]
                            if r_id and aadhaar_owner.id != r_id:
                                skipped_count += 1
                                error_count += 1
                                sheet_failed += 1
                                errors.append(f"Sheet '{current_sheet}', Row {row_num}: Aadhaar '{r_aadhaar}' already exists for another trainee '{aadhaar_owner.id}' in database.")
                                continue
                                
                        trainee = None
                        if r_ticket and r_ticket in existing_by_ticket:
                            trainee = existing_by_ticket[r_ticket]
                        if not trainee and r_id and r_id in existing_by_id:
                            trainee = existing_by_id[r_id]
                        if not trainee and r_aadhaar and r_aadhaar in existing_by_aadhaar:
                            trainee = existing_by_aadhaar[r_aadhaar]
                            
                        resolved_id = trainee.id if trainee else (r_id if r_id else r_ticket)
                        
                        if trainee:
                            if trainee.id not in sheet_before_state:
                                sheet_before_state[trainee.id] = cls._serialize_trainee_state(trainee)
                            is_rehire = False
                            if trainee.status in ("SEPARATED", "BLOCKED"):
                                if trainee.dol and r_doj > trainee.dol and r_doj != trainee.doj:
                                    is_rehire = True
                                    
                            if is_rehire:
                                if not trainee.extra_data:
                                    trainee.extra_data = {}
                                lifecycles = trainee.extra_data.get("lifecycles", [])
                                lifecycle_num = len(lifecycles) + 1
                                
                                # Query and serialize history for the previous lifecycle (where date >= trainee.doj)
                                prev_doj = trainee.doj
                                prev_invoices = []
                                prev_ledger = []
                                prev_validations = []
                                reason = "Separated"
                                
                                if prev_doj:
                                    # 1. Invoice Records
                                    invs = db.query(InvoiceRecord).filter(
                                        InvoiceRecord.trainee_id == trainee.id,
                                        InvoiceRecord.invoice_date >= prev_doj
                                    ).all()
                                    prev_invoices = [
                                        {
                                            "invoice_number": inv.invoice_number,
                                            "invoice_date": inv.invoice_date.strftime("%Y-%m-%d") if inv.invoice_date else None,
                                            "billed_joining_amount": inv.billed_joining_amount,
                                            "billed_180_days_amount": inv.billed_180_days_amount,
                                            "billed_other_amount": inv.billed_other_amount,
                                            "billed_total_amount": inv.billed_total_amount,
                                            "approved_joining_amount": inv.approved_joining_amount,
                                            "approved_180_days_amount": inv.approved_180_days_amount,
                                            "approved_total_amount": inv.approved_total_amount,
                                            "status": inv.status,
                                            "file_name": inv.file_name
                                        }
                                        for inv in invs
                                    ]
                                    
                                    # 2. Payment Ledger Entries
                                    leds = db.query(PaymentLedger).filter(
                                        PaymentLedger.trainee_id == trainee.id,
                                        PaymentLedger.payment_date >= prev_doj
                                    ).all()
                                    prev_ledger = [
                                        {
                                            "invoice_number": led.invoice_number,
                                            "payment_type": led.payment_type,
                                            "amount_paid": led.amount_paid,
                                            "payment_date": led.payment_date.strftime("%Y-%m-%d") if led.payment_date else None
                                        }
                                        for led in leds
                                    ]
                                    
                                    # 3. Validation Results
                                    vals = db.query(ValidationResult).filter(
                                        ValidationResult.trainee_id == trainee.id,
                                        ValidationResult.created_at >= datetime.datetime(prev_doj.year, prev_doj.month, prev_doj.day)
                                    ).all()
                                    prev_validations = [
                                        {
                                            "rule_name": val.rule_name,
                                            "status": val.status,
                                            "message": val.message,
                                            "reason_code": val.reason_code,
                                            "recommended_action": val.recommended_action
                                        }
                                        for val in vals
                                    ]
                                    
                                    if trainee.status == "BLOCKED":
                                        reason = trainee.blocked_reason or "Blocked"
                                    elif trainee.status == "SEPARATED":
                                        latest_sep = db.query(SeparationRecord).filter(
                                            SeparationRecord.trainee_id == trainee.id
                                        ).order_by(SeparationRecord.dol.desc()).first()
                                        if latest_sep:
                                            reason = latest_sep.reason or "Separated"
                                
                                lifecycles.append({
                                    "lifecycle_number": lifecycle_num,
                                    "doj": trainee.doj.strftime("%Y-%m-%d") if trainee.doj else None,
                                    "dol": trainee.dol.strftime("%Y-%m-%d") if trainee.dol else None,
                                    "status": trainee.status,
                                    "blocked_reason": trainee.blocked_reason,
                                    "reason": reason,
                                    "category": trainee.category,
                                    "batch": trainee.batch,
                                    "shop": trainee.shop,
                                    "bdc_workbook": trainee.current_workbook,
                                    "bdc_sheet": trainee.current_sheet,
                                    "invoice_history": prev_invoices,
                                    "payment_ledger": prev_ledger,
                                    "validation_history": prev_validations
                                })
                                trainee.extra_data = {
                                    **(trainee.extra_data or {}),
                                    "lifecycles": lifecycles,
                                    "current_lifecycle": {
                                        "lifecycle_number": lifecycle_num + 1,
                                        "previous_doj": trainee.doj.strftime("%Y-%m-%d") if trainee.doj else None,
                                        "previous_dol": trainee.dol.strftime("%Y-%m-%d") if trainee.dol else None,
                                        "current_doj": r_doj.strftime("%Y-%m-%d"),
                                        "current_dol": None
                                    }
                                }
                                
                                trainee.name = r_name
                                trainee.category = r_category
                                trainee.scheme = "B.Tech" if r_category == "B.TECH" else ("M.Tech" if r_category == "M.TECH" else "NAPS")
                                trainee.batch = r_batch
                                trainee.shop = r_shop
                                trainee.doj = r_doj
                                trainee.dol = None
                                trainee.status = "ACTIVE"
                                trainee.blocked_reason = None
                                if r_aadhaar:
                                    trainee.aadhaar = r_aadhaar
                                if r_ticket:
                                    trainee.ticket_number = r_ticket
                                    
                                trainee.current_workbook = file_name
                                trainee.current_sheet = current_sheet
                                
                                sheet_updated += 1
                                updated_count += 1
                                sheet_after_state[trainee.id] = cls._serialize_trainee_state(trainee)
                            else:
                                changed = False
                                if trainee.name != r_name:
                                    trainee.name = r_name
                                    changed = True
                                    
                                if trainee.status not in ("SEPARATED", "BLOCKED"):
                                    if trainee.doj != r_doj:
                                        trainee.doj = r_doj
                                        changed = True
                                        
                                if (trainee.category or "") != (r_category or ""):
                                    trainee.category = r_category
                                    changed = True
                                    
                                legacy_scheme = "B.Tech" if r_category == "B.TECH" else ("M.Tech" if r_category == "M.TECH" else "NAPS")
                                if (trainee.scheme or "") != legacy_scheme:
                                    trainee.scheme = legacy_scheme
                                    changed = True
                                    
                                if (trainee.batch or "") != (r_batch or ""):
                                    trainee.batch = r_batch or None
                                    changed = True
                                    
                                if (trainee.shop or "") != (r_shop or ""):
                                    trainee.shop = r_shop or None
                                    changed = True
                                    
                                if r_aadhaar and (trainee.aadhaar or "") != r_aadhaar:
                                    trainee.aadhaar = r_aadhaar
                                    changed = True
                                    
                                if r_ticket and (trainee.ticket_number or "") != r_ticket:
                                    trainee.ticket_number = r_ticket
                                    changed = True
                                    
                                if trainee.current_workbook != file_name or trainee.current_sheet != current_sheet:
                                    trainee.current_workbook = file_name
                                    trainee.current_sheet = current_sheet
                                    
                                if changed:
                                    if trainee.status not in ("SEPARATED", "BLOCKED"):
                                        trainee.status = "ACTIVE"
                                    sheet_updated += 1
                                    updated_count += 1
                                    sheet_after_state[trainee.id] = cls._serialize_trainee_state(trainee)
                                else:
                                    if trainee.status == "BLOCKED":
                                        blocked_count += 1
                                    elif trainee.status == "SEPARATED":
                                        separated_count += 1
                                    skip_count += 1
                        else:
                            new_trainee = Trainee(
                                id=resolved_id,
                                name=r_name,
                                doj=r_doj,
                                scheme="B.Tech" if r_category == "B.TECH" else ("M.Tech" if r_category == "M.TECH" else "NAPS"),
                                category=r_category,
                                batch=r_batch or None,
                                shop=r_shop or None,
                                aadhaar=r_aadhaar or None,
                                ticket_number=r_ticket or None,
                                status="ACTIVE",
                                current_workbook=file_name,
                                current_sheet=current_sheet
                            )
                            db.add(new_trainee)
                            existing_by_id[resolved_id] = new_trainee
                            if r_ticket:
                                existing_by_ticket[r_ticket] = new_trainee
                            if r_aadhaar:
                                existing_by_aadhaar[r_aadhaar] = new_trainee
                            sheet_inserted += 1
                            created_count += 1
                            sheet_after_state[resolved_id] = cls._serialize_trainee_state(new_trainee)
                            
                        bdc_rec = BDCRecord(
                            trainee_id=resolved_id,
                            doj=r_doj,
                            scheme="B.Tech" if r_category == "B.TECH" else ("M.Tech" if r_category == "M.TECH" else "NAPS"),
                            file_name=file_name,
                            extra_data={
                                "sheet_name": current_sheet,
                                "category": r_category,
                                "aadhaar": r_aadhaar,
                                "ticket_number": r_ticket,
                                "batch": r_batch,
                                "shop": r_shop
                            }
                        )
                        db.add(bdc_rec)
                        success_count += 1
                    except Exception as e:
                        skipped_count += 1
                        error_count += 1
                        sheet_failed += 1
                        errors.append(f"Sheet '{current_sheet}', Row {row_num}: Database operation failed: {str(e)}")
                        
                db.commit()
            
            try:
                # Iterate rows in sheet using batching
                for i in range(0, len(sheet["rows"]), BATCH_SIZE):
                    process_batch(sheet["rows"][i:i+BATCH_SIZE], sheet_name)
                    
                sheet_duration = time.time() - sheet_start_time
                AuditLogRepository.add_log(
                    db=db,
                    action="IMPORT_BDC_SHEET",
                    module="BDC_UPLOAD",
                    details=f"Workbook: {file_name} | Sheet: {sheet_name} | Import Time: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} | Rows Read: {sheet['valid_rows'] + sheet['blank_rows']} | Rows Imported: {sheet_inserted} | Rows Updated: {sheet_updated} | Rows Failed: {sheet_failed} | Operator: Admin | Duration: {sheet_duration:.2f}s",
                    operator="Admin",
                    workbook=file_name,
                    sheet=sheet_name,
                    rows_count=sheet['valid_rows'] + sheet['blank_rows'],
                    duration=sheet_duration,
                    inserted=sheet_inserted,
                    updated=sheet_updated,
                    failed=sheet_failed,
                    warnings=len(warnings),
                    errors=sheet_failed,
                    before_state={"trainees": sheet_before_state} if sheet_before_state else None,
                    after_state={"trainees": sheet_after_state} if sheet_after_state else None
                )

                
            except Exception as e:
                failed_sheets.append(sheet_name)
                error_count += 1
                errors.append(f"Failed to process sheet '{sheet_name}': {str(e)}")
                db.rollback()
                
        if not sheets_processed:
            raise ValueError("No sheets with required columns found.")
            


        total_duration = time.time() - start_time
        AuditLogRepository.add_log(
            db=db,
            action="IMPORT_BDC_WORKBOOK",
            module="BDC_UPLOAD",
            details=f"File: {file_name}. Sheets processed: {', '.join(sheets_processed)}. Imported: {created_count}, Updated: {updated_count}, Errors: {error_count}. Duration: {total_duration:.2f}s",
            operator="Admin",
            workbook=file_name,
            sheet=", ".join(sheets_processed),
            rows_count=created_count + updated_count + skip_count + error_count,
            duration=total_duration,
            inserted=created_count,
            updated=updated_count,
            failed=error_count,
            warnings=len(warnings),
            errors=error_count
        )
        return {
            "workbook_name": file_name,
            "number_of_sheets": len(parsed_wb["sheets"]) + len(skipped_sheets),
            "processed_sheets": sheets_processed,
            "skipped_sheets": skipped_sheets,
            "failed_sheets": failed_sheets,
            "inserted_records": created_count,
            "updated_records": updated_count,
            "skipped_records": skip_count,
            "failed_records": error_count,
            "warnings": warnings,
            "errors": errors,
            
            # Spec compliance keys
            "sheets_processed": sheets_processed,
            "employees_updated": updated_count,
            "early_separations": 0,
            "blocked_employees": blocked_count,
            "inserted": created_count,
            "updated": updated_count,
            "blocked": blocked_count,
            "separated": separated_count,
            "duplicates": duplicate_count,
            "unknown_employees": 0,
            
            # original keys
            "success_count": success_count,
            "skipped_count": skipped_count,
            "errors": errors,
            "total_records": success_count + skipped_count,
            "created_count": created_count,
            "updated_count": updated_count,
            "insert_count": created_count,
            "update_count": updated_count,
            "skip_count": skip_count,
            "error_count": error_count,
            
            # Additional UI friendly stats keys
            "Workbook Name": file_name,
            "Processed Sheets": ", ".join(sheets_processed),
            "Skipped Sheets": ", ".join(skipped_sheets),
            "Inserted": created_count,
            "Updated": updated_count,
            "Skipped": skip_count,
            "Failed": error_count
        }

    @classmethod
    def import_separation_workbook(cls, db: Session, file_content: bytes, file_name: str) -> Dict[str, Any]:
        """Processes the Separation Workbook (NAPS, B.Tech, M.Tech) using Universal WorkbookParser."""
        import time
        start_time = time.time()
        
        parsed_wb = WorkbookParser.parse_workbook(file_content, file_name)
        wb_stats = parsed_wb["stats"]
        
        success_count = 0
        skipped_count = 0
        separated_count = 0
        already_synced_count = 0
        error_count = 0
        early_exits_count = 0
        blocked_count = 0
        duplicate_count = 0
        unknown_employees_count = 0
        errors = list(wb_stats["errors"])
        warnings = list(wb_stats["warnings"])
        
        id_kws = ['traineeid', 'empid', 'employeeid', 'regno', 'persno', 'pno', 'personnelno', 'personnelnumber', 'persnumber', 'employeenumber', 'traineenumber', 'id', 'emp_id', 'employee_id']
        dol_kws = ['dol', 'dateofleaving', 'leavingdate', 'resignationdate', 'separationdate', 'separationdate']
        reason_kws = ['reason', 'remarks', 'typeofseparation', 'reasonforaction', 'reasonfortermination', 'separationreason']
        
        sheets_processed = []
        skipped_sheets = list(wb_stats["skipped_sheets"])
        failed_sheets = list(wb_stats["failed_sheets"])
        
        BATCH_SIZE = 2000
        
        for sheet in parsed_wb["sheets"]:
            sheet_name = sheet["sheet_name"]
            
            if sheet["sheet_type"] != "Separation":
                skipped_sheets.append(sheet_name)
                warnings.append(f"Sheet '{sheet_name}' skipped: Detected type is '{sheet["sheet_type"]}', expected Separation.")
                continue
                
            sheets_processed.append(sheet_name)
            
            # Parse month from sheet name
            sheet_month = cls._parse_sheet_month(sheet_name)
            
            sheet_separated = 0
            sheet_blocked = 0
            sheet_failed = 0
            sheet_start_time = time.time()
            sheet_before_state = {}
            sheet_after_state = {}
            
            def process_batch(rows_to_process, current_sheet):
                nonlocal success_count, skipped_count, separated_count, already_synced_count, error_count, early_exits_count, blocked_count, duplicate_count, unknown_employees_count
                nonlocal sheet_separated, sheet_blocked, sheet_failed
                nonlocal sheet_before_state, sheet_after_state
                
                valid_rows = []
                batch_trainee_ids = set()
                seen_row_trainees = set()
                
                for row in rows_to_process:
                    row_num = row["_row_num"]
                    try:
                        trainee_id = cls.get_column_value(row, id_kws) or ""
                        dol = cls.get_column_value(row, dol_kws)
                        reason = str(cls.get_column_value(row, reason_kws) or "").strip() or "Separated"
                        
                        if not trainee_id or not dol:
                            skipped_count += 1
                            error_count += 1
                            sheet_failed += 1
                            errors.append(f"Sheet '{current_sheet}', Row {row_num}: Missing Trainee ID or Date of Leaving.")
                            continue
                            
                        if (trainee_id, dol) in seen_row_trainees:
                            skipped_count += 1
                            duplicate_count += 1
                            error_count += 1
                            sheet_failed += 1
                            errors.append(f"Sheet '{current_sheet}', Row {row_num}: Duplicate separation entry for '{trainee_id}' on {dol} within the sheet.")
                            continue
                        seen_row_trainees.add((trainee_id, dol))
                        
                        batch_trainee_ids.add(trainee_id)
                        valid_rows.append({
                            "row_num": row_num,
                            "id": trainee_id,
                            "dol": dol,
                            "reason": reason
                        })
                    except Exception as e:
                        skipped_count += 1
                        error_count += 1
                        sheet_failed += 1
                        errors.append(f"Sheet '{current_sheet}', Row {row_num}: Error parsing columns: {str(e)}")
                        
                if not valid_rows:
                    return
                    
                existing_trainees = {
                    t.id: t for t in db.query(Trainee).filter(Trainee.id.in_(batch_trainee_ids)).all()
                }
                
                for item in valid_rows:
                    row_num = item["row_num"]
                    try:
                        trainee_id = item["id"]
                        dol = item["dol"]
                        reason = item["reason"]
                        
                        if trainee_id in existing_trainees:
                            trainee = existing_trainees[trainee_id]
                            if trainee.id not in sheet_before_state:
                                sheet_before_state[trainee.id] = cls._serialize_trainee_state(trainee)
                            
                            if not trainee.doj:
                                raise ValueError(f"Trainee '{trainee_id}' in Database does not have a Date of Joining. Cannot calculate tenure.")
                            
                            days_worked = (dol - trainee.doj).days
                            if days_worked < 0:
                                raise ValueError(f"Date of Leaving ({dol}) is before Date of Joining ({trainee.doj}).")
                                
                            status_before = trainee.status
                            status_after = "SEPARATED"
                            blocked_reason = None
                            
                            # Rule 8: Separation Rules
                            if days_worked < 30:
                                status_after = "BLOCKED"
                                blocked_reason = f"Early Separation - Resigned before 30 days (tenure: {days_worked} days)"
                                reason = "Early Separation"
                                early_exits_count += 1
                                sheet_blocked += 1
                                blocked_count += 1
                            else:
                                sheet_separated += 1
                                separated_count += 1
                                
                            existing_rec = db.query(SeparationRecord).filter(
                                SeparationRecord.trainee_id == trainee.id,
                                SeparationRecord.dol == dol
                            ).first()
                            
                            if not existing_rec:
                                sep_rec = SeparationRecord(
                                    trainee_id=trainee.id,
                                    dol=dol,
                                    reason=reason,
                                    file_name=file_name,
                                    extra_data={
                                        "sheet": current_sheet,
                                        "sheet_name": current_sheet,
                                        "month": sheet_month,
                                        "status_before": status_before,
                                        "status_after": status_after,
                                        "tenure": days_worked,
                                        "early_exit": days_worked < 30,
                                        "days_worked": days_worked,
                                        "scheme": trainee.scheme
                                    }
                                )
                                db.add(sep_rec)
                            else:
                                already_synced_count += 1
                                
                            trainee.dol = dol
                            trainee.status = status_after
                            trainee.blocked_reason = blocked_reason
                            sheet_after_state[trainee.id] = cls._serialize_trainee_state(trainee)
                            
                            success_count += 1
                        else:
                            skipped_count += 1
                            unknown_employees_count += 1
                            error_count += 1
                            sheet_failed += 1
                            errors.append(f"Sheet '{current_sheet}', Row {row_num}: Trainee ID '{trainee_id}' not found in Employee Master. Please import BDC Master first.")
                    except Exception as e:
                        skipped_count += 1
                        error_count += 1
                        sheet_failed += 1
                        errors.append(f"Sheet '{current_sheet}', Row {row_num}: Database operation failed: {str(e)}")
                        
                db.commit()

            try:
                for i in range(0, len(sheet["rows"]), BATCH_SIZE):
                    process_batch(sheet["rows"][i:i+BATCH_SIZE], sheet_name)
                    
                sheet_duration = time.time() - sheet_start_time
                AuditLogRepository.add_log(
                    db=db,
                    action="IMPORT_SEPARATION_SHEET",
                    module="SEPARATION_UPLOAD",
                    details=f"Workbook: {file_name} | Sheet: {sheet_name} | Import Time: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} | Rows Read: {sheet['valid_rows'] + sheet['blank_rows']} | Rows Imported: {sheet_separated + sheet_blocked} | Rows Updated: {sheet_separated + sheet_blocked} | Rows Failed: {sheet_failed} | Operator: Admin | Duration: {sheet_duration:.2f}s",
                    operator="Admin",
                    workbook=file_name,
                    sheet=sheet_name,
                    rows_count=sheet['valid_rows'] + sheet['blank_rows'],
                    duration=sheet_duration,
                    inserted=0,
                    updated=sheet_separated + sheet_blocked,
                    failed=sheet_failed,
                    warnings=len(warnings),
                    errors=sheet_failed,
                    before_state={"trainees": sheet_before_state} if sheet_before_state else None,
                    after_state={"trainees": sheet_after_state} if sheet_after_state else None
                )
                
            except Exception as e:
                failed_sheets.append(sheet_name)
                error_count += 1
                errors.append(f"Failed to process sheet '{sheet_name}': {str(e)}")
                db.rollback()
                
        if not sheets_processed:
            raise ValueError("No sheets with required columns found.")
            
        total_duration = time.time() - start_time
        AuditLogRepository.add_log(
            db=db,
            action="IMPORT_SEPARATION_WORKBOOK",
            module="SEPARATION_UPLOAD",
            details=f"File: {file_name}. Sheets processed: {', '.join(sheets_processed)}. Imported: {separated_count + blocked_count}, Errors: {error_count}. Duration: {total_duration:.2f}s",
            operator="Admin",
            workbook=file_name,
            sheet=", ".join(sheets_processed),
            rows_count=separated_count + blocked_count + already_synced_count + skipped_count + error_count,
            duration=total_duration,
            inserted=0,
            updated=separated_count + blocked_count,
            failed=error_count,
            warnings=len(warnings),
            errors=error_count
        )
        
        return {
            "workbook_name": file_name,
            "number_of_sheets": len(parsed_wb["sheets"]) + len(skipped_sheets),
            "processed_sheets": sheets_processed,
            "skipped_sheets": skipped_sheets,
            "failed_sheets": failed_sheets,
            "inserted_records": separated_count + blocked_count,
            "updated_records": already_synced_count,
            "skipped_records": skipped_count - error_count,
            "failed_records": error_count,
            "warnings": warnings,
            "errors": errors,
            
            # Spec compliance keys
            "sheets_processed": sheets_processed,
            "employees_updated": separated_count + blocked_count,
            "early_separations": early_exits_count,
            "blocked_employees": blocked_count,
            "inserted": 0,
            "updated": separated_count + blocked_count,
            "blocked": blocked_count,
            "separated": separated_count,
            "duplicates": duplicate_count,
            "unknown_employees": unknown_employees_count,
            
            # original keys
            "success_count": success_count,
            "skipped_count": skipped_count,
            "errors": errors,
            "total_records": success_count + skipped_count,
            "separated_count": separated_count,
            "already_synced_count": already_synced_count
        }

    @classmethod
    def import_invoice_workbook(
        cls, 
        db: Session, 
        file_content: bytes, 
        file_name: str,
        invoice_number_override: Optional[str] = None,
        invoice_date_override: Optional[datetime.date] = None
    ) -> Dict[str, Any]:
        """Processes a Monthly Invoice Workbook using Universal WorkbookParser."""
        import time
        start_time = time.time()
        parsed_wb = WorkbookParser.parse_workbook(file_content, file_name)
        wb_stats = parsed_wb["stats"]
        
        # Determine invoice number and date before processing sheets
        detected_inv_num = None
        detected_inv_date = None
        
        if invoice_number_override:
            detected_inv_num = invoice_number_override.strip()
        if invoice_date_override:
            detected_inv_date = invoice_date_override
            
        id_kws = ['trainee id', 'emp id', 'employee id', 'trainee_id', 'reg no', 'ticket no', 'ticket_no', 'ticket number', 'pers no', 'pers_no', 'p no', 'p_no', 'personnel no', 'personnel_no', 'ticket', 'ticketno', 'ticketnumber', 'persno', 'personnelnumber', 'id', 'emp_id', 'employee_id']
        ticket_kws = ['ticket', 'ticket no', 'ticket_no', 'ticket number', 'boarding ticket', 'ticket id']
        name_kws = ['name', 'trainee name', 'employee name', 'billed name', 'employee_name']
        
        # If they aren't overridden, find them from the first invoice sheet first row
        if not detected_inv_num or not detected_inv_date:
            for sheet in parsed_wb["sheets"]:
                if sheet["sheet_type"] == "Invoice" and sheet["rows"]:
                    first_row = sheet["rows"][0]
                    if not detected_inv_num:
                        detected_inv_num = cls.get_column_value(first_row, ['invoice number', 'invoice_no', 'invoice no', 'bill no'])
                    if not detected_inv_date:
                        raw_date = cls.get_column_value(first_row, ['invoice date', 'date', 'bill date'])
                        if raw_date:
                            detected_inv_date = WorkbookParser.parse_date(raw_date)
                    if detected_inv_num and detected_inv_date:
                        break
                        
        # Fallbacks if still not detected
        if not detected_inv_num:
            detected_inv_num = file_name.split('.')[0]
        if not detected_inv_date:
            detected_inv_date = datetime.date.today()
            
        # Capture existing invoices before deletion for before_state
        existing_invoices = db.query(InvoiceRecord).filter(InvoiceRecord.invoice_number == detected_inv_num).all()
        invoice_before_state = {
            "invoice_records": [
                {
                    "invoice_number": inv.invoice_number,
                    "invoice_date": inv.invoice_date.strftime("%Y-%m-%d") if inv.invoice_date else None,
                    "trainee_id": inv.trainee_id,
                    "billed_name": inv.billed_name,
                    "billed_joining_amount": inv.billed_joining_amount,
                    "billed_180_days_amount": inv.billed_180_days_amount,
                    "billed_other_amount": inv.billed_other_amount,
                    "billed_total_amount": inv.billed_total_amount,
                    "approved_joining_amount": inv.approved_joining_amount,
                    "approved_180_days_amount": inv.approved_180_days_amount,
                    "approved_total_amount": inv.approved_total_amount,
                    "status": inv.status,
                    "file_name": inv.file_name,
                }
                for inv in existing_invoices
            ]
        }
        invoice_after_state = []

        # Delete existing invoice records exactly once!
        InvoiceRepository.delete_by_invoice_number(db, detected_inv_num)
        
        success_count = 0
        skipped_count = 0
        error_count = 0
        errors = list(wb_stats["errors"])
        warnings = list(wb_stats["warnings"])
        
        sheets_processed = []
        skipped_sheets = list(wb_stats["skipped_sheets"])
        failed_sheets = list(wb_stats["failed_sheets"])
        
        BATCH_SIZE = 2000
        
        for sheet in parsed_wb["sheets"]:
            sheet_name = sheet["sheet_name"]
            
            if sheet["sheet_type"] != "Invoice":
                skipped_sheets.append(sheet_name)
                warnings.append(f"Sheet '{sheet_name}' skipped: Detected type is '{sheet["sheet_type"]}', expected Invoice.")
                continue
                
            sheets_processed.append(sheet_name)
            
            def process_batch(rows_to_process, current_sheet):
                nonlocal success_count, skipped_count, error_count, invoice_after_state
                
                batch_trainee_ids = set()
                batch_tickets = set()
                valid_rows = []
                
                for row in rows_to_process:
                    row_num = row["_row_num"]
                    trainee_id = cls.get_column_value(row, id_kws) or ""
                    r_ticket = cls.get_column_value(row, ticket_kws) or ""
                    
                    if not trainee_id and not r_ticket:
                        skipped_count += 1
                        error_count += 1
                        errors.append(f"Sheet '{current_sheet}', Row {row_num}: Missing both Trainee ID and Ticket Number.")
                        continue
                        
                    if trainee_id:
                        batch_trainee_ids.add(trainee_id)
                    if r_ticket:
                        batch_tickets.add(r_ticket)
                        
                    valid_rows.append((row_num, trainee_id, r_ticket, row))
                    
                if not valid_rows:
                    return
                    
                db_trainees_by_id = {}
                if batch_trainee_ids:
                    res_id = db.query(Trainee).filter(Trainee.id.in_(batch_trainee_ids)).all()
                    db_trainees_by_id = {t.id: t for t in res_id}
                    
                db_trainees_by_ticket = {}
                if batch_tickets:
                    res_ticket = db.query(Trainee).filter(Trainee.ticket_number.in_(batch_tickets)).all()
                    db_trainees_by_ticket = {t.ticket_number: t for t in res_ticket}
                    
                for row_num, trainee_id, r_ticket, row in valid_rows:
                    try:
                        trainee = None
                        if trainee_id and trainee_id in db_trainees_by_id:
                            trainee = db_trainees_by_id[trainee_id]
                        elif r_ticket and r_ticket in db_trainees_by_ticket:
                            trainee = db_trainees_by_ticket[r_ticket]
                            
                        exists_in_master = trainee is not None
                        resolved_trainee_id = trainee.id if exists_in_master else None
                        trainee_name = trainee.name if exists_in_master else None
                        
                        billed_name = str(cls.get_column_value(row, name_kws) or "").strip()
                        
                        joining_amt = 0.0
                        days180_amt = 0.0
                        other_amt = 0.0
                        
                        stage_idx_val = cls.get_column_value(row, ['billing stage', 'stage', 'billing_stage'])
                        if stage_idx_val:
                            stage_val = str(stage_idx_val).strip().lower()
                            claimed_amt = cls.get_column_value(row, ['claimed amount', 'amount', 'claimed_amount', 'total', 'billed total', 'total_amount']) or 0.0
                            if "join" in stage_val:
                                joining_amt = claimed_amt
                            elif "six" in stage_val or "180" in stage_val or "month" in stage_val:
                                days180_amt = claimed_amt
                            else:
                                joining_amt = claimed_amt
                        else:
                            joining_amt = cls.get_column_value(row, ['joining', 'joining payment', 'joining reimbursement', 'joining_amount']) or 0.0
                            days180_amt = cls.get_column_value(row, ['180 days', '180 days payment', '180 days reimbursement', '180_days_amount']) or 0.0
                            other_amt = cls.get_column_value(row, ['other', 'uniform', 'shirt', 'jeans', 'excess']) or 0.0
                            
                        total_amt = cls.get_column_value(row, ['total', 'billed total', 'amount', 'total_amount']) or (joining_amt + days180_amt + other_amt)
                        if cls.get_column_value(row, ['claimed amount', 'claimed_amount']) is not None and stage_idx_val is not None:
                            total_amt = cls.get_column_value(row, ['claimed amount', 'claimed_amount']) or (joining_amt + days180_amt)
                            
                        shirt_qty = cls.get_column_value(row, ['shirt quantity', 'shirt qty', 'shirt_quantity', 'shirt_qty', 'shirt']) or 0.0
                        jean_qty = cls.get_column_value(row, ['jean quantity', 'jean qty', 'jean_quantity', 'jean_qty', 'jeans quantity', 'jeans qty', 'jeans']) or 0.0
                        
                        # Maintain raw row dict mapping for backward compatibility
                        raw_row_data = {k: str(v) if v is not None else "" for k, v in row.items() if not k.startswith('_')}
                        raw_row_data["shirt_quantity"] = shirt_qty
                        raw_row_data["jean_quantity"] = jean_qty
                        raw_row_data["sheet_name"] = current_sheet
                        if r_ticket:
                            raw_row_data["ticket_number"] = r_ticket
                            
                        invoice_rec = InvoiceRecord(
                            invoice_number=detected_inv_num,
                            invoice_date=detected_inv_date,
                            trainee_id=resolved_trainee_id,
                            billed_name=billed_name or (trainee_name if exists_in_master else f"Unknown ({trainee_id or r_ticket})"),
                            billed_joining_amount=joining_amt,
                            billed_180_days_amount=days180_amt,
                            billed_other_amount=other_amt,
                            billed_total_amount=total_amt,
                            approved_joining_amount=0.0,
                            approved_180_days_amount=0.0,
                            approved_total_amount=0.0,
                            status="PENDING",
                            file_name=file_name,
                            extra_data=raw_row_data
                        )
                        
                        InvoiceRepository.create_record(db, invoice_rec, commit=False)
                        invoice_after_state.append({
                            "invoice_number": invoice_rec.invoice_number,
                            "invoice_date": invoice_rec.invoice_date.strftime("%Y-%m-%d") if invoice_rec.invoice_date else None,
                            "trainee_id": invoice_rec.trainee_id,
                            "billed_name": invoice_rec.billed_name,
                            "billed_joining_amount": invoice_rec.billed_joining_amount,
                            "billed_180_days_amount": invoice_rec.billed_180_days_amount,
                            "billed_other_amount": invoice_rec.billed_other_amount,
                            "billed_total_amount": invoice_rec.billed_total_amount,
                            "approved_joining_amount": invoice_rec.approved_joining_amount,
                            "approved_180_days_amount": invoice_rec.approved_180_days_amount,
                            "approved_total_amount": invoice_rec.approved_total_amount,
                            "status": invoice_rec.status,
                            "file_name": invoice_rec.file_name,
                        })
                        success_count += 1
                    except Exception as e:
                        skipped_count += 1
                        error_count += 1
                        errors.append(f"Sheet '{current_sheet}', Row {row_num}: {str(e)}")
                        
                db.commit()

            try:
                for i in range(0, len(sheet["rows"]), BATCH_SIZE):
                    process_batch(sheet["rows"][i:i+BATCH_SIZE], sheet_name)
            except Exception as e:
                failed_sheets.append(sheet_name)
                error_count += 1
                errors.append(f"Failed to process sheet '{sheet_name}': {str(e)}")
                db.rollback()
                
        if not sheets_processed:
            raise ValueError("No sheets with required columns found.")
            
        total_duration = time.time() - start_time
        AuditLogRepository.add_log(
            db=db,
            action="IMPORT_INVOICE",
            module="INVOICE_UPLOAD",
            details=f"Invoice: {detected_inv_num}. Billed: {success_count}, Skipped: {skipped_count}. Duration: {total_duration:.2f}s",
            operator="Admin",
            workbook=file_name,
            sheet=", ".join(sheets_processed),
            rows_count=success_count + skipped_count,
            duration=total_duration,
            inserted=success_count,
            updated=0,
            failed=error_count,
            warnings=len(warnings),
            errors=error_count,
            before_state=invoice_before_state if invoice_before_state["invoice_records"] else None,
            after_state={"invoice_records": invoice_after_state} if invoice_after_state else None,
            invoice_number=detected_inv_num
        )
        
        return {
            "workbook_name": file_name,
            "number_of_sheets": len(parsed_wb["sheets"]) + len(skipped_sheets),
            "processed_sheets": sheets_processed,
            "skipped_sheets": skipped_sheets,
            "failed_sheets": failed_sheets,
            "inserted_records": success_count,
            "updated_records": 0,
            "skipped_records": skipped_count - error_count,
            "failed_records": error_count,
            "warnings": warnings,
            "errors": errors,
            
            # original keys
            "invoice_number": detected_inv_num,
            "invoice_date": detected_inv_date,
            "success_count": success_count,
            "skipped_count": skipped_count,
            "errors": errors,
            "total_records": success_count + skipped_count,
            "records_imported": success_count
        }

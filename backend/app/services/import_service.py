import re
import os
import datetime
from typing import Dict, List, Tuple, Any, Optional
from sqlalchemy.orm import Session
from backend.app.repositories.repositories import TraineeRepository, InvoiceRepository, AuditLogRepository
from backend.app.models.models import Trainee, InvoiceRecord, SeparationRecord, BDCRecord, PaymentLedger, ValidationResult, UploadHistory, TraineeLifecycle, Invoice, InvoiceItem
from backend.app.services.workbook_parser import WorkbookParser
from backend.app.core.json_util import make_json_serializable

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
    def derive_category_and_scheme(cls, sheet_name: str, row_dict: Dict[str, Any]) -> Tuple[str, str]:
        # Try to find category from row dictionary using synonyms
        raw_cat = cls.get_column_value(row_dict, WorkbookParser.SYNONYMS["category"])
        if raw_cat:
            cat = str(raw_cat).strip().upper()
        else:
            # Fallback to sheet name
            cat = sheet_name.strip().upper()
        
        # Strip trailing/leading separation markers from sheet name category if present
        # e.g. "NAPS SEPARATION" -> category "NAPS"
        cat = re.sub(r'[\-_]?SEPARATION\b', '', cat).strip()
        
        # Normalize category name
        if "B.TECH" in cat or "BTECH" in cat:
            normalized_cat = "B.TECH"
            scheme = "B.Tech"
        elif "M.TECH" in cat or "MTECH" in cat:
            normalized_cat = "M.TECH"
            scheme = "M.Tech"
        elif "NAPS" in cat:
            normalized_cat = "NAPS"
            scheme = "NAPS"
        else:
            normalized_cat = cat
            if cat in ("ITI", "NAPS"):
                scheme = cat
            else:
                scheme = cat.title()
                
        return normalized_cat, scheme

    @classmethod
    def _process_employee_master_sheet(cls, db: Session, sheet: Dict[str, Any], file_name: str, BATCH_SIZE: int, state: Dict[str, Any]) -> None:
        import time
        sheet_name = sheet["sheet_name"]
        sheet_inserted = 0
        sheet_updated = 0
        sheet_failed = 0
        sheet_start_time = time.time()
        sheet_before_state = {}
        sheet_after_state = {}

        # 1. Automatic category and scheme detection
        first_row = sheet["rows"][0] if sheet["rows"] else {}
        sheet_category, sheet_scheme = cls.derive_category_and_scheme(sheet_name, first_row)

        # Check if offer_id column is present in sheet headers (original or normalized)
        has_offer_id_col = False
        for orig_h in sheet["original_headers"]:
            norm_h = WorkbookParser.normalize_header(orig_h)
            if norm_h in WorkbookParser.SYNONYMS["offer_id"]:
                has_offer_id_col = True
                break
        
        if not has_offer_id_col:
            state["warnings"].append(f"Sheet '{sheet_name}': Missing optional/historical column 'offer_id'.")

        seen_trainee_ids = set()
        seen_aadhaars = set()
        seen_tickets = set()

        def process_batch(rows_to_process):
            nonlocal sheet_inserted, sheet_updated, sheet_failed
            valid_rows = []
            batch_trainee_ids = set()
            batch_aadhaars = set()
            batch_tickets = set()

            for row in rows_to_process:
                row_num = row["_row_num"]
                state["rows_processed"] += 1
                try:
                    # Get standard key values
                    r_id = row.get("trainee_id") or ""
                    r_ticket = row.get("ticket_number") or ""
                    r_name = row.get("candidate_name") or ""
                    r_doj = row.get("joining_date")
                    r_offer_id = row.get("offer_id") or ""
                    r_aadhaar = row.get("aadhaar") or ""
                    r_mobile = row.get("mobile") or ""
                    r_email = row.get("email") or ""
                    
                    r_category, r_scheme = cls.derive_category_and_scheme(sheet_name, row)
                    
                    # Clean fields
                    r_name = str(r_name).strip()
                    r_aadhaar = r_aadhaar.replace(" ", "").replace("-", "") if r_aadhaar else ""
                    r_ticket = str(r_ticket).strip()
                    r_batch = str(row.get("batch") or "").strip()
                    r_shop = str(row.get("shop") or "").strip()

                    # Validate required fields
                    if not r_name or r_name.lower() == 'nan' or not r_doj:
                        state["skipped_count"] += 1
                        state["error_count"] += 1
                        sheet_failed += 1
                        state["errors"].append(f"Sheet '{sheet_name}', Row {row_num}: Missing Name or Date of Joining.")
                        continue
                        
                    if not r_id and not r_ticket:
                        state["skipped_count"] += 1
                        state["error_count"] += 1
                        sheet_failed += 1
                        state["errors"].append(f"Sheet '{sheet_name}', Row {row_num}: Missing both Trainee ID and Ticket Number.")
                        continue

                    # If offer_id column is present, enforce it strictly per row
                    if has_offer_id_col and not r_offer_id:
                        state["skipped_count"] += 1
                        state["error_count"] += 1
                        sheet_failed += 1
                        state["errors"].append(f"Sheet '{sheet_name}', Row {row_num}: Missing required field: offer_id.")
                        continue

                    # Duplicates within the sheet validation
                    if r_id:
                        if r_id in seen_trainee_ids:
                            state["skipped_count"] += 1
                            state["duplicate_count"] += 1
                            state["error_count"] += 1
                            sheet_failed += 1
                            state["errors"].append(f"Sheet '{sheet_name}', Row {row_num}: Duplicate Trainee ID '{r_id}' within the sheet.")
                            continue
                        seen_trainee_ids.add(r_id)
                        batch_trainee_ids.add(r_id)
                        
                    if r_aadhaar:
                        if r_aadhaar in seen_aadhaars:
                            state["skipped_count"] += 1
                            state["duplicate_count"] += 1
                            state["error_count"] += 1
                            sheet_failed += 1
                            state["errors"].append(f"Sheet '{sheet_name}', Row {row_num}: Duplicate Aadhaar '{r_aadhaar}' within the sheet.")
                            continue
                        seen_aadhaars.add(r_aadhaar)
                        batch_aadhaars.add(r_aadhaar)
                        
                    if r_ticket:
                        if r_ticket in seen_tickets:
                            state["skipped_count"] += 1
                            state["duplicate_count"] += 1
                            state["error_count"] += 1
                            sheet_failed += 1
                            state["errors"].append(f"Sheet '{sheet_name}', Row {row_num}: Duplicate Ticket '{r_ticket}' within the sheet.")
                            continue
                        seen_tickets.add(r_ticket)
                        batch_tickets.add(r_ticket)

                    valid_rows.append({
                        "row_num": row_num,
                        "id": r_id,
                        "name": r_name,
                        "doj": r_doj,
                        "category": r_category,
                        "scheme": r_scheme,
                        "aadhaar": r_aadhaar,
                        "ticket": r_ticket,
                        "batch": r_batch,
                        "shop": r_shop,
                        "offer_id": r_offer_id,
                        "mobile": r_mobile,
                        "email": r_email,
                        "raw_row": row
                    })
                except Exception as e:
                    state["skipped_count"] += 1
                    state["error_count"] += 1
                    sheet_failed += 1
                    state["errors"].append(f"Sheet '{sheet_name}', Row {row_num}: Error parsing columns: {str(e)}")

            if not valid_rows:
                return

            # Bulk lookups for database checks
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
                    r_scheme = item["scheme"]
                    r_aadhaar = item["aadhaar"]
                    r_ticket = item["ticket"]
                    r_batch = item["batch"]
                    r_shop = item["shop"]
                    r_offer_id = item["offer_id"]
                    r_mobile = item["mobile"]
                    r_email = item["email"]
                    raw_row = item["raw_row"]

                    # Cross-trainee database checks
                    if r_ticket and r_ticket in existing_by_ticket:
                        ticket_owner = existing_by_ticket[r_ticket]
                        if r_id and ticket_owner.id != r_id:
                            state["skipped_count"] += 1
                            state["error_count"] += 1
                            sheet_failed += 1
                            state["errors"].append(f"Sheet '{sheet_name}', Row {row_num}: Ticket '{r_ticket}' already exists for another trainee '{ticket_owner.id}' in database.")
                            continue
                            
                    if r_aadhaar and r_aadhaar in existing_by_aadhaar:
                        aadhaar_owner = existing_by_aadhaar[r_aadhaar]
                        if r_id and aadhaar_owner.id != r_id:
                            state["skipped_count"] += 1
                            state["error_count"] += 1
                            sheet_failed += 1
                            state["errors"].append(f"Sheet '{sheet_name}', Row {row_num}: Aadhaar '{r_aadhaar}' already exists for another trainee '{aadhaar_owner.id}' in database.")
                            continue

                    trainee = None
                    if r_ticket and r_ticket in existing_by_ticket:
                        trainee = existing_by_ticket[r_ticket]
                    if not trainee and r_id and r_id in existing_by_id:
                        trainee = existing_by_id[r_id]
                    if not trainee and r_aadhaar and r_aadhaar in existing_by_aadhaar:
                        trainee = existing_by_aadhaar[r_aadhaar]

                    resolved_id = trainee.id if trainee else (r_id if r_id else r_ticket)
                    
                    if "processed_ids" not in state:
                        state["processed_ids"] = set()
                    state["processed_ids"].add(resolved_id)

                    # Extract unknown columns
                    all_synonyms = set()
                    for syns in WorkbookParser.SYNONYMS.values():
                        all_synonyms.update(syns)
                    unknown_data = {}
                    for k, val in raw_row.items():
                        if k not in WorkbookParser.SYNONYMS and k not in all_synonyms and not k.startswith('_'):
                            unknown_data[k] = val

                    if trainee:
                        if trainee.id not in sheet_before_state:
                            sheet_before_state[trainee.id] = cls._serialize_trainee_state(trainee)
                        is_rehire = False
                        if trainee.status in ("SEPARATED", "BLOCKED"):
                            if trainee.dol and r_doj > trainee.dol and r_doj != trainee.doj:
                                is_rehire = True

                        if is_rehire:
                            prev_doj = trainee.doj
                            prev_invoices = []
                            prev_ledger = []
                            prev_validations = []
                            reason = "Separated"

                            if prev_doj:
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

                            # Archive previous lifecycle to TraineeLifecycle table
                            old_lc = TraineeLifecycle(
                                trainee_id=trainee.id,
                                joining_date=trainee.doj,
                                leaving_date=trainee.dol,
                                status=trainee.status,
                                upload_id=state.get("upload_id"),
                                extra_data={
                                    "invoice_history": prev_invoices,
                                    "payment_ledger": prev_ledger,
                                    "validation_history": prev_validations,
                                    "reason": reason,
                                    "category": trainee.category,
                                    "batch": trainee.batch,
                                    "shop": trainee.shop,
                                    "bdc_workbook": trainee.current_workbook,
                                    "bdc_sheet": trainee.current_sheet
                                }
                            )
                            db.add(old_lc)
                            db.flush()

                            trainee.name = r_name
                            trainee.category = r_category
                            trainee.scheme = r_scheme
                            trainee.batch = r_batch or None
                            trainee.shop = r_shop or None
                            trainee.doj = r_doj
                            trainee.dol = None
                            trainee.status = "ACTIVE"
                            trainee.blocked_reason = None
                            if r_aadhaar:
                                trainee.aadhaar = r_aadhaar
                            if r_ticket:
                                trainee.ticket_number = r_ticket
                            
                            trainee.offer_id = r_offer_id
                            trainee.mobile = r_mobile
                            trainee.email = r_email
                            
                            # Merge extra_data
                            ext_data = trainee.extra_data or {}
                            ext_data["offer_id"] = r_offer_id
                            ext_data["mobile"] = r_mobile
                            ext_data["email"] = r_email
                            for k, val in unknown_data.items():
                                ext_data[k] = val
                            trainee.extra_data = make_json_serializable(ext_data)

                            trainee.current_workbook = file_name
                            trainee.current_sheet = sheet_name

                            sheet_updated += 1
                            state["updated_count"] += 1
                            state["rows_rehired"] += 1
                            sheet_after_state[trainee.id] = cls._serialize_trainee_state(trainee)
                        else:
                            changed = False
                            if trainee.name != r_name:
                                trainee.name = r_name
                                changed = True
                                
                            if trainee.status not in ("SEPARATED", "BLOCKED", "INACTIVE"):
                                if trainee.doj != r_doj:
                                    trainee.doj = r_doj
                                    changed = True

                            if (trainee.category or "") != (r_category or ""):
                                trainee.category = r_category
                                changed = True

                            if (trainee.scheme or "") != r_scheme:
                                trainee.scheme = r_scheme
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

                            if (trainee.offer_id or "") != r_offer_id:
                                trainee.offer_id = r_offer_id
                                changed = True
                            if (trainee.mobile or "") != r_mobile:
                                trainee.mobile = r_mobile
                                changed = True
                            if (trainee.email or "") != r_email:
                                trainee.email = r_email
                                changed = True

                            # Save new extra_data fields
                            ext_data = trainee.extra_data or {}
                            ext_changed = False
                            if ext_data.get("offer_id") != r_offer_id:
                                ext_data["offer_id"] = r_offer_id
                                ext_changed = True
                            if ext_data.get("mobile") != r_mobile:
                                ext_data["mobile"] = r_mobile
                                ext_changed = True
                            if ext_data.get("email") != r_email:
                                ext_data["email"] = r_email
                                ext_changed = True
                            for k, val in unknown_data.items():
                                if ext_data.get(k) != val:
                                    ext_data[k] = val
                                    ext_changed = True
                                    
                            if ext_changed:
                                trainee.extra_data = make_json_serializable(ext_data)
                                changed = True

                            if trainee.current_workbook != file_name or trainee.current_sheet != sheet_name:
                                trainee.current_workbook = file_name
                                trainee.current_sheet = sheet_name

                            if changed:
                                if trainee.status not in ("SEPARATED", "BLOCKED"):
                                    trainee.status = "ACTIVE"
                                sheet_updated += 1
                                state["updated_count"] += 1
                                sheet_after_state[trainee.id] = cls._serialize_trainee_state(trainee)
                            else:
                                if trainee.status == "BLOCKED":
                                    state["blocked_count"] += 1
                                elif trainee.status == "SEPARATED":
                                    state["separated_count"] += 1
                                state["rows_no_change"] += 1
                                state["skip_count"] += 1
                    else:
                        ext_data = {
                            "offer_id": r_offer_id,
                            "mobile": r_mobile,
                            "email": r_email
                        }
                        for k, val in unknown_data.items():
                            ext_data[k] = val

                        new_trainee = Trainee(
                            id=resolved_id,
                            name=r_name,
                            doj=r_doj,
                            scheme=r_scheme,
                            category=r_category,
                            batch=r_batch or None,
                            shop=r_shop or None,
                            aadhaar=r_aadhaar or None,
                            ticket_number=r_ticket or None,
                            status="ACTIVE",
                            current_workbook=file_name,
                            current_sheet=sheet_name,
                            offer_id=r_offer_id,
                            mobile=r_mobile,
                            email=r_email,
                            extra_data=ext_data
                        )
                        db.add(new_trainee)
                        existing_by_id[resolved_id] = new_trainee
                        if r_ticket:
                            existing_by_ticket[r_ticket] = new_trainee
                        if r_aadhaar:
                            existing_by_aadhaar[r_aadhaar] = new_trainee
                        sheet_inserted += 1
                        state["created_count"] += 1
                        sheet_after_state[resolved_id] = cls._serialize_trainee_state(new_trainee)

                    bdc_rec = BDCRecord(
                        trainee_id=resolved_id,
                        doj=r_doj,
                        scheme=r_scheme,
                        file_name=file_name,
                        extra_data={
                            "sheet_name": sheet_name,
                            "category": r_category,
                            "aadhaar": r_aadhaar,
                            "ticket_number": r_ticket,
                            "batch": r_batch,
                            "shop": r_shop,
                            "offer_id": r_offer_id,
                            "mobile": r_mobile,
                            "email": r_email,
                            **unknown_data
                        }
                    )
                    db.add(bdc_rec)
                    state["success_count"] += 1
                except Exception as e:
                    state["skipped_count"] += 1
                    state["error_count"] += 1
                    sheet_failed += 1
                    state["errors"].append(f"Sheet '{sheet_name}', Row {row_num}: Database operation failed: {str(e)}")

            db.flush()

        # Run process_batch in batches
        for i in range(0, len(sheet["rows"]), BATCH_SIZE):
            process_batch(sheet["rows"][i:i+BATCH_SIZE])

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
            warnings=len(state["warnings"]),
            errors=sheet_failed,
            before_state={"trainees": sheet_before_state} if sheet_before_state else None,
            after_state={"trainees": sheet_after_state} if sheet_after_state else None,
            upload_id=state.get("upload_id"),
            commit=False
        )

        # Detailed parser debug log
        import logging
        logger = logging.getLogger("workbook_parser")
        class_info = WorkbookParser._CLASSIFICATION_REASONS.get(sheet_name, {})
        classification_score = class_info.get("score_summary", "N/A")
        sheet_type = sheet.get("sheet_type", "Employee Master")
        
        debug_msg = (
            f"\n=== DETAILED PARSER DEBUG LOG ===\n"
            f"Workbook Name       : {file_name}\n"
            f"Sheet Name          : {sheet_name}\n"
            f"Detected Headers    : {sheet.get('original_headers', [])}\n"
            f"Classification Score: {classification_score}\n"
            f"Final Sheet Type    : {sheet_type}\n"
            f"Processing Route    : Employee Master Ingestion\n"
            f"Rows Imported       : {sheet_inserted}\n"
            f"Rows Updated        : {sheet_updated}\n"
            f"Rows Failed         : {sheet_failed}\n"
            f"Warnings            : {state.get('warnings', [])}\n"
            f"Errors              : {state.get('errors', [])}\n"
            f"================================="
        )
        logger.info(debug_msg)
        print(debug_msg)

    @classmethod
    def _process_separation_sheet(cls, db: Session, sheet: Dict[str, Any], file_name: str, BATCH_SIZE: int, state: Dict[str, Any]) -> None:
        import time
        sheet_name = sheet["sheet_name"]
        sheet_separated = 0
        sheet_blocked = 0
        sheet_failed = 0
        sheet_start_time = time.time()
        sheet_before_state = {}
        sheet_after_state = {}

        sheet_month = cls._parse_sheet_month(sheet_name)
        seen_row_trainees = set()

        def process_batch(rows_to_process):
            nonlocal sheet_separated, sheet_blocked, sheet_failed
            valid_rows = []
            batch_trainee_ids = set()

            for row in rows_to_process:
                row_num = row["_row_num"]
                state["rows_processed"] += 1
                try:
                    # Get standard key values
                    trainee_id = row.get("trainee_id") or row.get("ticket_number") or ""
                    dol = row.get("end_date")
                    reason = str(row.get("reason") or "").strip() or "Separated"

                    if not trainee_id or not dol:
                        state["skipped_count"] += 1
                        state["error_count"] += 1
                        sheet_failed += 1
                        state["errors"].append(f"Sheet '{sheet_name}', Row {row_num}: Missing Trainee ID or Date of Leaving.")
                        continue

                    if (trainee_id, dol) in seen_row_trainees:
                        state["skipped_count"] += 1
                        state["duplicate_count"] += 1
                        state["error_count"] += 1
                        sheet_failed += 1
                        state["errors"].append(f"Sheet '{sheet_name}', Row {row_num}: Duplicate separation entry for '{trainee_id}' on {dol} within the sheet.")
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
                    state["skipped_count"] += 1
                    state["error_count"] += 1
                    sheet_failed += 1
                    state["errors"].append(f"Sheet '{sheet_name}', Row {row_num}: Error parsing columns: {str(e)}")

            if not valid_rows:
                return

            existing_trainees = {
                t.id: t for t in db.query(Trainee).filter(Trainee.id.in_(batch_trainee_ids)).all()
            }
            missing_ids = batch_trainee_ids - set(existing_trainees.keys())
            if missing_ids:
                by_ticket = db.query(Trainee).filter(Trainee.ticket_number.in_(missing_ids)).all()
                for t in by_ticket:
                    existing_trainees[t.ticket_number] = t
                    existing_trainees[t.id] = t

            for item in valid_rows:
                row_num = item["row_num"]
                try:
                    trainee_id = item["id"]
                    dol = item["dol"]
                    reason = item["reason"]

                    if trainee_id in existing_trainees:
                        trainee = existing_trainees[trainee_id]
                        
                        # Newer separation check
                        if trainee.dol:
                            if dol == trainee.dol or dol < trainee.dol:
                                state["skip_count"] += 1
                                continue
                            else: # dol > trainee.dol
                                prev_doj = trainee.doj
                                prev_invoices = []
                                prev_ledger = []
                                prev_validations = []
                                old_reason = "Separated"

                                if prev_doj:
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
                                        old_reason = trainee.blocked_reason or "Blocked"
                                    elif trainee.status == "SEPARATED":
                                        latest_sep = db.query(SeparationRecord).filter(
                                            SeparationRecord.trainee_id == trainee.id
                                        ).order_by(SeparationRecord.dol.desc()).first()
                                        if latest_sep:
                                            old_reason = latest_sep.reason or "Separated"

                                old_lc = TraineeLifecycle(
                                    trainee_id=trainee.id,
                                    joining_date=trainee.doj,
                                    leaving_date=trainee.dol,
                                    status=trainee.status,
                                    upload_id=state.get("upload_id"),
                                    extra_data={
                                        "invoice_history": prev_invoices,
                                        "payment_ledger": prev_ledger,
                                        "validation_history": prev_validations,
                                        "reason": old_reason,
                                        "category": trainee.category,
                                        "batch": trainee.batch,
                                        "shop": trainee.shop,
                                        "bdc_workbook": trainee.current_workbook,
                                        "bdc_sheet": trainee.current_sheet
                                    }
                                )
                                db.add(old_lc)
                                db.flush()

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

                        if days_worked < 30:
                            status_after = "BLOCKED"
                            blocked_reason = f"Early Separation - Resigned before 30 days (tenure: {days_worked} days)"
                            reason = "Early Separation"
                            state["early_separations_count"] += 1
                            sheet_blocked += 1
                            state["blocked_count"] += 1
                        else:
                            sheet_separated += 1
                            state["separated_count"] += 1

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
                                    "sheet": sheet_name,
                                    "sheet_name": sheet_name,
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
                            state["skip_count"] += 1

                        trainee.dol = dol
                        trainee.status = status_after
                        trainee.blocked_reason = blocked_reason
                        sheet_after_state[trainee.id] = cls._serialize_trainee_state(trainee)
                        
                        state["success_count"] += 1
                    else:
                        state["skipped_count"] += 1
                        state["unknown_employees_count"] += 1
                        state["error_count"] += 1
                        sheet_failed += 1
                        state["errors"].append(f"Sheet '{sheet_name}', Row {row_num}: Trainee ID '{trainee_id}' not found in Employee Master. Please import BDC Master first.")
                except Exception as e:
                    state["skipped_count"] += 1
                    state["error_count"] += 1
                    sheet_failed += 1
                    state["errors"].append(f"Sheet '{sheet_name}', Row {row_num}: Database operation failed: {str(e)}")

            db.flush()

        # Run process_batch in batches
        for i in range(0, len(sheet["rows"]), BATCH_SIZE):
            process_batch(sheet["rows"][i:i+BATCH_SIZE])

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
            warnings=len(state["warnings"]),
            errors=sheet_failed,
            before_state={"trainees": sheet_before_state} if sheet_before_state else None,
            after_state={"trainees": sheet_after_state} if sheet_after_state else None,
            upload_id=state.get("upload_id"),
            commit=False
        )

        # Detailed parser debug log
        import logging
        logger = logging.getLogger("workbook_parser")
        class_info = WorkbookParser._CLASSIFICATION_REASONS.get(sheet_name, {})
        classification_score = class_info.get("score_summary", "N/A")
        sheet_type = sheet.get("sheet_type", "Separation")
        
        debug_msg = (
            f"\n=== DETAILED PARSER DEBUG LOG ===\n"
            f"Workbook Name       : {file_name}\n"
            f"Sheet Name          : {sheet_name}\n"
            f"Detected Headers    : {sheet.get('original_headers', [])}\n"
            f"Classification Score: {classification_score}\n"
            f"Final Sheet Type    : {sheet_type}\n"
            f"Processing Route    : Separation Ingestion\n"
            f"Rows Imported       : 0\n"
            f"Rows Updated        : {sheet_separated + sheet_blocked}\n"
            f"Rows Failed         : {sheet_failed}\n"
            f"Warnings            : {state.get('warnings', [])}\n"
            f"Errors              : {state.get('errors', [])}\n"
            f"================================="
        )
        logger.info(debug_msg)
        print(debug_msg)

    @classmethod
    def import_bdc_workbook(cls, db: Session, file_content: bytes, file_name: str, upload_mode: str = "INCREMENTAL", operator: str = "Admin") -> Dict[str, Any]:
        """Processes the BDC Master Workbook using Universal WorkbookParser."""
        import time
        import uuid
        import hashlib
        start_time = time.time()
        
        # 1. Compute file hash and check duplicate
        file_hash = hashlib.sha256(file_content).hexdigest()
        file_size = len(file_content)
        
        # Unique UUID for the upload history
        current_upload_id = str(uuid.uuid4())
        
        existing_upload = db.query(UploadHistory).filter(UploadHistory.file_hash == file_hash).first()
        is_duplicate = False
        duplicate_warning = None
        if existing_upload:
            is_duplicate = True
            duplicate_warning = f"Workbook '{file_name}' was already uploaded previously (Upload ID: {existing_upload.upload_id})."
            
        # Create UploadHistory first and flush it to the session
        upload = UploadHistory(
            upload_id=current_upload_id,
            file_name=file_name,
            file_hash=file_hash,
            file_size=file_size,
            upload_type="UNKNOWN",
            uploaded_by=operator,
            processing_time=0.0,
            status="PROCESSING",
            is_duplicate=is_duplicate,
            remarks=duplicate_warning
        )
        db.add(upload)
        db.flush()

        parsed_wb = WorkbookParser.parse_workbook(file_content, file_name)
        wb_stats = parsed_wb["stats"]
        
        warnings = list(wb_stats["warnings"])
        if duplicate_warning:
            warnings.append(duplicate_warning)
        errors = list(wb_stats["errors"])
        
        state = {
            "success_count": 0,
            "skipped_count": 0,
            "created_count": 0,
            "updated_count": 0,
            "skip_count": 0,
            "error_count": 0,
            "duplicate_count": 0,
            "blocked_count": 0,
            "separated_count": 0,
            "early_separations_count": 0,
            "unknown_employees_count": 0,
            "rows_processed": 0,
            "rows_no_change": 0,
            "rows_rehired": 0,
            "rows_inactive": 0,
            "warnings": warnings,
            "errors": errors,
            "upload_id": current_upload_id,
            "processed_ids": set()
        }

        sheets_processed = []
        employee_sheets = []
        separation_sheets = []
        skipped_sheets = list(wb_stats["skipped_sheets"])
        failed_sheets = list(wb_stats["failed_sheets"])
        
        BATCH_SIZE = 2000
        
        for sheet in parsed_wb["sheets"]:
            sheet_name = sheet["sheet_name"]
            sheet_type = sheet["sheet_type"]
            
            if sheet_type in ("Employee Master", "BDC"):
                sheets_processed.append(sheet_name)
                employee_sheets.append(sheet_name)
                cls._process_employee_master_sheet(db, sheet, file_name, BATCH_SIZE, state)
            elif sheet_type == "Separation":
                sheets_processed.append(sheet_name)
                separation_sheets.append(sheet_name)
                cls._process_separation_sheet(db, sheet, file_name, BATCH_SIZE, state)
            else:
                skipped_sheets.append(sheet_name)
                state["warnings"].append(f"Sheet '{sheet_name}' ignored. Classification: '{sheet_type}'. Reason: Sheet type is not supported for BDC Master/Separation sync.")

        # Full Sync Mode: Mark missing ACTIVE employees as INACTIVE
        if upload_mode == "FULL_SYNC":
            if employee_sheets and not failed_sheets:
                # Find currently ACTIVE trainees not present in processed_ids
                missing_trainees = db.query(Trainee).filter(
                    Trainee.status == "ACTIVE",
                    ~Trainee.id.in_(state["processed_ids"])
                ).all()
                for mt in missing_trainees:
                    before_state = cls._serialize_trainee_state(mt)
                    mt.status = "INACTIVE"
                    mt.blocked_reason = "Missing from Latest Master"
                    state["rows_inactive"] += 1
                    
                    AuditLogRepository.add_log(
                        db=db,
                        action="EMPLOYEE_DEACTIVATED",
                        module="BDC_UPLOAD",
                        details=f"Employee '{mt.name}' ({mt.id}) deactivated: Missing from Latest Master.",
                        operator=operator,
                        workbook=file_name,
                        employee_id=mt.id,
                        before_state=before_state,
                        after_state=cls._serialize_trainee_state(mt),
                        upload_id=current_upload_id,
                        commit=False
                    )
                db.flush()
            else:
                state["warnings"].append("Full Sync mode requested, but Employee Master sheets were empty or workbook processing encountered errors. Deactivations skipped.")

        if not sheets_processed:
            raise ValueError("No sheets with required columns found.")
            
        total_duration = time.time() - start_time
        
        # Classify upload type
        if employee_sheets and separation_sheets:
            upload_type = "MIXED"
        elif employee_sheets:
            upload_type = "FULL_SYNC" if upload_mode == "FULL_SYNC" else "INCREMENTAL"
        elif separation_sheets:
            upload_type = "SEPARATION"
        else:
            upload_type = "UNKNOWN"
            
        upload_status = "SUCCESS"
        if failed_sheets:
            upload_status = "PARTIAL" if sheets_processed else "FAILED"
            
        # Update existing UploadHistory summary fields in database
        upload.upload_type = upload_type
        upload.processing_time = total_duration
        upload.status = upload_status
        upload.workbook_version = wb_stats.get("workbook_version")
        upload.parser_version = wb_stats.get("parser_version", "2.0.0")
        upload.sheet_count = wb_stats.get("number_of_sheets", 0)
        upload.visible_sheet_count = len(sheets_processed)
        upload.hidden_sheet_count = len(skipped_sheets)
        upload.rows_processed = state.get("rows_processed", 0)
        upload.rows_inserted = state.get("created_count", 0)
        upload.rows_updated = state.get("updated_count", 0)
        upload.rows_no_change = state.get("rows_no_change", 0)
        upload.rows_skipped = state.get("skip_count", 0)
        upload.rows_failed = state.get("error_count", 0)
        upload.rows_rehired = state.get("rows_rehired", 0)
        upload.rows_inactive = state.get("rows_inactive", 0)
        upload.employee_sheets = employee_sheets
        upload.separation_sheets = separation_sheets
        upload.invoice_sheets = []
        upload.remarks = duplicate_warning
        db.flush()
        
        AuditLogRepository.add_log(
            db=db,
            action="IMPORT_BDC_WORKBOOK",
            module="BDC_UPLOAD",
            details=f"File: {file_name}. Sheets processed: {', '.join(sheets_processed)}. Imported: {state['created_count']}, Updated: {state['updated_count']}, Inactivated: {state['rows_inactive']}, Errors: {state['error_count']}. Duration: {total_duration:.2f}s",
            operator=operator,
            workbook=file_name,
            sheet=", ".join(sheets_processed),
            rows_count=state["rows_processed"],
            duration=total_duration,
            inserted=state["created_count"],
            updated=state["updated_count"],
            failed=state["error_count"],
            warnings=len(state["warnings"]),
            errors=state["error_count"],
            upload_id=current_upload_id,
            commit=False
        )
        
        db.commit()

        return {
            "workbook_name": file_name,
            "number_of_sheets": len(parsed_wb["sheets"]) + len(skipped_sheets),
            "processed_sheets": sheets_processed,
            "skipped_sheets": skipped_sheets,
            "failed_sheets": failed_sheets,
            "inserted_records": state["created_count"],
            "updated_records": state["updated_count"] + state["separated_count"] + state["blocked_count"],
            "skipped_records": state["skip_count"],
            "failed_records": state["error_count"],
            "warnings": state["warnings"],
            "errors": state["errors"],
            "upload_id": current_upload_id,
            "is_duplicate": is_duplicate,
            
            # Spec compliance keys
            "employee_sheets": employee_sheets,
            "separation_sheets": separation_sheets,
            "rows_processed": state["rows_processed"],
            "rows_imported": state["created_count"],
            "rows_updated": state["updated_count"] + state["separated_count"] + state["blocked_count"],
            "rows_skipped": state["skip_count"],
            "rows_failed": state["error_count"],
            "rows_no_change": state["rows_no_change"],
            "rows_rehired": state["rows_rehired"],
            "rows_inactive": state["rows_inactive"],
            "processing_time": total_duration,
            
            # Legacy compatibility keys
            "sheets_processed": sheets_processed,
            "employees_updated": state["updated_count"] + state["separated_count"] + state["blocked_count"],
            "early_separations": state["early_separations_count"],
            "blocked_employees": state["blocked_count"],
            "inserted": state["created_count"],
            "updated": state["updated_count"] + state["separated_count"] + state["blocked_count"],
            "blocked": state["blocked_count"],
            "separated": state["separated_count"],
            "duplicates": state["duplicate_count"],
            "unknown_employees": state["unknown_employees_count"],
            
            # original keys
            "success_count": state["success_count"],
            "skipped_count": state["skipped_count"],
            "total_records": state["success_count"] + state["skipped_count"],
            "created_count": state["created_count"],
            "updated_count": state["updated_count"] + state["separated_count"] + state["blocked_count"],
            "insert_count": state["created_count"],
            "update_count": state["updated_count"] + state["separated_count"] + state["blocked_count"],
            "skip_count": state["skip_count"],
            "error_count": state["error_count"],
            
            # Additional UI friendly stats keys
            "Workbook Name": file_name,
            "Processed Sheets": ", ".join(sheets_processed),
            "Skipped Sheets": ", ".join(skipped_sheets),
            "Inserted": state["created_count"],
            "Updated": state["updated_count"] + state["separated_count"] + state["blocked_count"],
            "Skipped": state["skip_count"],
            "Failed": state["error_count"]
        }

    @classmethod
    def _save_upload_history(
        cls,
        db: Session,
        upload_id: str,
        file_name: str,
        file_hash: str,
        file_size: int,
        upload_type: str,
        uploaded_by: str,
        processing_time: float,
        status: str,
        is_duplicate: bool,
        stats: dict,
        state: dict,
        employee_sheets: List[str],
        separation_sheets: List[str],
        invoice_sheets: List[str],
        remarks: Optional[str] = None
    ) -> None:
        hist = UploadHistory(
            upload_id=upload_id,
            file_name=file_name,
            file_hash=file_hash,
            file_size=file_size,
            upload_type=upload_type,
            uploaded_by=uploaded_by,
            processing_time=processing_time,
            status=status,
            is_duplicate=is_duplicate,
            workbook_version=stats.get("workbook_version"),
            parser_version=stats.get("parser_version", "2.0.0"),
            application_version="2.0.0",
            sheet_count=stats.get("number_of_sheets", 0),
            visible_sheet_count=len(stats.get("sheets_processed", [])),
            hidden_sheet_count=len(stats.get("skipped_sheets", [])),
            rows_processed=state.get("rows_processed", 0),
            rows_inserted=state.get("created_count", 0),
            rows_updated=state.get("updated_count", 0),
            rows_no_change=state.get("rows_no_change", 0),
            rows_skipped=state.get("skip_count", 0),
            rows_failed=state.get("error_count", 0),
            rows_rehired=state.get("rows_rehired", 0),
            rows_inactive=state.get("rows_inactive", 0),
            employee_sheets=employee_sheets,
            separation_sheets=separation_sheets,
            invoice_sheets=invoice_sheets,
            remarks=remarks
        )
        db.add(hist)
        db.commit()

    @classmethod
    def import_separation_workbook(cls, db: Session, file_content: bytes, file_name: str, operator: str = "Admin") -> Dict[str, Any]:
        """Processes the Separation Workbook (NAPS, B.Tech, M.Tech) using Universal WorkbookParser."""
        import time
        import uuid
        import hashlib
        start_time = time.time()
        
        # Compute file hash and check duplicate
        file_hash = hashlib.sha256(file_content).hexdigest()
        file_size = len(file_content)
        
        # Unique UUID for the upload history
        current_upload_id = str(uuid.uuid4())
        
        existing_upload = db.query(UploadHistory).filter(UploadHistory.file_hash == file_hash).first()
        is_duplicate = False
        duplicate_warning = None
        if existing_upload:
            is_duplicate = True
            duplicate_warning = f"Workbook '{file_name}' was already uploaded previously (Upload ID: {existing_upload.upload_id})."
            
        # Create UploadHistory first and flush it
        upload = UploadHistory(
            upload_id=current_upload_id,
            file_name=file_name,
            file_hash=file_hash,
            file_size=file_size,
            upload_type="SEPARATION",
            uploaded_by=operator,
            processing_time=0.0,
            status="PROCESSING",
            is_duplicate=is_duplicate,
            remarks=duplicate_warning
        )
        db.add(upload)
        db.flush()

        parsed_wb = WorkbookParser.parse_workbook(file_content, file_name)
        wb_stats = parsed_wb["stats"]
        
        warnings = list(wb_stats["warnings"])
        if duplicate_warning:
            warnings.append(duplicate_warning)
        errors = list(wb_stats["errors"])
        
        state = {
            "success_count": 0,
            "skipped_count": 0,
            "created_count": 0,
            "updated_count": 0,
            "skip_count": 0,
            "error_count": 0,
            "duplicate_count": 0,
            "blocked_count": 0,
            "separated_count": 0,
            "early_separations_count": 0,
            "unknown_employees_count": 0,
            "rows_processed": 0,
            "rows_no_change": 0,
            "rows_rehired": 0,
            "rows_inactive": 0,
            "warnings": warnings,
            "errors": errors,
            "upload_id": current_upload_id
        }

        sheets_processed = []
        employee_sheets = []
        separation_sheets = []
        skipped_sheets = list(wb_stats["skipped_sheets"])
        failed_sheets = list(wb_stats["failed_sheets"])
        
        BATCH_SIZE = 2000
        
        for sheet in parsed_wb["sheets"]:
            sheet_name = sheet["sheet_name"]
            sheet_type = sheet["sheet_type"]
            
            if sheet_type == "Separation":
                sheets_processed.append(sheet_name)
                separation_sheets.append(sheet_name)
                cls._process_separation_sheet(db, sheet, file_name, BATCH_SIZE, state)
            elif sheet_type in ("Employee Master", "BDC"):
                skipped_sheets.append(sheet_name)
                state["warnings"].append(f"Sheet '{sheet_name}' ignored. Classification: '{sheet_type}'. Reason: Sheet type is not supported for Separation sync.")
            else:
                skipped_sheets.append(sheet_name)
                state["warnings"].append(f"Sheet '{sheet_name}' ignored. Classification: '{sheet_type}'. Reason: Sheet type is not supported for Separation sync.")

        if not sheets_processed:
            raise ValueError("No sheets with required columns found.")
            
        total_duration = time.time() - start_time
        
        upload_status = "SUCCESS"
        if failed_sheets:
            upload_status = "PARTIAL" if sheets_processed else "FAILED"
            
        # Update existing UploadHistory summary fields in database
        upload.upload_type = "SEPARATION"
        upload.processing_time = total_duration
        upload.status = upload_status
        upload.workbook_version = wb_stats.get("workbook_version")
        upload.parser_version = wb_stats.get("parser_version", "2.0.0")
        upload.sheet_count = wb_stats.get("number_of_sheets", 0)
        upload.visible_sheet_count = len(sheets_processed)
        upload.hidden_sheet_count = len(skipped_sheets)
        upload.rows_processed = state.get("rows_processed", 0)
        upload.rows_inserted = 0
        upload.rows_updated = state.get("separated_count", 0) + state.get("blocked_count", 0)
        upload.rows_no_change = state.get("rows_no_change", 0)
        upload.rows_skipped = state.get("skip_count", 0)
        upload.rows_failed = state.get("error_count", 0)
        upload.rows_rehired = 0
        upload.rows_inactive = 0
        upload.employee_sheets = []
        upload.separation_sheets = separation_sheets
        upload.invoice_sheets = []
        upload.remarks = duplicate_warning
        db.flush()
        
        AuditLogRepository.add_log(
            db=db,
            action="IMPORT_SEPARATION_WORKBOOK",
            module="SEPARATION_UPLOAD",
            details=f"File: {file_name}. Sheets processed: {', '.join(sheets_processed)}. Separated: {state['separated_count'] + state['blocked_count']}, Errors: {state['error_count']}. Duration: {total_duration:.2f}s",
            operator=operator,
            workbook=file_name,
            sheet=", ".join(sheets_processed),
            rows_count=state["rows_processed"],
            duration=total_duration,
            inserted=0,
            updated=state["separated_count"] + state["blocked_count"],
            failed=state["error_count"],
            warnings=len(state["warnings"]),
            errors=state["error_count"],
            upload_id=current_upload_id,
            commit=False
        )
        
        db.commit()
        
        return {
            "workbook_name": file_name,
            "number_of_sheets": len(parsed_wb["sheets"]) + len(skipped_sheets),
            "processed_sheets": sheets_processed,
            "skipped_sheets": skipped_sheets,
            "failed_sheets": failed_sheets,
            "inserted_records": state["separated_count"] + state["blocked_count"],
            "updated_records": state["skip_count"],
            "skipped_records": state["skipped_count"] - state["error_count"],
            "failed_records": state["error_count"],
            "warnings": state["warnings"],
            "errors": state["errors"],
            "upload_id": current_upload_id,
            "is_duplicate": is_duplicate,
            
            # Spec compliance keys
            "employee_sheets": employee_sheets,
            "separation_sheets": separation_sheets,
            "rows_processed": state["rows_processed"],
            "rows_imported": 0,
            "rows_updated": state["separated_count"] + state["blocked_count"],
            "rows_skipped": state["skip_count"],
            "rows_failed": state["error_count"],
            "rows_no_change": state["rows_no_change"],
            "rows_rehired": state["rows_rehired"],
            "rows_inactive": state["rows_inactive"],
            "processing_time": total_duration,
            
            # Legacy compatibility keys
            "sheets_processed": sheets_processed,
            "employees_updated": state["separated_count"] + state["blocked_count"],
            "early_separations": state["early_separations_count"],
            "blocked_employees": state["blocked_count"],
            "inserted": 0,
            "updated": state["separated_count"] + state["blocked_count"],
            "blocked": state["blocked_count"],
            "separated": state["separated_count"],
            "duplicates": state["duplicate_count"],
            "unknown_employees": state["unknown_employees_count"],
            
            # original keys
            "success_count": state["success_count"],
            "skipped_count": state["skipped_count"],
            "errors": state["errors"],
            "total_records": state["success_count"] + state["skipped_count"],
            "separated_count": state["separated_count"],
            "already_synced_count": state["skip_count"]
        }

    @classmethod
    def parse_pair(cls, pair_val: Any) -> Dict[str, float]:
        """
        Parse a textual pair value into counts of pairs, jeans, and shirts.
        """
        res = {"pair_count": 0.0, "jeans_count": 0.0, "shirt_count": 0.0}
        if pair_val is None:
            return res
        pair_str = str(pair_val).strip().lower()
        if not pair_str or pair_str.lower() in ('nan', 'none', 'null') or pair_str.startswith('#'):
            return res

        # Check for specific jeans and shirt counts
        # E.g. "2 Pair Jeans & 2 Pair T Shirt" or "1.5 pr jeans, 1 shirt"
        import re
        jeans_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:pair|pr)?s?\s*(?:of)?\s*(?:jeans?|jean)', pair_str)
        shirt_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:pair|pr)?s?\s*(?:of)?\s*(?:t\s*shirts?|t-shirts?|tshirts?|shirts?|shirt)', pair_str)
        
        has_specific = False
        if jeans_match:
            res["jeans_count"] = float(jeans_match.group(1))
            has_specific = True
        if shirt_match:
            res["shirt_count"] = float(shirt_match.group(1))
            has_specific = True

        # If it is like "2 Pair" (no specific jeans/shirt count), or has a generic pair prefix
        # E.g. "2 Pair", "1.5 pr", "3"
        generic_match = re.search(r'^(\d+(?:\.\d+)?)\s*(?:pair|pr)?s?$', pair_str)
        val_float = 0.0
        if not generic_match:
            try:
                val_float = float(pair_str)
                generic_match = True
            except ValueError:
                generic_match = False
        else:
            val_float = float(generic_match.group(1))

        if generic_match and not has_specific:
            res["pair_count"] = val_float
            res["jeans_count"] = val_float
            res["shirt_count"] = val_float
        else:
            leading_match = re.match(r'^(\d+(?:\.\d+)?)\s*(?:pair|pr)s?\b', pair_str)
            if leading_match:
                res["pair_count"] = float(leading_match.group(1))
            else:
                res["pair_count"] = max(res["jeans_count"], res["shirt_count"])
                
        return res

    @classmethod
    def parse_pdf_invoice(cls, file_content: bytes, file_name: str) -> Dict[str, Any]:
        """
        Parses a PDF invoice using pdfplumber, extracting tables, matching headers using synonyms,
        and returning a structure compatible with WorkbookParser.parse_workbook.
        """
        import io
        import pdfplumber
        
        stats = {
            "workbook_name": file_name,
            "number_of_sheets": 1,
            "sheets_processed": ["Invoice"],
            "skipped_sheets": [],
            "failed_sheets": [],
            "warnings": [],
            "errors": []
        }
        
        all_rows = []
        headers = None
        header_idx = None
        
        # Define synonyms mapping for header detection
        invoice_synonyms = {
            "ticket_number": ["t no", "ticket no", "ticket number", "pers no", "ticket", "ticketid", "tktno", "tktnumber", "boarding ticket", "ticket id", "persno", "personnelno", "personnelnumber", "emp id", "employee id", "employee_id", "emp_id", "trainee id", "trainee_id"],
            "joining_date": ["date of joining", "joining date", "doj", "joining"],
            "batch": ["batch no", "batch"],
            "candidate_name": ["candidates name", "candidate name", "employee name", "name", "completename", "completname", "traineename", "employeename", "firstname", "fullname", "billed name", "employee_name"],
            "pair": ["pair", "uniform pair", "kit pair"],
            "amount": ["amount", "bill amount", "billing amount", "claimed amount", "total", "billed total", "total amount", "total_amount", "amount_paid"],
            "distribution_date": ["distribution date", "issued date", "date"],
            "page_number": ["page no", "page", "page_number"]
        }
        
        try:
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables()
                    for table in tables:
                        if not table:
                            continue
                        
                        # Find headers if not yet found
                        for row_idx, row in enumerate(table):
                            cleaned_row = [str(c).strip() if c is not None else "" for c in row]
                            
                            if headers is None:
                                matched_fields = set()
                                for cell in cleaned_row:
                                    norm_cell = WorkbookParser.normalize_header(cell)
                                    for field, syns in invoice_synonyms.items():
                                        if norm_cell in [WorkbookParser.normalize_header(s) for s in syns]:
                                            matched_fields.add(field)
                                            break
                                
                                if len(matched_fields) >= 2:
                                    headers = cleaned_row
                                    header_idx = row_idx
                                    continue
                            
                            if headers is not None:
                                if row_idx == header_idx and len(all_rows) == 0:
                                    continue
                                if all(c == "" for c in cleaned_row):
                                    continue
                                all_rows.append(cleaned_row)
        except Exception as e:
            stats["failed_sheets"].append("Invoice")
            stats["errors"].append(f"Failed parsing PDF: {str(e)}")
            return {
                "stats": stats,
                "sheets": []
            }
            
        if headers is None:
            stats["skipped_sheets"].append("Invoice")
            stats["warnings"].append("Could not detect invoice headers in PDF.")
            return {
                "stats": stats,
                "sheets": []
            }
            
        # Dedup headers
        normalized_headers = []
        seen_headers = {}
        for idx, orig_h in enumerate(headers):
            norm_h = WorkbookParser.normalize_header(orig_h)
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
        
        for r_idx, row in enumerate(all_rows, start=1):
            row_cells = row + [""] * (len(headers) - len(row))
            row_cells = row_cells[:len(headers)]
            
            if all(val is None or str(val).strip() == "" for val in row_cells):
                blank_rows_count += 1
                continue
                
            row_dict = {}
            for idx, norm_h in enumerate(normalized_headers):
                val = row_cells[idx]
                row_dict[norm_h] = val
                
            row_dict["_row_num"] = r_idx
            rows_data.append(row_dict)
            valid_rows_count += 1
            
        parsed_sheets = [{
            "sheet_name": "Invoice",
            "sheet_type": "Invoice",
            "original_headers": headers,
            "normalized_headers": normalized_headers,
            "rows": rows_data,
            "total_rows": len(all_rows) + 1,
            "valid_rows": valid_rows_count,
            "blank_rows": blank_rows_count
        }]
        
        return {
            "stats": stats,
            "sheets": parsed_sheets
        }

    @classmethod
    def parse_month_year(cls, val_str: str) -> Tuple[Optional[str], Optional[int]]:
        month_pattern = re.compile(
            r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b',
            re.IGNORECASE
        )
        m_mon = month_pattern.search(val_str)
        
        year_pattern = re.compile(r'\b(20\d{2}|\d{2})\b')
        m_yr = year_pattern.search(val_str)
        
        mon = None
        yr = None
        if m_mon:
            months_map_full = {
                "jan": "January", "feb": "February", "mar": "March", "apr": "April",
                "may": "May", "jun": "June", "jul": "July", "aug": "August",
                "sep": "September", "oct": "October", "nov": "November", "dec": "December"
            }
            mon_raw = m_mon.group(1).lower()[:3]
            mon = months_map_full.get(mon_raw, m_mon.group(1).capitalize())
            
        if m_yr:
            yr_str = m_yr.group(1)
            if len(yr_str) == 2:
                yr = 2000 + int(yr_str)
            else:
                yr = int(yr_str)
                
        return mon, yr

    @classmethod
    def detect_sheet_metadata(
        cls, 
        sheet: Dict[str, Any], 
        file_content: bytes,
        file_name: str, 
        invoice_number_override: Optional[str] = None, 
        invoice_date_override: Optional[datetime.date] = None
    ) -> Tuple[str, datetime.date, str, int, str]:
        import openpyxl
        import io
        
        inv_num = invoice_number_override
        inv_date = invoice_date_override
        billing_month = None
        billing_year = None
        vendor_name = None
        
        # 1. Search columns of first row
        if sheet["rows"]:
            first_row = sheet["rows"][0]
            if not inv_num:
                inv_num = cls.get_column_value(first_row, ['invoice number', 'invoice_no', 'invoice no', 'bill no', 'bill number', 'reference number', 'reference no'])
            if not inv_date:
                raw_date = cls.get_column_value(first_row, ['invoice date', 'date', 'bill date'])
                inv_date = WorkbookParser.parse_date(raw_date)
            
            # Check for billing month
            billing_month_val = cls.get_column_value(first_row, ['billing month', 'invoice month', 'month'])
            if billing_month_val:
                billing_month, billing_year = cls.parse_month_year(str(billing_month_val))
                
            # Check for vendor
            vendor_val = cls.get_column_value(first_row, ['vendor', 'vendor name', 'vendor_name', 'supplier', 'supplier name'])
            if vendor_val:
                vendor_name = str(vendor_val).strip()

        # 2. Search cells of top rows if Excel
        if not file_name.lower().endswith(".pdf") and (not inv_num or not inv_date or not billing_month or not vendor_name):
            try:
                # Load sheet specifically
                wb = openpyxl.load_workbook(io.BytesIO(file_content), read_only=True, data_only=True)
                if sheet["sheet_name"] in wb.sheetnames:
                    ws = wb[sheet["sheet_name"]]
                    # Scan first 15 rows
                    for r in range(1, 16):
                        for c in range(1, min(ws.max_column + 1, 30)):
                            val = ws.cell(row=r, column=c).value
                            if val and isinstance(val, str):
                                val_clean = val.strip()
                                if not inv_num:
                                    m = re.search(r'(?:invoice\s*no|invoice\s*number|bill\s*no|bill\s*number|reference\s*number)\s*[:\-]?\s*([a-zA-Z0-9\-\/]+)', val_clean, re.IGNORECASE)
                                    if m:
                                        inv_num = m.group(1)
                                if not inv_date:
                                    m = re.search(r'(?:invoice\s*date|bill\s*date|date)\s*[:\-]?\s*([\d\-\.\/]+)', val_clean, re.IGNORECASE)
                                    if m:
                                        inv_date = WorkbookParser.parse_date(m.group(1))
                                if not billing_month:
                                    m = re.search(r'(?:billing\s*month|invoice\s*month|month)\s*[:\-]?\s*([a-zA-Z0-9\s]+)', val_clean, re.IGNORECASE)
                                    if m:
                                        billing_month, billing_year = cls.parse_month_year(m.group(1))
                                if not vendor_name:
                                    m = re.search(r'(?:vendor\s*name|vendor|supplier|supplier\s*name)\s*[:\-]?\s*([a-zA-Z0-9\s\.\,\-\&]+)', val_clean, re.IGNORECASE)
                                    if m:
                                        vendor_name = m.group(1)
                wb.close()
            except Exception:
                pass

        # 3. Fallback from sheet name for billing month/year
        if not billing_month:
            billing_month, billing_year = cls.parse_month_year(sheet["sheet_name"])
            
        # 4. Derive billing month from invoice date if still absent
        if not billing_month and inv_date:
            months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
            billing_month = months[inv_date.month - 1]
            billing_year = inv_date.year

        # 5. Fallback defaults
        if not inv_num:
            base_name = os.path.splitext(file_name)[0]
            inv_num = f"{base_name}_{sheet['sheet_name']}".replace(" ", "_")
        if not inv_date:
            inv_date = datetime.date.today()
        if not billing_month:
            months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
            billing_month = months[inv_date.month - 1]
            billing_year = inv_date.year
        if not vendor_name:
            vendor_name = "Tata Projects"

        return str(inv_num).strip(), inv_date, billing_month, billing_year, vendor_name

    @classmethod
    def import_invoice_workbook(
        cls, 
        db: Session, 
        file_content: bytes, 
        file_name: str,
        invoice_number_override: Optional[str] = None,
        invoice_date_override: Optional[datetime.date] = None,
        operator: str = "Admin"
    ) -> Dict[str, Any]:
        """Processes a Monthly Invoice Workbook/PDF using Universal parser with synonym matching."""
        import time
        import uuid
        import hashlib
        import os
        start_time = time.time()
        
        file_hash = hashlib.sha256(file_content).hexdigest()
        file_size = len(file_content)
        current_upload_id = str(uuid.uuid4())
        
        existing_upload = db.query(UploadHistory).filter(UploadHistory.file_hash == file_hash).first()
        is_duplicate = False
        duplicate_warning = None
        if existing_upload:
            is_duplicate = True
            duplicate_warning = f"Invoice file '{file_name}' was already uploaded previously (Upload ID: {existing_upload.upload_id})."
        
        is_pdf = file_name.lower().endswith(".pdf")
        if is_pdf:
            parsed_wb = cls.parse_pdf_invoice(file_content, file_name)
        else:
            parsed_wb = WorkbookParser.parse_workbook(file_content, file_name)
            
        wb_stats = parsed_wb["stats"]
        
        warnings = list(wb_stats.get("warnings", []))
        if duplicate_warning:
            warnings.append(duplicate_warning)
        errors = list(wb_stats.get("errors", []))
        
        invoice_synonyms = {
            "ticket_number": ["t no", "ticket no", "ticket number", "pers no", "ticket", "ticketid", "tktno", "tktnumber", "boarding ticket", "ticket id", "persno", "personnelno", "personnelnumber", "emp id", "employee id", "employee_id", "emp_id", "trainee id", "trainee_id"],
            "joining_date": ["date of joining", "joining date", "doj", "joining"],
            "batch": ["batch no", "batch"],
            "candidate_name": ["candidates name", "candidate name", "employee name", "name", "completename", "completname", "traineename", "employeename", "firstname", "fullname", "billed name", "employee_name"],
            "pair": ["pair", "uniform pair", "kit pair"],
            "amount": ["amount", "bill amount", "billing amount", "claimed amount", "total", "billed total", "total amount", "total_amount", "amount_paid"],
            "distribution_date": ["distribution date", "issued date", "date"],
            "page_number": ["page no", "page", "page_number"]
        }
        
        success_count = 0
        skipped_count = 0
        error_count = 0
        
        sheets_processed = []
        skipped_sheets = list(wb_stats["skipped_sheets"])
        failed_sheets = list(wb_stats["failed_sheets"])
        
        first_inv_num = None
        first_inv_date = None
        
        BATCH_SIZE = 2000
        
        for sheet in parsed_wb["sheets"]:
            sheet_name = sheet["sheet_name"]
            sheets_processed.append(sheet_name)
            
            # Detect metadata per sheet
            inv_num, inv_date, billing_month, billing_year, vendor_name = cls.detect_sheet_metadata(
                sheet=sheet,
                file_content=file_content,
                file_name=file_name,
                invoice_number_override=invoice_number_override,
                invoice_date_override=invoice_date_override
            )
            
            if not first_inv_num:
                first_inv_num = inv_num
                first_inv_date = inv_date
                
            # Keep previous invoices but mark them as SUPERSEDED if they are currently ACTIVE
            existing_active = db.query(Invoice).filter(
                Invoice.invoice_number == inv_num,
                Invoice.status == "ACTIVE"
            ).all()
            for ext_inv in existing_active:
                ext_inv.status = "SUPERSEDED"
            db.flush()
            
            # Create parent Invoice
            invoice = Invoice(
                invoice_number=inv_num,
                invoice_date=inv_date,
                billing_month=billing_month,
                billing_year=billing_year,
                vendor_name=vendor_name,
                workbook_name=file_name,
                sheet_name=sheet_name,
                upload_id=current_upload_id,
                uploaded_by=operator,
                uploaded_at=datetime.datetime.utcnow(),
                status="ACTIVE",
                total_amount=0.0,
                approved_amount=0.0,
                rejected_amount=0.0,
                fraud_amount=0.0
            )
            db.add(invoice)
            db.flush()
            
            sheet_total_amount = 0.0
            
            def process_batch(rows_to_process, current_sheet, parent_invoice):
                nonlocal success_count, skipped_count, error_count, sheet_total_amount
                
                batch_trainee_ids = set()
                batch_tickets = set()
                valid_rows = []
                
                for row in rows_to_process:
                    row_num = row["_row_num"]
                    
                    r_ticket = cls.get_column_value(row, invoice_synonyms["ticket_number"])
                    r_ticket = str(r_ticket).strip() if r_ticket is not None else ""
                    
                    trainee_id = r_ticket
                    direct_id = cls.get_column_value(row, ['trainee id', 'emp id', 'employee id', 'trainee_id', 'reg no'])
                    if direct_id:
                        trainee_id = str(direct_id).strip()
                    
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
                        
                        billed_name = cls.get_column_value(row, invoice_synonyms["candidate_name"])
                        billed_name = str(billed_name).strip() if billed_name is not None else ""
                        
                        joining_date_raw = cls.get_column_value(row, invoice_synonyms["joining_date"])
                        joining_date = WorkbookParser.parse_date(joining_date_raw) or (trainee.doj if trainee else None)
                        
                        distribution_date_raw = cls.get_column_value(row, invoice_synonyms["distribution_date"])
                        distribution_date = WorkbookParser.parse_date(distribution_date_raw) or parent_invoice.invoice_date
                        
                        batch = cls.get_column_value(row, invoice_synonyms["batch"])
                        batch = str(batch).strip() if batch is not None else (trainee.batch if trainee else "")
                        
                        pair = cls.get_column_value(row, invoice_synonyms["pair"])
                        pair = str(pair).strip() if pair is not None else ""
                        
                        amount_raw = cls.get_column_value(row, invoice_synonyms["amount"])
                        amount = WorkbookParser.parse_float(amount_raw)
                        
                        page_number_raw = cls.get_column_value(row, invoice_synonyms["page_number"])
                        page_number = None
                        if page_number_raw is not None:
                            try:
                                page_number = int(float(page_number_raw))
                            except Exception:
                                page_number = str(page_number_raw).strip()
                        
                        joining_amt = 0.0
                        days180_amt = 0.0
                        other_amt = 0.0
                        
                        stage_idx_val = cls.get_column_value(row, ['billing stage', 'stage', 'billing_stage'])
                        if stage_idx_val:
                            stage_val = str(stage_idx_val).strip().lower()
                            if "join" in stage_val:
                                joining_amt = amount
                            elif "six" in stage_val or "180" in stage_val or "month" in stage_val:
                                days180_amt = amount
                            else:
                                joining_amt = amount
                        else:
                            legacy_joining = cls.get_column_value(row, ['joining', 'joining payment', 'joining reimbursement', 'joining_amount'])
                            legacy_180 = cls.get_column_value(row, ['180 days', '180 days payment', '180 days reimbursement', '180_days_amount'])
                            
                            if legacy_joining is not None or legacy_180 is not None:
                                joining_amt = WorkbookParser.parse_float(legacy_joining)
                                days180_amt = WorkbookParser.parse_float(legacy_180)
                                other_amt = WorkbookParser.parse_float(cls.get_column_value(row, ['other', 'uniform', 'shirt', 'jeans', 'excess']))
                            else:
                                ref_doj = joining_date or (trainee.doj if trainee else None)
                                ref_dist = distribution_date or parent_invoice.invoice_date
                                
                                if ref_doj and ref_dist:
                                    delta_days = (ref_dist - ref_doj).days
                                    if delta_days >= 180:
                                        days180_amt = amount
                                    else:
                                        joining_amt = amount
                                else:
                                    joining_amt = amount
                                    
                        parsed_pair = cls.parse_pair(pair)
                        shirt_qty = parsed_pair["shirt_count"]
                        jean_qty = parsed_pair["jeans_count"]
                        pair_count = parsed_pair["pair_count"]
                        
                        if not shirt_qty:
                            shirt_qty = WorkbookParser.parse_float(cls.get_column_value(row, ['shirt quantity', 'shirt qty', 'shirt_quantity', 'shirt_qty', 'shirt']) or 0.0)
                        if not jean_qty:
                            jean_qty = WorkbookParser.parse_float(cls.get_column_value(row, ['jean quantity', 'jean qty', 'jean_quantity', 'jean_qty', 'jeans quantity', 'jeans qty', 'jeans']) or 0.0)
                        if not pair_count:
                            pair_count = max(shirt_qty, jean_qty)
                        
                        raw_row_data = {
                            "ticket_number": r_ticket,
                            "ticket number": r_ticket,
                            "ticket no": r_ticket,
                            "trainee_id": resolved_trainee_id or trainee_id,
                            "trainee id": resolved_trainee_id or trainee_id,
                            "joining_date": joining_date.strftime("%Y-%m-%d") if joining_date else "",
                            "batch": batch,
                            "candidate_name": billed_name,
                            "pair": pair,
                            "amount": amount,
                            "distribution_date": distribution_date.strftime("%Y-%m-%d") if distribution_date else "",
                            "page_number": str(page_number) if page_number is not None else "",
                            "shirt_quantity": shirt_qty,
                            "jean_quantity": jean_qty,
                            "pair_count": pair_count,
                            "jeans_count": jean_qty,
                            "shirt_count": shirt_qty,
                            "sheet_name": current_sheet
                        }
                        
                        for k, v in row.items():
                            if not k.startswith('_') and k not in raw_row_data:
                                raw_row_data[k] = str(v) if v is not None else ""
                                
                        invoice_item = InvoiceItem(
                            invoice_id=parent_invoice.invoice_id,
                            ticket_number=r_ticket,
                            candidate_name=billed_name or (trainee_name if exists_in_master else f"Unknown ({trainee_id or r_ticket})"),
                            joining_date=joining_date,
                            batch=batch,
                            pair=pair,
                            jeans_count=int(jean_qty),
                            shirt_count=int(shirt_qty),
                            claimed_amount=amount,
                            approved_amount=0.0,
                            rejected_amount=0.0,
                            distribution_date=distribution_date,
                            page_number=int(page_number) if isinstance(page_number, int) else None,
                            status="PENDING",
                            reason=None,
                            validation_summary=None,
                            
                            # Legacy compatibility columns
                            invoice_number=parent_invoice.invoice_number,
                            invoice_date=parent_invoice.invoice_date,
                            trainee_id=resolved_trainee_id,
                            billed_name=billed_name or (trainee_name if exists_in_master else f"Unknown ({trainee_id or r_ticket})"),
                            billed_joining_amount=joining_amt,
                            billed_180_days_amount=days180_amt,
                            billed_other_amount=other_amt,
                            billed_total_amount=amount,
                            approved_joining_amount=0.0,
                            approved_180_days_amount=0.0,
                            approved_total_amount=0.0,
                            file_name=file_name,
                            uploaded_at=parent_invoice.uploaded_at,
                            extra_data=raw_row_data
                        )
                        
                        db.add(invoice_item)
                        success_count += 1
                        sheet_total_amount += amount
                    except Exception as e:
                        skipped_count += 1
                        error_count += 1
                        errors.append(f"Sheet '{current_sheet}', Row {row_num}: {str(e)}")
                
                db.flush()
            
            try:
                for i in range(0, len(sheet["rows"]), BATCH_SIZE):
                    process_batch(sheet["rows"][i:i+BATCH_SIZE], sheet_name, invoice)
                invoice.total_amount = sheet_total_amount
                db.commit()
            except Exception as e:
                failed_sheets.append(sheet_name)
                error_count += 1
                errors.append(f"Failed to process sheet '{sheet_name}': {str(e)}")
                db.rollback()
                
        if not sheets_processed:
            raise ValueError("No sheets with required columns found.")
            
        total_duration = time.time() - start_time
        
        upload_status = "SUCCESS"
        if failed_sheets:
            upload_status = "PARTIAL" if sheets_processed else "FAILED"

        # Log upload history record
        cls._save_upload_history(
            db=db,
            upload_id=current_upload_id,
            file_name=file_name,
            file_hash=file_hash,
            file_size=file_size,
            upload_type="INVOICE",
            uploaded_by=operator,
            processing_time=total_duration,
            status=upload_status,
            is_duplicate=is_duplicate,
            stats=wb_stats,
            state={
                "rows_processed": success_count + skipped_count,
                "created_count": success_count,
                "updated_count": 0,
                "rows_no_change": 0,
                "skip_count": skipped_count - error_count,
                "error_count": error_count,
                "rows_rehired": 0,
                "rows_inactive": 0
            },
            employee_sheets=[],
            separation_sheets=[],
            invoice_sheets=sheets_processed,
            remarks=duplicate_warning
        )
        
        AuditLogRepository.add_log(
            db=db,
            action="IMPORT_INVOICE",
            module="INVOICE_UPLOAD",
            details=f"Invoice(s): {first_inv_num}. Billed: {success_count}, Skipped: {skipped_count}. Duration: {total_duration:.2f}s",
            operator=operator,
            workbook=file_name,
            sheet=", ".join(sheets_processed),
            rows_count=success_count + skipped_count,
            duration=total_duration,
            inserted=success_count,
            updated=0,
            failed=error_count,
            warnings=len(warnings),
            errors=error_count,
            before_state=None,
            after_state=None,
            invoice_number=first_inv_num,
            upload_id=current_upload_id
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
            "upload_id": current_upload_id,
            "is_duplicate": is_duplicate,
            
            # original keys for compatibility
            "invoice_number": first_inv_num,
            "invoice_date": first_inv_date,
            "success_count": success_count,
            "skipped_count": skipped_count,
            "errors": errors,
            "total_records": success_count + skipped_count,
            "records_imported": success_count
        }

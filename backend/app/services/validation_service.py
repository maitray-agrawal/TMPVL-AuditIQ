import os
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.repositories.repositories import (
    InvoiceRepository, 
    TraineeRepository, 
    ValidationRepository,
    AuditLogRepository
)
from backend.app.models.models import Trainee, PaymentLedger, InvoiceRecord, ValidationResult
from backend.app.core.json_util import make_json_serializable

# Import new rules
from backend.app.services.rules import (
    RuleTraineeNotFound,
    RuleBlockedEmployee,
    RuleDuplicateBilling,
    RuleDuplicateTicket,
    RuleDuplicateAadhaar,
    Rule30Days,
    Rule180Days,
    RuleJoiningLimit,
    RuleAnnualLimit,
    RuleKitLimit,
    RuleSeparationChecks,
    RuleMultipleSubmissions,
    RuleAmountMismatch,
    RuleInactiveEmployee,
    RuleMetadataMismatch,
    RuleChronology,
    RuleCrossInvoice
)

# For backward compatibility with existing tests that import these classes from validation_service
class TraineeNotFoundRule:
    def evaluate(self, record, trainee, history, config, state, app_joining, app_180):
        rule = RuleTraineeNotFound()
        res = rule.evaluate(record, trainee, history, config, state, app_joining, app_180)
        results_list = []
        if not res.passed and res.severity:
            results_list.append({
                "rule_name": rule.name,
                "status": res.severity,
                "message": res.reason
            })
        return res.approved_joining, res.approved_180, results_list, res.stop_processing

class BlockedTraineeRule:
    def evaluate(self, record, trainee, history, config, state, app_joining, app_180):
        rule = RuleBlockedEmployee()
        res = rule.evaluate(record, trainee, history, config, state, app_joining, app_180)
        results_list = []
        if not res.passed and res.severity:
            results_list.append({
                "rule_name": rule.name,
                "status": res.severity,
                "message": res.reason
            })
        return res.approved_joining, res.approved_180, results_list, res.stop_processing

class ExcessItemsIgnoredRule:
    def evaluate(self, record, trainee, history, config, state, app_joining, app_180):
        rule = RuleKitLimit()
        res = rule.evaluate(record, trainee, history, config, state, app_joining, app_180)
        results_list = []
        if not res.passed and res.severity:
            results_list.append({
                "rule_name": rule.name,
                "status": res.severity,
                "message": res.reason
            })
        return res.approved_joining, res.approved_180, results_list, res.stop_processing

class ValidationService:
    @classmethod
    def validate_invoice(cls, db: Session, invoice_number: str) -> Dict[str, Any]:
        """Runs the validation engine and fraud detection engine on an imported invoice."""
        import time
        start_time = time.time()
        records = InvoiceRepository.get_by_invoice_number(db, invoice_number)
        if not records:
            raise ValueError(f"Invoice '{invoice_number}' not found.")

        # Capture before state of validation results for this invoice
        record_ids = [r.id for r in records]
        existing_val_results = db.query(ValidationResult).filter(ValidationResult.invoice_record_id.in_(record_ids)).all() if record_ids else []
        validation_before_state = {
            "validation_results": [
                {
                    "invoice_record_id": v.invoice_record_id,
                    "trainee_id": v.trainee_id,
                    "rule_name": v.rule_name,
                    "status": v.status,
                    "message": v.message,
                    "reason_code": v.reason_code,
                    "recommended_action": v.recommended_action,
                }
                for v in existing_val_results
            ]
        }
        validation_after_state = []

        # Clear existing validation results for this invoice
        ValidationRepository.clear_for_invoice_number(db, invoice_number)

        # Load dynamic settings configs
        config = {
            "joining_payment_max": 1200.0,
            "days180_payment_max": 600.0,
            "max_payable_per_trainee": 1800.0,
            "min_days_reimbursement": 30
        }

        from backend.app.core.config import BASE_DIR
        settings_paths = [
            (BASE_DIR / "settings_config.json").as_posix()
        ]
        for path in settings_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        config.update(json.load(f))
                    break
                except Exception:
                    pass

        fraud_count = 0
        error_count = 0
        warning_count = 0
        success_count = 0

        # Keep track of trainees processed in this invoice to detect duplicates
        seen_trainees_joining = set()
        seen_trainees_180 = set()
        seen_tickets = {}
        seen_aadhaars = {}

        # OPTIMIZATION: Bulk fetch all trainee records and ledger histories
        trainee_ids = list({r.trainee_id for r in records if r.trainee_id})
        
        trainees = db.query(Trainee).filter(Trainee.id.in_(trainee_ids)).all() if trainee_ids else []
        trainees_map = {t.id: t for t in trainees}

        ledger_entries = db.query(PaymentLedger).filter(PaymentLedger.trainee_id.in_(trainee_ids)).all() if trainee_ids else []
        ledger_map = {}
        for entry in ledger_entries:
            ledger_map.setdefault(entry.trainee_id, []).append(entry)

        # Optimize ticket and Aadhaar duplicate database lookups in a single batch
        tickets_in_invoice = [t.ticket_number for t in trainees if t.ticket_number]
        aadhaars_in_invoice = [t.aadhaar for t in trainees if t.aadhaar]

        db_tickets = {}
        if tickets_in_invoice:
            res_tickets = db.query(Trainee.id, Trainee.ticket_number).filter(
                Trainee.ticket_number.in_(tickets_in_invoice)
            ).all()
            db_tickets = {t_num: t_id for t_id, t_num in res_tickets}

        db_aadhaars = {}
        if aadhaars_in_invoice:
            res_aadhaars = db.query(Trainee.id, Trainee.aadhaar).filter(
                Trainee.aadhaar.in_(aadhaars_in_invoice)
            ).all()
            db_aadhaars = {aadhaar: t_id for t_id, aadhaar in res_aadhaars}

        # Fetch historical items for the trainees in a single query
        historical_items_map = {}
        if trainee_ids:
            from backend.app.models.models import Invoice, InvoiceItem
            hist_items = db.query(InvoiceItem).join(Invoice).filter(
                InvoiceItem.trainee_id.in_(trainee_ids),
                Invoice.invoice_number != invoice_number,
                Invoice.status == "ACTIVE"
            ).all()
            for item in hist_items:
                historical_items_map.setdefault(item.trainee_id, []).append(item)

        invoice_history_map = {}
        if trainee_ids:
            other_invoices = db.query(InvoiceRecord.trainee_id, InvoiceRecord.invoice_number, InvoiceRecord.invoice_date).filter(
                InvoiceRecord.trainee_id.in_(trainee_ids),
                InvoiceRecord.invoice_number != invoice_number
            ).all()
            for r_t_id, r_inv_num, r_inv_date in other_invoices:
                if r_t_id:
                    t = trainees_map.get(r_t_id)
                    if t and t.doj and r_inv_date and r_inv_date < t.doj:
                        continue
                    invoice_history_map.setdefault(r_t_id, []).append({
                        "invoice_number": r_inv_num,
                        "invoice_date": r_inv_date
                    })

        # Define pipeline rules
        rules = [
            RuleTraineeNotFound(),
            RuleBlockedEmployee(),
            RuleInactiveEmployee(),
            RuleAmountMismatch(),
            RuleDuplicateBilling(),
            RuleDuplicateTicket(),
            RuleDuplicateAadhaar(),
            RuleMultipleSubmissions(),
            RuleSeparationChecks(),
            Rule30Days(),
            Rule180Days(),
            RuleJoiningLimit(),
            RuleAnnualLimit(),
            RuleKitLimit(),
            RuleMetadataMismatch(),
            RuleChronology(),
            RuleCrossInvoice()
        ]

        for record in records:
            trainee_id = record.trainee_id
            trainee = trainees_map.get(trainee_id) if trainee_id else None
            history = ledger_map.get(trainee_id, []) if trainee_id else []
            if trainee and trainee.doj:
                history = [h for h in history if h.payment_date >= trainee.doj]

            # Reset approved amounts to billed amounts initially
            app_joining = record.billed_joining_amount
            app_180 = record.billed_180_days_amount
            record_flags = []

            state = {
                "seen_trainees_joining": seen_trainees_joining,
                "seen_trainees_180": seen_trainees_180,
                "seen_tickets": seen_tickets,
                "seen_aadhaars": seen_aadhaars,
                "db_tickets": db_tickets,
                "db_aadhaars": db_aadhaars,
                "invoice_history_map": invoice_history_map,
                "historical_items_map": historical_items_map,
                "record_results": [],
                "block_trainee_reason": None
            }

            for rule in rules:
                rule_result = rule.evaluate(
                    record=record,
                    trainee=trainee,
                    history=history,
                    config=config,
                    state=state,
                    current_joining=app_joining,
                    current_180=app_180
                )
                
                # Update current approved amounts
                app_joining = rule_result.approved_joining
                app_180 = rule_result.approved_180

                # Process rule failures/warnings
                all_rule_failures = []
                if rule_result.failures:
                    all_rule_failures.extend(rule_result.failures)
                elif not rule_result.passed and rule_result.severity:
                    all_rule_failures.append({
                        "rule_name": state.get("custom_rule_name", rule.name),
                        "status": rule_result.severity,
                        "message": rule_result.reason,
                        "reason_code": None,
                        "recommended_action": None
                    })
                
                # Reset custom rule name if any
                state.pop("custom_rule_name", None)

                for fail in all_rule_failures:
                    res = ValidationRepository.add_result(
                        db=db,
                        invoice_record_id=record.id,
                        trainee_id=trainee_id if trainee else None,
                        rule_name=fail["rule_name"],
                        status=fail["status"],
                        message=fail["message"],
                        reason_code=fail.get("reason_code"),
                        recommended_action=fail.get("recommended_action"),
                        commit=False
                    )
                    validation_after_state.append({
                        "invoice_record_id": record.id,
                        "trainee_id": trainee_id if trainee else None,
                        "rule_name": fail["rule_name"],
                        "status": fail["status"],
                        "message": fail["message"],
                        "reason_code": fail.get("reason_code"),
                        "recommended_action": fail.get("recommended_action"),
                    })
                    record_flags.append(res)
                    state["record_results"].append(fail)

                if rule_result.stop_processing:
                    break

            # Block trainee if flag set
            if state["block_trainee_reason"] and trainee_id:
                TraineeRepository.block_trainee(db, trainee_id, state["block_trainee_reason"], commit=False)

            # Calculate Fraud Score (0-100)
            fraud_score = 0.0
            critical_rules = ["RuleTraineeNotFound", "RuleBlockedEmployee", "RuleSeparationChecks", "RuleInactiveEmployee", "Inactive Employee Billing", "Distribution Date Before DOJ", "Future Distribution Date", "Repeated Monthly Billing", "Duplicate Distribution Date", "Duplicate Kit Claim"]
            high_rules = ["RuleAnnualLimit", "RuleJoiningLimit", "Rule180Days"]
            medium_rules = ["RuleAmountMismatch", "Name Mismatch"]
            low_rules = ["RuleDuplicateBilling", "RuleDuplicateTicket", "RuleDuplicateAadhaar", "RuleMultipleSubmissions", "Rule30Days", "RuleKitLimit", "Batch Mismatch", "Joining Date Mismatch"]

            for fail in state["record_results"]:
                r_name = fail["rule_name"]
                status = fail["status"]
                
                if status == "FRAUD":
                    fraud_score += 40
                elif status == "ERROR":
                    fraud_score += 25
                elif status == "WARNING":
                    fraud_score += 10
                    
                if any(cr in r_name for cr in critical_rules):
                    fraud_score += 40
                elif any(hr in r_name for hr in high_rules):
                    fraud_score += 25
                elif any(mr in r_name for mr in medium_rules):
                    fraud_score += 15
                elif any(lr in r_name for lr in low_rules):
                    fraud_score += 5
            
            fraud_score = min(100.0, fraud_score)
            
            if fraud_score <= 20:
                fraud_cat = "Low"
            elif fraud_score <= 50:
                fraud_cat = "Medium"
            elif fraud_score <= 80:
                fraud_cat = "High"
            else:
                fraud_cat = "Critical"

            record.fraud_score = fraud_score
            record.fraud_category = fraud_cat
            record.validation_summary = make_json_serializable(state["record_results"])
            record.reason = "; ".join(f["message"] for f in state["record_results"]) if state["record_results"] else None

            # Determine aggregate status for this record based on flags
            record_status = "APPROVED"
            has_fraud = any(f.status == "FRAUD" for f in record_flags)
            has_error = any(f.status == "ERROR" for f in record_flags)
            has_warning = any(f.status == "WARNING" for f in record_flags)

            if has_fraud:
                record_status = "FRAUD"
                fraud_count += 1
            elif has_error:
                record_status = "REJECTED"
                error_count += 1
            elif has_warning:
                total_billed = record.billed_total_amount
                total_approved = app_joining + app_180
                if total_approved == 0:
                    record_status = "REJECTED"
                elif total_approved < total_billed:
                    record_status = "PARTIALLY_APPROVED"
                else:
                    record_status = "APPROVED"
                warning_count += 1
            else:
                total_billed = record.billed_total_amount
                total_approved = app_joining + app_180
                if total_approved == 0:
                    record_status = "REJECTED"
                else:
                    record_status = "APPROVED"
                success_count += 1

            # Update approved amounts and status in db (commit=False for batching)
            InvoiceRepository.update_record_approved_amounts(
                db=db,
                record_id=record.id,
                approved_joining=app_joining,
                approved_180=app_180,
                status=record_status,
                commit=False
            )

        # Bulk commit all validation updates and results
        db.commit()

        # Update parent Invoice aggregates
        from backend.app.models.models import Invoice, InvoiceItem
        parent_invoices = db.query(Invoice).filter(
            Invoice.invoice_number == invoice_number,
            Invoice.status == "ACTIVE"
        ).all()
        for parent_inv in parent_invoices:
            items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == parent_inv.invoice_id).all()
            total_app = sum(item.approved_amount for item in items)
            total_rej = sum(item.rejected_amount for item in items)
            total_fraud = sum(item.claimed_amount for item in items if item._status == "FRAUD")
            
            parent_inv.approved_amount = total_app
            parent_inv.rejected_amount = total_rej
            parent_inv.fraud_amount = total_fraud
            
        db.commit()

        total_duration = time.time() - start_time
        workbook_name = records[0].file_name if records else None
        AuditLogRepository.add_log(
            db=db,
            action="RUN_VALIDATION",
            module="VALIDATION",
            details=f"Invoice: {invoice_number}. Audited {len(records)} records. Fraud: {fraud_count}, Errors: {error_count}, Warnings: {warning_count}, Clear: {success_count}. Duration: {total_duration:.2f}s",
            operator="Admin",
            workbook=workbook_name,
            rows_count=len(records),
            duration=total_duration,
            inserted=len(validation_after_state),
            updated=0,
            failed=error_count + fraud_count,
            warnings=warning_count,
            errors=error_count + fraud_count,
            before_state=validation_before_state if validation_before_state["validation_results"] else None,
            after_state={"validation_results": validation_after_state} if validation_after_state else None,
            invoice_number=invoice_number
        )

        return {
            "invoice_number": invoice_number,
            "total_records": len(records),
            "fraud_count": fraud_count,
            "error_count": error_count,
            "warning_count": warning_count,
            "success_count": success_count
        }

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
    RuleAmountMismatch
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

        settings_paths = [
            "settings_config.json",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "settings_config.json")
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
            RuleKitLimit()
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

            # Determine aggregate status for this record based on flags
            record_status = "VALIDATED"
            has_fraud = any(f.status == "FRAUD" for f in record_flags)
            has_error = any(f.status == "ERROR" for f in record_flags)
            has_warning = any(f.status == "WARNING" for f in record_flags)

            if has_fraud:
                record_status = "EXCEPTION"
                fraud_count += 1
            elif has_error:
                record_status = "EXCEPTION"
                error_count += 1
            elif has_warning:
                record_status = "VALIDATED"
                warning_count += 1
            else:
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

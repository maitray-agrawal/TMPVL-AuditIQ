from sqlalchemy.orm import Session
import datetime
from backend.app.repositories.repositories import (
    InvoiceRepository, 
    LedgerRepository, 
    AuditLogRepository
)
from backend.app.models.models import PaymentLedger

class LedgerService:
    
    # Payment policy constants
    ANNUAL_MAXIMUM = 1800.0
    JOINING_MAX = 1200.0
    DAYS_180_MAX = 600.0
    
    @classmethod
    def get_trainee_payment_summary(cls, db: Session, trainee_id: str) -> dict:
        """Calculate current payment totals and remaining balance for a trainee."""
        prior_entries = db.query(PaymentLedger).filter(
            PaymentLedger.trainee_id == trainee_id
        ).all()
        
        total_approved = sum(e.amount_paid for e in prior_entries)
        remaining = max(0.0, cls.ANNUAL_MAXIMUM - total_approved)
        
        return {
            "total_approved": total_approved,
            "remaining_balance": remaining,
            "annual_cap": cls.ANNUAL_MAXIMUM,
            "entries_count": len(prior_entries)
        }
    
    @classmethod
    def approve_invoice_and_post_to_ledger(cls, db: Session, invoice_number: str) -> bool:
        """
        Approves all records in an invoice and posts non-zero payouts to the ledger.
        Enforces annual maximum (₹1800) per trainee.
        """
        import time
        start_time = time.time()
        records = InvoiceRepository.get_by_invoice_number(db, invoice_number)
        if not records:
            return False

        # Capture existing ledger entries before clearing for before_state
        existing_ledger = db.query(PaymentLedger).filter(PaymentLedger.invoice_number == invoice_number).all()
        ledger_before_state = {
            "ledger_entries": [
                {
                    "trainee_id": entry.trainee_id,
                    "invoice_number": entry.invoice_number,
                    "payment_type": entry.payment_type,
                    "amount_paid": entry.amount_paid,
                    "payment_date": entry.payment_date.strftime("%Y-%m-%d") if entry.payment_date else None,
                }
                for entry in existing_ledger
            ]
        }
        ledger_after_state = []

        # First, clear any existing ledger entries for this invoice to prevent duplicates
        LedgerRepository.delete_by_invoice_number(db, invoice_number, commit=False)

        post_count = 0
        total_payout = 0.0
        audit_details = []

        for r in records:
            # Skip posting to ledger if the item is FRAUD or REJECTED
            if r._status in ("FRAUD", "REJECTED", "EXCEPTION"):
                continue
                
            if r._status == "VALIDATED":
                r.status = "APPROVED"

            # Get current payment summary for trainee
            payment_summary = cls.get_trainee_payment_summary(db, r.trainee_id)
            trainee_running_total = payment_summary["total_approved"]
            remaining_balance = payment_summary["remaining_balance"]

            # Post joining payout if approved and within limits
            if r.approved_joining_amount > 0.0:
                # Enforce annual cap: don't pay more than remaining balance
                joining_to_post = min(r.approved_joining_amount, remaining_balance)
                
                if joining_to_post > 0:
                    rejected_joining = max(0.0, r.billed_joining_amount - joining_to_post)
                    trainee_running_total += joining_to_post
                    remaining_balance = max(0.0, cls.ANNUAL_MAXIMUM - trainee_running_total)
                    
                    extra_data = {
                        "invoice_month": r.invoice_date.strftime("%B %Y") if r.invoice_date else "",
                        "rejected": rejected_joining,
                        "running_total": trainee_running_total,
                        "remaining_balance": remaining_balance
                    }

                    LedgerRepository.add_entry(
                        db=db,
                        trainee_id=r.trainee_id,
                        invoice_number=invoice_number,
                        payment_type="JOINING",
                        amount_paid=joining_to_post,
                        payment_date=r.invoice_date,
                        extra_data=extra_data,
                        commit=False
                    )
                    ledger_after_state.append({
                        "trainee_id": r.trainee_id,
                        "invoice_number": invoice_number,
                        "payment_type": "JOINING",
                        "amount_paid": joining_to_post,
                        "payment_date": r.invoice_date.strftime("%Y-%m-%d") if r.invoice_date else None,
                    })
                    post_count += 1
                    total_payout += joining_to_post
                    audit_details.append(f"JOINING: ₹{joining_to_post} posted (rejected: ₹{rejected_joining}, remaining: ₹{remaining_balance})")
                else:
                    audit_details.append(f"JOINING: ₹0 posted (annual cap reached, trainee at ₹{trainee_running_total})")

            # Post 180 days payout if approved and within limits
            if r.approved_180_days_amount > 0.0:
                # Enforce annual cap: don't pay more than remaining balance
                days_180_to_post = min(r.approved_180_days_amount, remaining_balance)
                
                if days_180_to_post > 0:
                    rejected_180 = max(0.0, r.billed_180_days_amount - days_180_to_post)
                    trainee_running_total += days_180_to_post
                    remaining_balance = max(0.0, cls.ANNUAL_MAXIMUM - trainee_running_total)
                    
                    extra_data = {
                        "invoice_month": r.invoice_date.strftime("%B %Y") if r.invoice_date else "",
                        "rejected": rejected_180,
                        "running_total": trainee_running_total,
                        "remaining_balance": remaining_balance
                    }

                    LedgerRepository.add_entry(
                        db=db,
                        trainee_id=r.trainee_id,
                        invoice_number=invoice_number,
                        payment_type="180_DAYS",
                        amount_paid=days_180_to_post,
                        payment_date=r.invoice_date,
                        extra_data=extra_data,
                        commit=False
                    )
                    ledger_after_state.append({
                        "trainee_id": r.trainee_id,
                        "invoice_number": invoice_number,
                        "payment_type": "180_DAYS",
                        "amount_paid": days_180_to_post,
                        "payment_date": r.invoice_date.strftime("%Y-%m-%d") if r.invoice_date else None,
                    })
                    post_count += 1
                    total_payout += days_180_to_post
                    audit_details.append(f"180_DAYS: ₹{days_180_to_post} posted (rejected: ₹{rejected_180}, remaining: ₹{remaining_balance})")
                else:
                    audit_details.append(f"180_DAYS: ₹0 posted (annual cap reached, trainee at ₹{trainee_running_total})")

        db.commit()

        total_duration = time.time() - start_time
        workbook_name = records[0].file_name if records else None
        audit_msg = f"Approved invoice '{invoice_number}'. Posted {post_count} payout entries. Total approved: ₹{total_payout}. Details: {'; '.join(audit_details)}"
        AuditLogRepository.add_log(
            db=db,
            action="APPROVE_INVOICE",
            module="LEDGER",
            details=audit_msg,
            operator="Admin",
            workbook=workbook_name,
            rows_count=len(records),
            duration=total_duration,
            inserted=post_count,
            updated=0,
            failed=0,
            warnings=0,
            errors=0,
            before_state=ledger_before_state if ledger_before_state["ledger_entries"] else None,
            after_state={"ledger_entries": ledger_after_state} if ledger_after_state else None,
            invoice_number=invoice_number
        )

        return True

    @classmethod
    def reject_invoice(cls, db: Session, invoice_number: str) -> bool:
        """Rejects an invoice, clearing any ledger posts."""
        import time
        start_time = time.time()
        records = InvoiceRepository.get_by_invoice_number(db, invoice_number)
        if not records:
            return False

        # Capture existing ledger entries before clearing for before_state
        existing_ledger = db.query(PaymentLedger).filter(PaymentLedger.invoice_number == invoice_number).all()
        ledger_before_state = {
            "ledger_entries": [
                {
                    "trainee_id": entry.trainee_id,
                    "invoice_number": entry.invoice_number,
                    "payment_type": entry.payment_type,
                    "amount_paid": entry.amount_paid,
                    "payment_date": entry.payment_date.strftime("%Y-%m-%d") if entry.payment_date else None,
                }
                for entry in existing_ledger
            ]
        }

        for r in records:
            r.status = "REJECTED"
            r.approved_joining_amount = 0.0
            r.approved_180_days_amount = 0.0
            r.approved_total_amount = 0.0

        # Remove from ledger
        LedgerRepository.delete_by_invoice_number(db, invoice_number, commit=False)
        db.commit()

        total_duration = time.time() - start_time
        workbook_name = records[0].file_name if records else None
        AuditLogRepository.add_log(
            db=db,
            action="REJECT_INVOICE",
            module="LEDGER",
            details=f"Rejected invoice '{invoice_number}'. Cleared any ledger entries.",
            operator="Admin",
            workbook=workbook_name,
            rows_count=len(records),
            duration=total_duration,
            inserted=0,
            updated=0,
            failed=0,
            warnings=0,
            errors=0,
            before_state=ledger_before_state if ledger_before_state["ledger_entries"] else None,
            after_state=None,
            invoice_number=invoice_number
        )

        return True

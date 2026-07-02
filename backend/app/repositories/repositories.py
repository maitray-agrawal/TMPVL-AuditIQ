from typing import List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
import datetime
from backend.app.models.models import (
    Trainee,
    BDCRecord,
    SeparationRecord,
    InvoiceRecord,
    PaymentLedger,
    ValidationResult,
    AuditLog
)

class TraineeRepository:
    @staticmethod
    def get_by_id(db: Session, trainee_id: str) -> Optional[Trainee]:
        return db.query(Trainee).filter(Trainee.id == trainee_id).first()

    @staticmethod
    def get_all(
        db: Session,
        search: Optional[str] = None,
        status: Optional[str] = None,
        scheme: Optional[str] = None
    ) -> List[Trainee]:
        query = db.query(Trainee)
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                or_(Trainee.id.like(search_filter), Trainee.name.like(search_filter))
            )
        if status:
            query = query.filter(Trainee.status == status)
        if scheme:
            query = query.filter(Trainee.scheme == scheme)
        return query.order_by(Trainee.id).all()

    @staticmethod
    def count_by_status(db: Session) -> dict:
        """Return total and per-status trainee counts in a single pass."""
        all_trainees = db.query(Trainee.status).all()
        counts = {"total": 0, "ACTIVE": 0, "BLOCKED": 0, "SEPARATED": 0}
        for (status,) in all_trainees:
            counts["total"] += 1
            if status in counts:
                counts[status] += 1
        return counts

    @staticmethod
    def create_or_update_from_bdc(
        db: Session,
        trainee_id: str,
        name: str,
        doj: datetime.date,
        scheme: str,
        commit: bool = True
    ) -> Trainee:
        trainee = db.query(Trainee).filter(Trainee.id == trainee_id).first()
        if trainee:
            trainee.name = name
            trainee.doj = doj
            trainee.scheme = scheme
            # If previously separated or active, we preserve that unless blocked
            if trainee.status != "BLOCKED":
                trainee.status = "ACTIVE"
        else:
            trainee = Trainee(
                id=trainee_id,
                name=name,
                doj=doj,
                scheme=scheme,
                status="ACTIVE"
            )
            db.add(trainee)
        if commit:
            db.commit()
            db.refresh(trainee)
        return trainee

    @staticmethod
    def create_or_update_from_separation(
        db: Session,
        trainee_id: str,
        dol: datetime.date,
        reason: Optional[str],
        scheme: str,
        commit: bool = True
    ) -> Optional[Trainee]:
        trainee = db.query(Trainee).filter(Trainee.id == trainee_id).first()
        if trainee:
            trainee.dol = dol
            if trainee.status != "BLOCKED":
                trainee.status = "SEPARATED"
            if commit:
                db.commit()
                db.refresh(trainee)
        return trainee

    @staticmethod
    def block_trainee(db: Session, trainee_id: str, reason: str, commit: bool = True) -> Optional[Trainee]:
        trainee = db.query(Trainee).filter(Trainee.id == trainee_id).first()
        if trainee:
            trainee.status = "BLOCKED"
            trainee.blocked_reason = reason
            if commit:
                db.commit()
                db.refresh(trainee)
        return trainee

    @staticmethod
    def unblock_trainee(db: Session, trainee_id: str, commit: bool = True) -> Optional[Trainee]:
        trainee = db.query(Trainee).filter(Trainee.id == trainee_id).first()
        if trainee:
            trainee.status = "ACTIVE"
            trainee.blocked_reason = None
            if commit:
                db.commit()
                db.refresh(trainee)
        return trainee


class InvoiceRepository:
    @staticmethod
    def get_by_id(db: Session, record_id: int) -> Optional[InvoiceRecord]:
        return db.query(InvoiceRecord).filter(InvoiceRecord.id == record_id).first()

    @staticmethod
    def get_by_invoice_number(db: Session, invoice_number: str) -> List[InvoiceRecord]:
        return db.query(InvoiceRecord).filter(InvoiceRecord.invoice_number == invoice_number).all()

    @staticmethod
    def get_unique_invoices(db: Session) -> List[dict]:
        # Fetch all columns needed in a single query
        all_records = db.query(
            InvoiceRecord.invoice_number,
            InvoiceRecord.invoice_date,
            InvoiceRecord.status,
            InvoiceRecord.file_name,
            InvoiceRecord.uploaded_at,
            InvoiceRecord.billed_total_amount,
            InvoiceRecord.approved_total_amount
        ).all()

        if not all_records:
            return []

        # Aggregate stats in memory (O(N) time complexity)
        groups = {}
        for r in all_records:
            inv_num = r.invoice_number
            if inv_num not in groups:
                groups[inv_num] = {
                    "invoice_number": inv_num,
                    "invoice_date": r.invoice_date,
                    "file_name": r.file_name,
                    "uploaded_at": r.uploaded_at,
                    "billed_amount": 0.0,
                    "approved_amount": 0.0,
                    "record_count": 0,
                    "statuses": []
                }
            g = groups[inv_num]
            g["billed_amount"] += r.billed_total_amount
            g["approved_amount"] += r.approved_total_amount
            g["record_count"] += 1
            g["statuses"].append(r.status)

        results = []
        for g in groups.values():
            statuses = g["statuses"]
            # Resolve status precedence rule:
            # EXCEPTION > PENDING > VALIDATED > APPROVED
            if "EXCEPTION" in statuses:
                status = "EXCEPTION"
            elif "PENDING" in statuses:
                status = "PENDING"
            elif "VALIDATED" in statuses:
                status = "VALIDATED"
            elif "APPROVED" in statuses:
                status = "APPROVED"
            else:
                status = "PENDING"

            results.append({
                "invoice_number": g["invoice_number"],
                "invoice_date": g["invoice_date"],
                "status": status,
                "file_name": g["file_name"],
                "uploaded_at": g["uploaded_at"],
                "billed_amount": g["billed_amount"],
                "approved_amount": g["approved_amount"],
                "record_count": g["record_count"]
            })
        return results

    @staticmethod
    def create_record(db: Session, record: InvoiceRecord, commit: bool = True) -> InvoiceRecord:
        db.add(record)
        if commit:
            db.commit()
            db.refresh(record)
        return record

    @staticmethod
    def update_record_approved_amounts(
        db: Session,
        record_id: int,
        approved_joining: float,
        approved_180: float,
        status: str,
        commit: bool = True
    ) -> Optional[InvoiceRecord]:
        record = db.query(InvoiceRecord).filter(InvoiceRecord.id == record_id).first()
        if record:
            record.approved_joining_amount = approved_joining
            record.approved_180_days_amount = approved_180
            record.approved_total_amount = approved_joining + approved_180
            record.status = status
            if commit:
                db.commit()
                db.refresh(record)
        return record

    @staticmethod
    def delete_by_invoice_number(db: Session, invoice_number: str, commit: bool = True) -> bool:
        records = db.query(InvoiceRecord).filter(InvoiceRecord.invoice_number == invoice_number).all()
        if not records:
            return False
        
        # Delete related validation results
        record_ids = [r.id for r in records]
        db.query(ValidationResult).filter(ValidationResult.invoice_record_id.in_(record_ids)).delete(synchronize_session=False)
        
        # Delete invoice records
        db.query(InvoiceRecord).filter(InvoiceRecord.invoice_number == invoice_number).delete(synchronize_session=False)
        if commit:
            db.commit()
        return True


class LedgerRepository:
    @staticmethod
    def get_by_trainee_id(db: Session, trainee_id: str) -> List[PaymentLedger]:
        return db.query(PaymentLedger).filter(PaymentLedger.trainee_id == trainee_id).order_by(PaymentLedger.payment_date).all()

    @staticmethod
    def add_entry(
        db: Session,
        trainee_id: str,
        invoice_number: str,
        payment_type: str,
        amount_paid: float,
        payment_date: datetime.date,
        extra_data: Optional[dict] = None,
        commit: bool = True
    ) -> PaymentLedger:
        entry = PaymentLedger(
            trainee_id=trainee_id,
            invoice_number=invoice_number,
            payment_type=payment_type,
            amount_paid=amount_paid,
            payment_date=payment_date,
            extra_data=extra_data
        )
        db.add(entry)
        if commit:
            db.commit()
            db.refresh(entry)
        return entry

    @staticmethod
    def get_all_entries(db: Session) -> List[PaymentLedger]:
        return db.query(PaymentLedger).order_by(desc(PaymentLedger.payment_date)).all()

    @staticmethod
    def delete_by_invoice_number(db: Session, invoice_number: str, commit: bool = True) -> None:
        db.query(PaymentLedger).filter(PaymentLedger.invoice_number == invoice_number).delete(synchronize_session=False)
        if commit:
            db.commit()


class ValidationRepository:
    @staticmethod
    def get_by_invoice_record(db: Session, invoice_record_id: int) -> List[ValidationResult]:
        return db.query(ValidationResult).filter(ValidationResult.invoice_record_id == invoice_record_id).all()

    @staticmethod
    def get_by_invoice_number(db: Session, invoice_number: str) -> List[ValidationResult]:
        return db.query(ValidationResult).join(InvoiceRecord).filter(InvoiceRecord.invoice_number == invoice_number).all()

    @staticmethod
    def get_by_trainee_id(db: Session, trainee_id: str) -> List[ValidationResult]:
        return (
            db.query(ValidationResult)
            .filter(ValidationResult.trainee_id == trainee_id)
            .order_by(ValidationResult.created_at.desc())
            .all()
        )

    @staticmethod
    def count_by_statuses(db: Session, statuses: List[str]) -> int:
        """Count validation results matching any of the given statuses."""
        return db.query(ValidationResult).filter(ValidationResult.status.in_(statuses)).count()

    @staticmethod
    def add_result(
        db: Session,
        invoice_record_id: Optional[int],
        trainee_id: Optional[str],
        rule_name: str,
        status: str,
        message: str,
        reason_code: Optional[str] = None,
        recommended_action: Optional[str] = None,
        commit: bool = True
    ) -> ValidationResult:
        res = ValidationResult(
            invoice_record_id=invoice_record_id,
            trainee_id=trainee_id,
            rule_name=rule_name,
            status=status,
            message=message,
            reason_code=reason_code,
            recommended_action=recommended_action
        )
        db.add(res)
        if commit:
            db.commit()
            db.refresh(res)
        return res

    @staticmethod
    def clear_for_invoice_number(db: Session, invoice_number: str) -> None:
        records = db.query(InvoiceRecord).filter(InvoiceRecord.invoice_number == invoice_number).all()
        record_ids = [r.id for r in records]
        if record_ids:
            db.query(ValidationResult).filter(ValidationResult.invoice_record_id.in_(record_ids)).delete(synchronize_session=False)
            db.commit()


class AuditLogRepository:
    @staticmethod
    def add_log(
        db: Session,
        action: str,
        module: str,
        details: str,
        operator: Optional[str] = None,
        workbook: Optional[str] = None,
        sheet: Optional[str] = None,
        rows_count: Optional[int] = None,
        duration: Optional[float] = None,
        inserted: Optional[int] = None,
        updated: Optional[int] = None,
        failed: Optional[int] = None,
        warnings: Optional[int] = None,
        errors: Optional[int] = None,
        before_state: Optional[dict] = None,
        after_state: Optional[dict] = None,
        employee_id: Optional[str] = None,
        invoice_number: Optional[str] = None,
        timestamp: Optional[datetime.datetime] = None
    ) -> AuditLog:
        log = AuditLog(
            action=action,
            module=module,
            details=details,
            operator=operator,
            workbook=workbook,
            sheet=sheet,
            rows_count=rows_count,
            duration=duration,
            inserted=inserted,
            updated=updated,
            failed=failed,
            warnings=warnings,
            errors=errors,
            before_state=before_state,
            after_state=after_state,
            employee_id=employee_id,
            invoice_number=invoice_number
        )
        if timestamp:
            log.timestamp = timestamp
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def get_logs(
        db: Session,
        limit: int = 100,
        offset: int = 0,
        module: Optional[str] = None,
        employee_id: Optional[str] = None,
        invoice_number: Optional[str] = None,
        workbook: Optional[str] = None,
        date_from: Optional[Any] = None,
        date_to: Optional[Any] = None,
        action: Optional[str] = None
    ) -> List[AuditLog]:
        query = db.query(AuditLog)
        if module:
            query = query.filter(AuditLog.module == module)
        if employee_id:
            query = query.filter(AuditLog.employee_id.like(f"%{employee_id}%"))
        if invoice_number:
            query = query.filter(AuditLog.invoice_number.like(f"%{invoice_number}%"))
        if workbook:
            query = query.filter(AuditLog.workbook.like(f"%{workbook}%"))
        if date_from:
            if isinstance(date_from, str):
                try:
                    date_from = datetime.datetime.strptime(date_from, "%Y-%m-%d").date()
                except ValueError:
                    pass
            if isinstance(date_from, (datetime.date, datetime.datetime)):
                query = query.filter(AuditLog.timestamp >= datetime.datetime.combine(date_from, datetime.time.min))
        if date_to:
            if isinstance(date_to, str):
                try:
                    date_to = datetime.datetime.strptime(date_to, "%Y-%m-%d").date()
                except ValueError:
                    pass
            if isinstance(date_to, (datetime.date, datetime.datetime)):
                query = query.filter(AuditLog.timestamp <= datetime.datetime.combine(date_to, datetime.time.max))
        if action:
            query = query.filter(AuditLog.action.like(f"%{action}%"))
        return query.order_by(desc(AuditLog.timestamp)).offset(offset).limit(limit).all()

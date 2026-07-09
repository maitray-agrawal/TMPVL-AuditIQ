import datetime
import uuid
from sqlalchemy import Column, String, Date, DateTime, Float, Integer, ForeignKey, JSON as SQL_JSON, TypeDecorator
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from backend.app.core.db import Base
from backend.app.core.json_util import make_json_serializable

class SafeJSON(TypeDecorator):
    impl = SQL_JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return make_json_serializable(value)

JSON = SafeJSON

class Trainee(Base):
    __tablename__ = "trainees"

    id = Column(String, primary_key=True, index=True) # Trainee ID / Emp ID
    name = Column(String, nullable=False)
    doj = Column(Date, nullable=False)
    dol = Column(Date, nullable=True)
    scheme = Column(String, nullable=False) # NAPS, B.Tech, M.Tech
    status = Column(String, default="ACTIVE", nullable=False) # ACTIVE, SEPARATED, BLOCKED, INACTIVE
    blocked_reason = Column(String, nullable=True)
    aadhaar = Column(String, nullable=True, unique=True)
    ticket_number = Column(String, nullable=True, unique=True)
    category = Column(String, nullable=True)
    batch = Column(String, nullable=True)
    shop = Column(String, nullable=True)
    current_workbook = Column(String, nullable=True)
    current_sheet = Column(String, nullable=True)
    offer_id = Column(String, nullable=True)
    mobile = Column(String, nullable=True)
    email = Column(String, nullable=True)
    _extra_data = Column("extra_data", JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    bdc_records = relationship("BDCRecord", back_populates="trainee", cascade="all, delete-orphan")
    separation_records = relationship("SeparationRecord", back_populates="trainee", cascade="all, delete-orphan")
    invoice_records = relationship("InvoiceItem", back_populates="trainee", cascade="all, delete-orphan")
    ledger_entries = relationship("PaymentLedger", back_populates="trainee", cascade="all, delete-orphan")
    validation_results = relationship("ValidationResult", back_populates="trainee", cascade="all, delete-orphan")
    lifecycles = relationship("TraineeLifecycle", back_populates="trainee", cascade="all, delete-orphan", order_by="TraineeLifecycle.id")

    @property
    def extra_data(self):
        data = self._extra_data or {}
        if not isinstance(data, dict):
            data = {}
        lc_list = []
        for i, lc in enumerate(self.lifecycles):
            lc_dict = {
                "lifecycle_number": i + 1,
                "doj": lc.joining_date.strftime("%Y-%m-%d") if lc.joining_date else None,
                "dol": lc.leaving_date.strftime("%Y-%m-%d") if lc.leaving_date else None,
                "status": lc.status,
            }
            if lc.extra_data:
                for k, v in lc.extra_data.items():
                    lc_dict[k] = v
            # Ensure required history lists exist
            for key in ["invoice_history", "payment_ledger", "validation_history"]:
                if key not in lc_dict:
                    lc_dict[key] = []
            lc_list.append(lc_dict)
        data["lifecycles"] = lc_list
        return data

    @extra_data.setter
    def extra_data(self, val):
        if isinstance(val, dict):
            val = val.copy()
            val.pop("lifecycles", None)
        self._extra_data = val

class BDCRecord(Base):
    __tablename__ = "bdc_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trainee_id = Column(String, ForeignKey("trainees.id"), nullable=False, index=True)
    doj = Column(Date, nullable=False)
    scheme = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    extra_data = Column(JSON, nullable=True)

    trainee = relationship("Trainee", back_populates="bdc_records")

class SeparationRecord(Base):
    __tablename__ = "separation_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trainee_id = Column(String, ForeignKey("trainees.id"), nullable=False, index=True)
    dol = Column(Date, nullable=False)
    reason = Column(String, nullable=True)
    file_name = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    extra_data = Column(JSON, nullable=True)

    trainee = relationship("Trainee", back_populates="separation_records")

class Invoice(Base):
    __tablename__ = "invoices"

    invoice_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    invoice_number = Column(String, nullable=False, index=True)
    invoice_date = Column(Date, nullable=False)
    billing_month = Column(String, nullable=True)
    billing_year = Column(Integer, nullable=True)
    vendor_name = Column(String, nullable=True)
    workbook_name = Column(String, nullable=True)
    sheet_name = Column(String, nullable=True)
    upload_id = Column(String, ForeignKey("upload_history.upload_id"), nullable=True, index=True)
    uploaded_by = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String, default="ACTIVE", nullable=False) # ACTIVE, CANCELLED, SUPERSEDED
    total_amount = Column(Float, default=0.0)
    approved_amount = Column(Float, default=0.0)
    rejected_amount = Column(Float, default=0.0)
    fraud_amount = Column(Float, default=0.0)
    remarks = Column(String, nullable=True)

    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    upload_history = relationship("UploadHistory", back_populates="invoices")

class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(String, ForeignKey("invoices.invoice_id"), nullable=True, index=True)
    ticket_number = Column(String, nullable=True, index=True)
    candidate_name = Column(String, nullable=True)
    joining_date = Column(Date, nullable=True)
    batch = Column(String, nullable=True)
    pair = Column(String, nullable=True)
    jeans_count = Column(Integer, default=0)
    shirt_count = Column(Integer, default=0)
    claimed_amount = Column(Float, default=0.0)
    approved_amount = Column(Float, default=0.0)
    rejected_amount = Column(Float, default=0.0)
    distribution_date = Column(Date, nullable=True)
    page_number = Column(Integer, nullable=True)
    _status = Column("status", String, default="PENDING", nullable=False) # APPROVED, PARTIALLY_APPROVED, REJECTED, FRAUD, PENDING
    reason = Column(String, nullable=True)
    validation_summary = Column(JSON, nullable=True)

    @hybrid_property
    def status(self):
        if self._status in ("APPROVED", "PARTIALLY_APPROVED", "VALIDATED"):
            return "VALIDATED"
        elif self._status in ("REJECTED", "FRAUD", "EXCEPTION"):
            return "EXCEPTION"
        return self._status

    @status.setter
    def status(self, val):
        self._status = val

    @status.expression
    def status(cls):
        from sqlalchemy import case
        return case(
            (cls._status.in_(["APPROVED", "PARTIALLY_APPROVED", "VALIDATED"]), "VALIDATED"),
            (cls._status.in_(["REJECTED", "FRAUD", "EXCEPTION"]), "EXCEPTION"),
            else_=cls._status
        )
    
    fraud_score = Column(Float, default=0.0)
    fraud_category = Column(String, default="Low") # Low, Medium, High, Critical

    # Legacy compatibility fields
    invoice_number = Column(String, nullable=True, index=True)
    invoice_date = Column(Date, nullable=True)
    trainee_id = Column(String, ForeignKey("trainees.id"), nullable=True, index=True)
    billed_name = Column(String, nullable=True)
    billed_joining_amount = Column(Float, default=0.0)
    billed_180_days_amount = Column(Float, default=0.0)
    billed_other_amount = Column(Float, default=0.0)
    billed_total_amount = Column(Float, default=0.0)
    approved_joining_amount = Column(Float, default=0.0)
    approved_180_days_amount = Column(Float, default=0.0)
    approved_total_amount = Column(Float, default=0.0)
    file_name = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    extra_data = Column(JSON, nullable=True)

    invoice = relationship("Invoice", back_populates="items")
    trainee = relationship("Trainee", back_populates="invoice_records")
    validation_results = relationship("ValidationResult", back_populates="invoice_record", cascade="all, delete-orphan")

InvoiceRecord = InvoiceItem

class PaymentLedger(Base):
    __tablename__ = "payment_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trainee_id = Column(String, ForeignKey("trainees.id"), nullable=False, index=True)
    invoice_number = Column(String, nullable=False, index=True)
    payment_type = Column(String, nullable=False) # JOINING, 180_DAYS
    amount_paid = Column(Float, nullable=False)
    payment_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    extra_data = Column(JSON, nullable=True)

    trainee = relationship("Trainee", back_populates="ledger_entries")

class ValidationResult(Base):
    __tablename__ = "validation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_record_id = Column(Integer, ForeignKey("invoice_items.id"), nullable=True, index=True)
    trainee_id = Column(String, ForeignKey("trainees.id"), nullable=True, index=True)
    rule_name = Column(String, nullable=False)
    status = Column(String, nullable=False) # WARNING, ERROR, FRAUD
    message = Column(String, nullable=False)
    reason_code = Column(String, nullable=True)
    recommended_action = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    trainee = relationship("Trainee", back_populates="validation_results")
    invoice_record = relationship("InvoiceItem", back_populates="validation_results")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    action = Column(String, nullable=False, index=True)
    module = Column(String, nullable=False, index=True) # DASHBOARD, UPLOAD, VALIDATION, LEDGER, REPORTS
    details = Column(String, nullable=False)
    operator = Column(String, nullable=True)
    workbook = Column(String, nullable=True, index=True)
    sheet = Column(String, nullable=True)
    rows_count = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True)
    inserted = Column(Integer, nullable=True)
    updated = Column(Integer, nullable=True)
    failed = Column(Integer, nullable=True)
    warnings = Column(Integer, nullable=True)
    errors = Column(Integer, nullable=True)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    employee_id = Column(String, nullable=True, index=True)
    invoice_number = Column(String, nullable=True, index=True)
    upload_id = Column(String, ForeignKey("upload_history.upload_id"), nullable=True, index=True)

    upload_history = relationship("UploadHistory", back_populates="audit_logs")



class UploadHistory(Base):
    __tablename__ = "upload_history"

    upload_id = Column(String, primary_key=True, index=True)
    file_name = Column(String, nullable=False)
    file_hash = Column(String, index=True, nullable=False)
    file_size = Column(Integer, nullable=False)
    upload_type = Column(String, nullable=False) # FULL_SYNC, INCREMENTAL, SEPARATION, INVOICE, MIXED, UNKNOWN
    uploaded_by = Column(String, nullable=False)
    upload_time = Column(DateTime, default=datetime.datetime.utcnow)
    processing_time = Column(Float, nullable=False)
    status = Column(String, nullable=False) # SUCCESS, FAILED, PARTIAL, DUPLICATE
    is_duplicate = Column(JSON, default=False) # JSON or Boolean (let's use Integer/Boolean via Column(Float/JSON/etc.), wait: Column(JSON/Boolean) - Boolean is supported. Let's use Column(Integer) or Column(JSON) or Column(JSON) but wait, SQLITE supports Boolean. Let's use Column(JSON, default=False) since JSON can hold boolean values, or boolean.)
    is_duplicate = Column(JSON, default=False) # Let's use JSON as specified in the prompt/v2.0 fields
    workbook_version = Column(String, nullable=True)
    parser_version = Column(String, default="2.0.0")
    application_version = Column(String, default="2.0.0")
    sheet_count = Column(Integer, default=0)
    visible_sheet_count = Column(Integer, default=0)
    hidden_sheet_count = Column(Integer, default=0)
    rows_processed = Column(Integer, default=0)
    rows_inserted = Column(Integer, default=0)
    rows_updated = Column(Integer, default=0)
    rows_no_change = Column(Integer, default=0)
    rows_skipped = Column(Integer, default=0)
    rows_failed = Column(Integer, default=0)
    rows_rehired = Column(Integer, default=0)
    rows_inactive = Column(Integer, default=0)
    employee_sheets = Column(JSON, nullable=True)
    separation_sheets = Column(JSON, nullable=True)
    invoice_sheets = Column(JSON, nullable=True)
    remarks = Column(String, nullable=True)

    audit_logs = relationship("AuditLog", back_populates="upload_history", cascade="all, delete-orphan")
    lifecycles = relationship("TraineeLifecycle", back_populates="upload_history")
    invoices = relationship("Invoice", back_populates="upload_history", cascade="all, delete-orphan")

class TraineeLifecycle(Base):
    __tablename__ = "trainee_lifecycles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trainee_id = Column(String, ForeignKey("trainees.id"), index=True, nullable=False)
    joining_date = Column(Date, nullable=False)
    leaving_date = Column(Date, nullable=True)
    status = Column(String, nullable=False)
    upload_id = Column(String, ForeignKey("upload_history.upload_id"), nullable=True)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    trainee = relationship("Trainee", back_populates="lifecycles")
    upload_history = relationship("UploadHistory", back_populates="lifecycles")


import datetime
from sqlalchemy import Column, String, Date, DateTime, Float, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.app.core.db import Base

class Trainee(Base):
    __tablename__ = "trainees"

    id = Column(String, primary_key=True, index=True) # Trainee ID / Emp ID
    name = Column(String, nullable=False)
    doj = Column(Date, nullable=False)
    dol = Column(Date, nullable=True)
    scheme = Column(String, nullable=False) # NAPS, B.Tech, M.Tech
    status = Column(String, default="ACTIVE", nullable=False) # ACTIVE, SEPARATED, BLOCKED
    blocked_reason = Column(String, nullable=True)
    aadhaar = Column(String, nullable=True, unique=True)
    ticket_number = Column(String, nullable=True, unique=True)
    category = Column(String, nullable=True)
    batch = Column(String, nullable=True)
    shop = Column(String, nullable=True)
    current_workbook = Column(String, nullable=True)
    current_sheet = Column(String, nullable=True)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    bdc_records = relationship("BDCRecord", back_populates="trainee", cascade="all, delete-orphan")
    separation_records = relationship("SeparationRecord", back_populates="trainee", cascade="all, delete-orphan")
    invoice_records = relationship("InvoiceRecord", back_populates="trainee", cascade="all, delete-orphan")
    ledger_entries = relationship("PaymentLedger", back_populates="trainee", cascade="all, delete-orphan")
    validation_results = relationship("ValidationResult", back_populates="trainee", cascade="all, delete-orphan")

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

class InvoiceRecord(Base):
    __tablename__ = "invoice_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_number = Column(String, nullable=False, index=True)
    invoice_date = Column(Date, nullable=False)
    trainee_id = Column(String, ForeignKey("trainees.id"), nullable=True, index=True)
    billed_name = Column(String, nullable=True)
    billed_joining_amount = Column(Float, default=0.0)
    billed_180_days_amount = Column(Float, default=0.0)
    billed_other_amount = Column(Float, default=0.0)
    billed_total_amount = Column(Float, default=0.0)
    approved_joining_amount = Column(Float, default=0.0)
    approved_180_days_amount = Column(Float, default=0.0)
    approved_total_amount = Column(Float, default=0.0)
    status = Column(String, default="PENDING", nullable=False) # PENDING, VALIDATED, APPROVED, REJECTED, EXCEPTION
    file_name = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    extra_data = Column(JSON, nullable=True)

    trainee = relationship("Trainee", back_populates="invoice_records")
    validation_results = relationship("ValidationResult", back_populates="invoice_record", cascade="all, delete-orphan")

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
    invoice_record_id = Column(Integer, ForeignKey("invoice_records.id"), nullable=True, index=True)
    trainee_id = Column(String, ForeignKey("trainees.id"), nullable=True, index=True)
    rule_name = Column(String, nullable=False)
    status = Column(String, nullable=False) # WARNING, ERROR, FRAUD
    message = Column(String, nullable=False)
    reason_code = Column(String, nullable=True)
    recommended_action = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    trainee = relationship("Trainee", back_populates="validation_results")
    invoice_record = relationship("InvoiceRecord", back_populates="validation_results")

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


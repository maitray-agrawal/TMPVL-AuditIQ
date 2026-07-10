import os
import datetime
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.db import engine, Base
from backend.app.api.endpoints import router

# Automatically create all SQLite database tables on startup
Base.metadata.create_all(bind=engine)

def upgrade_db_schema(db_engine):
    from sqlalchemy import inspect, text
    import uuid
    inspector = inspect(db_engine)
    
    # Upgrade trainees table
    trainees_cols = [col['name'] for col in inspector.get_columns('trainees')]
    with db_engine.begin() as conn:
        if 'category' not in trainees_cols:
            conn.execute(text("ALTER TABLE trainees ADD COLUMN category TEXT"))
        if 'batch' not in trainees_cols:
            conn.execute(text("ALTER TABLE trainees ADD COLUMN batch TEXT"))
        if 'shop' not in trainees_cols:
            conn.execute(text("ALTER TABLE trainees ADD COLUMN shop TEXT"))
        if 'current_workbook' not in trainees_cols:
            conn.execute(text("ALTER TABLE trainees ADD COLUMN current_workbook TEXT"))
        if 'current_sheet' not in trainees_cols:
            conn.execute(text("ALTER TABLE trainees ADD COLUMN current_sheet TEXT"))
        if 'extra_data' not in trainees_cols:
            conn.execute(text("ALTER TABLE trainees ADD COLUMN extra_data JSON"))
        if 'offer_id' not in trainees_cols:
            conn.execute(text("ALTER TABLE trainees ADD COLUMN offer_id TEXT"))
        if 'mobile' not in trainees_cols:
            conn.execute(text("ALTER TABLE trainees ADD COLUMN mobile TEXT"))
        if 'email' not in trainees_cols:
            conn.execute(text("ALTER TABLE trainees ADD COLUMN email TEXT"))
            
    # Upgrade payment_ledger table
    ledger_cols = [col['name'] for col in inspector.get_columns('payment_ledger')]
    with db_engine.begin() as conn:
        if 'extra_data' not in ledger_cols:
            conn.execute(text("ALTER TABLE payment_ledger ADD COLUMN extra_data JSON"))
        if 'invoice_id' not in ledger_cols:
            conn.execute(text("ALTER TABLE payment_ledger ADD COLUMN invoice_id TEXT"))
        if 'invoice_item_id' not in ledger_cols:
            conn.execute(text("ALTER TABLE payment_ledger ADD COLUMN invoice_item_id INTEGER"))

    # Upgrade validation_results table
    val_cols = [col['name'] for col in inspector.get_columns('validation_results')]
    with db_engine.begin() as conn:
        if 'reason_code' not in val_cols:
            conn.execute(text("ALTER TABLE validation_results ADD COLUMN reason_code TEXT"))
        if 'recommended_action' not in val_cols:
            conn.execute(text("ALTER TABLE validation_results ADD COLUMN recommended_action TEXT"))

    # Upgrade audit_logs table
    audit_cols = [col['name'] for col in inspector.get_columns('audit_logs')]
    audit_indexes = [idx['name'] for idx in inspector.get_indexes('audit_logs')]
    with db_engine.begin() as conn:
        for col_name, col_type in [
            ('operator', 'TEXT'), ('workbook', 'TEXT'), ('sheet', 'TEXT'),
            ('rows_count', 'INTEGER'), ('duration', 'REAL'), ('inserted', 'INTEGER'),
            ('updated', 'INTEGER'), ('failed', 'INTEGER'), ('warnings', 'INTEGER'),
            ('errors', 'INTEGER'), ('before_state', 'JSON'), ('after_state', 'JSON'),
            ('employee_id', 'TEXT'), ('invoice_number', 'TEXT'), ('upload_id', 'TEXT'),
            ('invoice_id', 'TEXT')
        ]:
            if col_name not in audit_cols:
                conn.execute(text(f"ALTER TABLE audit_logs ADD COLUMN {col_name} {col_type}"))
        if 'ix_audit_logs_action' not in audit_indexes:
            conn.execute(text("CREATE INDEX ix_audit_logs_action ON audit_logs (action)"))

    # Upgrade trainee_lifecycles table
    try:
        lc_cols = [col['name'] for col in inspector.get_columns('trainee_lifecycles')]
        with db_engine.begin() as conn:
            if 'extra_data' not in lc_cols:
                conn.execute(text("ALTER TABLE trainee_lifecycles ADD COLUMN extra_data JSON"))
    except Exception:
        pass

    # Migrate data from invoice_records to invoices & invoice_items if needed
    try:
        if 'invoice_records' in inspector.get_table_names() and 'invoice_items' in inspector.get_table_names():
            with db_engine.begin() as conn:
                items_count = conn.execute(text("SELECT COUNT(*) FROM invoice_items")).scalar()
                records_count = conn.execute(text("SELECT COUNT(*) FROM invoice_records")).scalar()
                
                if items_count == 0 and records_count > 0:
                    print("Migrating invoice_records to new invoices/invoice_items ledger format...")
                    # Get unique invoices
                    records = conn.execute(text("SELECT * FROM invoice_records")).fetchall()
                    
                    # Columns in invoice_records:
                    # id, invoice_number, invoice_date, trainee_id, billed_name, billed_joining_amount, 
                    # billed_180_days_amount, billed_other_amount, billed_total_amount, approved_joining_amount, 
                    # approved_180_days_amount, approved_total_amount, status, file_name, uploaded_at, extra_data
                    
                    invoices_dict = {}
                    import json
                    for r in records:
                        # Find or create Invoice
                        inv_num = r.invoice_number
                        if inv_num not in invoices_dict:
                            inv_id = str(uuid.uuid4())
                            inv_date = r.invoice_date
                            # Parse billing month/year from date or filename
                            try:
                                import datetime
                                if isinstance(inv_date, str):
                                    dt = datetime.datetime.strptime(inv_date.split(' ')[0], "%Y-%m-%d")
                                elif isinstance(inv_date, (datetime.date, datetime.datetime)):
                                    dt = inv_date
                                else:
                                    dt = datetime.date.today()
                            except Exception:
                                dt = datetime.date.today()
                                
                            months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
                            billing_month = months[dt.month - 1]
                            billing_year = dt.year
                            
                            conn.execute(text("""
                                INSERT INTO invoices (invoice_id, invoice_number, invoice_date, billing_month, billing_year, 
                                                    vendor_name, workbook_name, sheet_name, upload_id, uploaded_by, 
                                                    uploaded_at, status, total_amount, approved_amount, rejected_amount, 
                                                    fraud_amount, remarks)
                                VALUES (:invoice_id, :invoice_number, :invoice_date, :billing_month, :billing_year,
                                        'Tata Projects', :workbook_name, 'Invoice', NULL, 'Admin', 
                                        :uploaded_at, 'ACTIVE', 0.0, 0.0, 0.0, 0.0, NULL)
                            """), {
                                "invoice_id": inv_id,
                                "invoice_number": inv_num,
                                "invoice_date": inv_date,
                                "billing_month": billing_month,
                                "billing_year": billing_year,
                                "workbook_name": r.file_name,
                                "uploaded_at": r.uploaded_at
                            })
                            invoices_dict[inv_num] = inv_id
                        
                        inv_id = invoices_dict[inv_num]
                        
                        # Parse extra_data for item fields
                        ext = {}
                        if r.extra_data:
                            try:
                                ext = json.loads(r.extra_data)
                            except Exception:
                                pass
                        
                        ticket = ext.get("ticket_number") or ""
                        batch = ext.get("batch") or ""
                        pair = ext.get("pair") or ""
                        
                        # Parse counts
                        jeans_count = ext.get("jeans_count", 0)
                        shirt_count = ext.get("shirt_count", 0)
                        distribution_date = ext.get("distribution_date")
                        page_number = ext.get("page_number")
                        if page_number:
                            try:
                                page_number = int(page_number)
                            except Exception:
                                page_number = None
                        
                        # Insert InvoiceItem
                        conn.execute(text("""
                            INSERT INTO invoice_items (id, invoice_id, ticket_number, candidate_name, joining_date, 
                                                      batch, pair, jeans_count, shirt_count, claimed_amount, 
                                                      approved_amount, rejected_amount, distribution_date, page_number, 
                                                      status, reason, validation_summary, fraud_score, fraud_category,
                                                      invoice_number, invoice_date, trainee_id, billed_name, 
                                                      billed_joining_amount, billed_180_days_amount, billed_other_amount, 
                                                      billed_total_amount, approved_joining_amount, approved_180_days_amount, 
                                                      approved_total_amount, file_name, uploaded_at, extra_data)
                            VALUES (:id, :invoice_id, :ticket_number, :candidate_name, :joining_date,
                                    :batch, :pair, :jeans_count, :shirt_count, :claimed_amount,
                                    :approved_amount, :rejected_amount, :distribution_date, :page_number,
                                    :status, NULL, NULL, 0.0, 'Low',
                                    :invoice_number, :invoice_date, :trainee_id, :billed_name,
                                    :billed_joining_amount, :billed_180_days_amount, :billed_other_amount,
                                    :billed_total_amount, :approved_joining_amount, :approved_180_days_amount,
                                    :approved_total_amount, :file_name, :uploaded_at, :extra_data)
                        """), {
                            "id": r.id,
                            "invoice_id": inv_id,
                            "ticket_number": ticket,
                            "candidate_name": r.billed_name,
                            "joining_date": r.invoice_date, # Fallback
                            "batch": batch,
                            "pair": pair,
                            "jeans_count": jeans_count,
                            "shirt_count": shirt_count,
                            "claimed_amount": r.billed_total_amount,
                            "approved_amount": r.approved_total_amount,
                            "rejected_amount": max(0.0, r.billed_total_amount - r.approved_total_amount),
                            "distribution_date": distribution_date,
                            "page_number": page_number,
                            "status": r.status,
                            "invoice_number": r.invoice_number,
                            "invoice_date": r.invoice_date,
                            "trainee_id": r.trainee_id,
                            "billed_name": r.billed_name,
                            "billed_joining_amount": r.billed_joining_amount,
                            "billed_180_days_amount": r.billed_180_days_amount,
                            "billed_other_amount": r.billed_other_amount,
                            "billed_total_amount": r.billed_total_amount,
                            "approved_joining_amount": r.approved_joining_amount,
                            "approved_180_days_amount": r.approved_180_days_amount,
                            "approved_total_amount": r.approved_total_amount,
                            "file_name": r.file_name,
                            "uploaded_at": r.uploaded_at,
                            "extra_data": r.extra_data
                        })
                        
                    # Update totals on Invoice
                    for inv_num, inv_id in invoices_dict.items():
                        conn.execute(text("""
                            UPDATE invoices 
                            SET total_amount = (SELECT SUM(claimed_amount) FROM invoice_items WHERE invoice_id = :inv_id),
                                approved_amount = (SELECT SUM(approved_amount) FROM invoice_items WHERE invoice_id = :inv_id),
                                rejected_amount = (SELECT SUM(rejected_amount) FROM invoice_items WHERE invoice_id = :inv_id)
                            WHERE invoice_id = :inv_id
                        """), {"inv_id": inv_id})
                    print("Migration completed successfully.")
    except Exception as e:
        print(f"Data migration error: {e}")



upgrade_db_schema(engine)

app = FastAPI(
    title="TMPVL Billing Audit & Fraud Detection System",
    description="Offline production-grade billing validation and compliance system.",
    version="1.0.0"
)

# CORS configuration to allow local React frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],  # Allow local frontend development and production ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(router, prefix="/api")

@app.on_event("startup")
def startup_event():
    print("Registered upload endpoints:")
    for route in app.routes:
        if hasattr(route, "path") and "upload" in route.path:
            print(route.path)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "TMPVL Billing Audit & Fraud Detection System API",
        "timestamp": datetime.datetime.now().isoformat(),
    }

if __name__ == "__main__":
    from backend.app.core.config import HOST, PORT
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)

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
            
    # Upgrade payment_ledger table
    ledger_cols = [col['name'] for col in inspector.get_columns('payment_ledger')]
    with db_engine.begin() as conn:
        if 'extra_data' not in ledger_cols:
            conn.execute(text("ALTER TABLE payment_ledger ADD COLUMN extra_data JSON"))

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
            ('employee_id', 'TEXT'), ('invoice_number', 'TEXT')
        ]:
            if col_name not in audit_cols:
                conn.execute(text(f"ALTER TABLE audit_logs ADD COLUMN {col_name} {col_type}"))
        if 'ix_audit_logs_action' not in audit_indexes:
            conn.execute(text("CREATE INDEX ix_audit_logs_action ON audit_logs (action)"))

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

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "TMPVL Billing Audit & Fraud Detection System API",
        "timestamp": datetime.datetime.now().isoformat(),
    }

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)

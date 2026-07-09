import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.app.core.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False, # Required for SQLite with multi-threaded FastAPI
        "timeout": 30.0             # 30-second busy timeout to avoid database locked errors
    }
)

# Apply performance pragmas to SQLite connection
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")       # Enforces database referential integrity
    cursor.execute("PRAGMA journal_mode=WAL")      # Enables concurrent readers during writes
    cursor.execute("PRAGMA synchronous=NORMAL")    # Safer WAL commits with fewer disk flushes
    cursor.execute("PRAGMA cache_size=-64000")     # Allocate 64MB cache (negative indicates KB)
    cursor.execute("PRAGMA temp_store=MEMORY")     # Keep temporary tables/indices in memory
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


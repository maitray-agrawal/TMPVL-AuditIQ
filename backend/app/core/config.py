import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Define BASE_DIR as the project root (TMPVL AuditIQ directory)
# This file is located at backend/app/core/config.py
BASE_DIR = Path(__file__).resolve().parents[3]

# Load environment variables from the project root .env file
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

# Centralized Directory Configuration
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIRECTORY", BASE_DIR / "uploads")).resolve()
REPORT_DIR = Path(os.getenv("REPORT_DIRECTORY", BASE_DIR / "reports")).resolve()
TEMPLATE_DIR = Path(os.getenv("TEMPLATE_DIRECTORY", BASE_DIR / "templates")).resolve()
TEMP_DIR = Path(os.getenv("TEMP_DIRECTORY", BASE_DIR / "temp")).resolve()
LOG_DIR = Path(os.getenv("LOG_DIRECTORY", BASE_DIR / "logs")).resolve()

# Automatically create all required directories
for directory in [UPLOAD_DIR, REPORT_DIR, TEMPLATE_DIR, TEMP_DIR, LOG_DIR]:
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating directory {directory}: {e}")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DEFAULT_DB_FILE = BASE_DIR / "backend" / "tmpvl_audit.db"
    DEFAULT_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{DEFAULT_DB_FILE.as_posix()}"
elif DATABASE_URL.startswith("sqlite:///"):
    db_rel_path = DATABASE_URL[9:]
    if not Path(db_rel_path).is_absolute():
        resolved_db_path = (BASE_DIR / db_rel_path).resolve()
        resolved_db_path.parent.mkdir(parents=True, exist_ok=True)
        DATABASE_URL = f"sqlite:///{resolved_db_path.as_posix()}"

# Server Configuration
HOST = os.getenv("HOST", "127.0.0.1")
try:
    PORT = int(os.getenv("PORT", "8000"))
except ValueError:
    PORT = 8000

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

try:
    # Default: 50MB max upload size
    MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(50 * 1024 * 1024)))
except ValueError:
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024

PARSER_VERSION = os.getenv("PARSER_VERSION", "2.0.0")

# Setup Logging
numeric_level = getattr(logging, LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=numeric_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("config")
logger.info(f"Loaded config. BASE_DIR: {BASE_DIR.as_posix()}")
logger.info(f"Database URL: {DATABASE_URL}")

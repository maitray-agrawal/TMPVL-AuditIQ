# TMPVL Billing Audit & Fraud Detection System

![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python&)
![React](https://img.shields.io/badge/React-19-blue?logo=react&)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-05998b?logo=fastapi)
![MUI](https://img.shields.io/badge/MUI-v6-007FFF?logo=mui)
![Vite](https://img.shields.io/badge/Vite-v5-646CFF?logo=vite)
![Status](https://img.shields.io/badge/Status-Active-success)

A production-grade, completely offline enterprise application designed to audit and reconcile trainee billing submissions for **TMPVL**. The system automates the reconciliation process across three source workbooks (**BDC Master**, **Separations**, and **Vendor Invoices**), executing a comprehensive rule-based policy and fraud detection engine. It blocks double claims, enforces strict tenure and annual payment caps, validates kit quantities, and generates standardized financial ledger entries and audit reports.

---

## ✨ Key Features

*   **Automated Rule Engine**: Executes an 11-point policy to validate every line item, ensuring compliance with tenure, payment caps, and separation rules.
*   **Fraud Detection**: Proactively identifies and flags high-risk activities like duplicate billing, billing for blocked trainees, and duplicate Aadhaar/Ticket numbers.
*   **Data Ingestion & Sync**: Seamlessly imports and synchronizes data from BDC Master, Separation, and Vendor Invoice Excel workbooks.
*   **Financial Ledger**: Maintains an immutable, append-only ledger of all approved payouts, tracking per-trainee lifetime spending against an annual cap.
*   **Comprehensive Reporting**: Generates detailed Excel reports for approved/rejected invoices, financial summaries, exception lists, and fraud incidents.
*   **Offline First**: Designed to run in fully air-gapped environments with no internet connectivity required.
*   **Modern UI**: A responsive and intuitive web interface built with React and Material UI for easy operation.

---

## 🏗️ Architecture & Technology Stack

Following a **Clean Architecture** pattern, the system runs locally on Windows and is designed for fully air-gapped (offline) environments.

*   **Backend**: 
    *   **FastAPI** (Python 3.12+) — Core REST API layer.
    *   **SQLAlchemy ORM** — Database abstraction layer.
    *   **SQLite** — Single-file, lightweight embedded relational database (`tmpvl_audit.db`).
    *   **Pandas & OpenPyXL** — Excel data ingestion, manipulation, and custom spreadsheet generation.
*   **Frontend**:
    *   **React 19** + **TypeScript** — Component structure and strict static typing.
    *   **Vite 8** — Fast compilation and bundling.
    *   **Material UI v6 (MUI)** — Modern interface with responsive layouts.
    *   **AG Grid** — Large-dataset table rendering with multi-column sorting and filtering.
    *   **Recharts** — Dynamic SVG charts for billing anomalies and financial statistics.
*   **Startup Utility**:
    *   **Windows Command Batch Script** — Starts both services concurrently.

---

## 🛡️ Auditing & Fraud Policy Engine Rules

The system passes all uploaded vendor invoices through a multi-layered validation engine, enforcing the following rules in a strict hierarchy:

### Core Policy & Fraud Detection Rules
1.  **Trainee Existence**: Rejects any record for a trainee not found in the BDC Master.
2.  **Separation Checks**: Rejects payouts if the invoice date is after the trainee's separation date.
3.  **30-Day Tenure Rule**: Trainees with a tenure of < 30 days are blocked from all payments.
4.  **180-Day Tenure Rule**: Trainees separating before 180 days are ineligible for the 180-day payout (₹600).
5.  **Duplicate Aadhaar/Ticket**: Flags as `FRAUD` if an Aadhaar or Ticket number is duplicated within an invoice or across the database for different trainees.
6.  **Duplicate Billing**: Flags as `FRAUD` if a trainee is billed for the same payout type (Joining/180-Days) multiple times, either within the same invoice or against the historical ledger.
7.  **Blocked Employee Billing**: Flags as `FRAUD` if a vendor bills for a trainee who is already marked as `BLOCKED`.

### Payment & Quantity Cap Rules
8.  **Joining Payment Limit**: Caps the total lifetime joining payment at **₹1200**.
9.  **180-Day Payment Limit**: Caps the total lifetime 180-day payment at **₹600**.
10. **Kit Quantity Validation**:
    *   Rejects any `billed_other_amount` for uniforms or excess items.
    *   Flags invoices claiming >5 shirts or >4 jeans and caps the total approval at **₹1200**.
    *   Issues a warning for claims exceeding 3 shirts or 3 jeans.
11. **Annual Maximum (Hard Cap)**: Enforces a strict lifetime payout cap of **₹1800** per trainee across all payments. This is the final check and will reduce any approved amounts to stay within the limit.

---

## 📁 Repository Directory Structure

```text
d:\TTBIS
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── endpoints.py          # FastAPI route controllers
│   │   ├── core/
│   │   │   └── db.py                 # SQLite engine configuration & ORM Base
│   │   ├── models/
│   │   │   └── models.py             # Database Schemas (SQLAlchemy)
│   │   ├── repositories/
│   │   │   └── repositories.py       # CRUD operations and SQL transactions
│   │   └── services/
│   │       ├── import_service.py     # Workbook ingestion (BDC, Separation, Invoice)
│   │       ├── ledger_service.py     # Ledger accounting posting
│   │       ├── report_service.py     # Excel Report compiler
│   │       └── validation_service.py # Policy & Fraud rules engine
│   ├── main.py                       # FastAPI application entry point
│   ├── requirements.txt              # Backend python dependencies
│   └── tests/
│       └── test_validation.py        # Validation engine unittest suite
├── frontend/
│   ├── public/                       # Static public assets
│   ├── src/
│   │   ├── components/               # Shared Layout headers and navigation
│   │   ├── pages/                    # UI dashboard & workflow pages
│   │   ├── api.ts                    # Axios wrapper config
│   │   ├── App.tsx                   # Main routing tree
│   │   ├── theme.ts                  # Material UI custom dark/light theme
│   │   └── index.css                 # Global stylesheets
│   ├── package.json                  # Node.js dependencies & scripts
│   ├── tsconfig.json                 # TypeScript compiler configuration
│   └── vite.config.ts                # Vite bundler configurations
└── run_all.bat                       # Dual-service startup control script
```

---

## 🚀 Installation & Local Execution

Follow these steps to set up and run the system on a Windows machine.

### Prerequisites
*   **Python 3.12+** (configured in Windows path)
*   **Node.js v20+** + **npm**

### Step-by-Step Installation
1.  **Clone / Open the repository**:
    Ensure you are in the project folder `d:\TTBIS`.

2.  **Configure the Backend Environment**:
    Create a virtual environment and install the required modules:
    ```cmd
    python -m venv .venv
    call .venv\Scripts\activate
    pip install -r backend/requirements.txt
    ```

3.  **Configure the Frontend Environment**:
    Install all npm dependencies:
    ```cmd
    cd frontend
    npm install
    cd ..
    ```

---

## ⚙️ Running the Application

### Single-Click Execution (Recommended)
Double-click the `run_all.bat` file in the root workspace directory, or launch it via the terminal:
```cmd
run_all.bat
```
This script will:
*   Spawn a command window starting the FastAPI service on `http://127.0.0.1:8000`.
*   Spawn a command window starting the Vite frontend on `http://localhost:5173`.
*   Automatically open your default browser to `http://localhost:5173/`.

### Manual Service Execution
If you prefer to run services manually:

**Backend Service**:
```cmd
call .venv\Scripts\activate
set PYTHONPATH=.
python -m backend.main
```
```
set PYTHONPATH=.python -m backend.main
```

**Frontend Client**:
```cmd
cd frontend
npm run dev
```

---

## 🧪 Running Backend Unit Tests

A comprehensive unit test suite validates the policy engine, fraud detection, and data import services against an in-memory SQLite database. Run all tests using `pytest` or a specific suite with `unittest`.

```cmd
call .venv\Scripts\activate
python -m pytest tests/ -v
```

---

## 📖 Operational Workflow

1.  **BDC Ingestion**: Head to the **BDC Upload** page and upload the BDC Master sheet to load active trainee profiles and their baseline details into the system.
2.  **Separation Ingestion**: Upload the Separation registers in the **Separation Upload** page to record resignations and update trainees' DOL (Date of Leaving) records.
3.  **Invoice Upload**: Importer a billing invoice spreadsheet from Quess.
4.  **Audit / Reconciliation**: Open the **Validation Engine**, select the pending invoice, and click **Run Rules Validation**. The engine will highlight and flag violations (Warnings, Errors, or Fraud) line-by-line.
5.  **payout Ledger Approval**: Click **Approve Invoice Payouts** to lock approved figures and write validated financial entries to the ledger.
6.  **Reports**: Download custom-compiled audit spreadsheets, exception reports, or summaries from the **Reports** portal.

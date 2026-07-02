# Payment Ledger Refactoring - Complete Guide

## Overview
The Payment Ledger has been comprehensively refactored to implement enhanced payment rules, improved UI visibility, and stricter annual cap enforcement (₹1800 maximum per trainee).

---

## 1. Payment Rules Implementation

### Rule Hierarchy & Validation Order

```
Invoice Submitted
    ↓
Rule: Trainee Exists & Status Valid
    ↓
Rule: 30-180 Day Separation Checks
    ↓
Rule: Duplicate Prevention (Aadhaar, Ticket, Billing)
    ↓
Rule: Blocked Employee Check
    ↓
Rule: Joining Payment Limit (Max ₹1200)
    ├─ Approved: Amount ≤ ₹1200
    ├─ Rejected: Amount > ₹1200 (reduce to max)
    └─ Ledger Entry: Track approved vs rejected
    ↓
Rule: 180-Day Payment Limit (Max ₹600)
    ├─ Approved: Amount ≤ ₹600
    ├─ Rejected: Amount > ₹600 (reduce to max)
    └─ Ledger Entry: Track approved vs rejected
    ↓
Rule: Kit Quantity Validation
    ├─ IF billed_other_amount > 0: Flag as rejected (uniforms/excess items)
    ├─ IF (shirts > 5 OR jeans > 4): Flag excess + cap at ₹1200
    ├─ IF (shirts > 3 OR jeans > 3): Warning only
    └─ Ledger Entry: Track flag status
    ↓
Rule: Annual Maximum (Hard Cap ₹1800)
    ├─ Calculate trainee's running_total from prior ledger entries
    ├─ remaining_balance = max(0, 1800 - running_total)
    ├─ approved_joining = min(approved_joining, remaining_balance)
    ├─ If approved_joining reduced:
    │  ├─ Update remaining_balance after joining
    │  └─ approved_180 = min(approved_180, remaining_balance)
    └─ Ledger Entry: Post only amounts within remaining balance
    ↓
Decision: Approve / Reject Invoice
    ↓
Ledger Entry Posted (if any approval amount > 0)
```

---

## 2. Ledger Data Structure

### Database Model: PaymentLedger
```python
class PaymentLedger(Base):
    id: int (Primary Key)
    trainee_id: str (Foreign Key → Trainee.id)
    invoice_number: str (Reference to original invoice)
    payment_type: str (JOINING | 180_DAYS)
    amount_paid: float (Approved amount posted)
    payment_date: date (Date of payment)
    extra_data: JSON (Metadata)
    created_at: datetime (Auto-timestamp)
```

### Extra Data JSON Structure
```json
{
  "invoice_month": "March 2025",
  "rejected": 300.0,
  "running_total": 1200.0,
  "remaining_balance": 600.0
}
```

**Field Definitions:**
- **invoice_month**: Display in ledger UI (extracted from invoice_date)
- **rejected**: billed_amount - approved_amount (policy violations)
- **running_total**: Cumulative payments for trainee (all prior entries + current)
- **remaining_balance**: Annual cap remaining (₹1800 - running_total)

---

## 3. Frontend Payment Ledger UI

### Column Layout (Left to Right)

| Column | Width | Type | Format | Notes |
|--------|-------|------|--------|-------|
| **Trainee ID** | 130px | String | - | Pinned left |
| **Trainee Name** | 200px | String | - | Searchable |
| **Payment Date** | 130px | Date | DD/MM/YYYY | Sortable |
| **Invoice Number** | 150px | String | - | Vendor ref |
| **Invoice Month** | 140px | String | "Month YYYY" | From extra_data |
| **Payment Type** | 130px | Enum | Color-coded badge | JOINING (blue) / 180_DAYS (green) |
| **Approved Amount** | 160px | Currency | ₹X,XXX | Green, bold |
| **Rejected Amount** | 160px | Currency | ₹X,XXX | Red, bold |
| **Running Total** | 160px | Currency | ₹X,XXX | Blue bg highlight |
| **Remaining Balance** | 160px | Currency | ₹X,XXX | Conditional coloring |

### Remaining Balance Color Coding
```
₹0 or less     → Red (Annual cap reached)
₹1 - ₹300      → Amber (Approaching limit)
₹301 - ₹1800   → Green (Safe zone)
```

### Example Ledger Output

```
Trainee ID | Name       | Pay Date    | Invoice  | Month     | Type      | Approved | Rejected | Running Total | Remaining
-----------|------------|-------------|----------|-----------|-----------|----------|----------|---------------|----------
T001       | John Doe   | 15/01/2025  | INV001   | Jan 2025  | JOINING   | ₹1,200   | ₹0       | ₹1,200        | ₹600
T001       | John Doe   | 20/03/2025  | INV002   | Mar 2025  | 180_DAYS  | ₹400     | ₹200     | ₹1,600        | ₹200
T002       | Jane Smith | 01/02/2025  | INV003   | Feb 2025  | JOINING   | ₹1,200   | ₹0       | ₹1,200        | ₹600
T002       | Jane Smith | 15/05/2025  | INV004   | May 2025  | 180_DAYS  | ₹600     | ₹0       | ₹1,800        | ₹0
```

---

## 4. Kit Quantity Rules

### Current Implementation

**Configuration Parameters:**
```python
config = {
    "max_shirts": 3.0,                    # Maximum approvable shirts
    "max_jeans": 3.0,                     # Maximum approvable jeans
    "invoice_threshold_shirts": 5.0,      # Threshold for flagging excess
    "invoice_threshold_jeans": 4.0,       # Threshold for flagging excess
    "kit_approval_cap": 1200.0            # Approval limit when excess flagged
}
```

### Validation Logic

**Step 1: Check for Billed Other Items**
- If `invoice.billed_other_amount > 0`:
  - Action: **REJECT** (always)
  - Message: "Vendor billed ₹XXX for uniforms/jeans/shirts, which is ignored/rejected per policy"
  - Reason Code: `KIT_OTHER_ITEMS`

**Step 2: Check Invoice Thresholds**
- If `shirt_qty > 5` OR `jean_qty > 4`:
  - Action: **FLAG** with WARNING status
  - Message: "Invoice claims X shirts, Y jeans. Threshold: 5 shirts, 4 jeans"
  - Consequence: Approve only ₹1,200 (cap at kit_approval_cap)
  - Reason Code: `KIT_EXCESS_THRESHOLD`

**Step 3: Check Max Quantities**
- If `shirt_qty > 3` OR `jean_qty > 3`:
  - Action: **WARNING** (no approval cap)
  - Message: "Kit quantity exceeds maximum: X shirts, Y jeans. Max: 3 shirts, 3 jeans"
  - Reason Code: `KIT_QTY_MISMATCH`

### Decision Matrix

| Shirts Qty | Jeans Qty | Billed Other | Action | Approval Cap | Status |
|-----------|-----------|-------------|--------|--------------|--------|
| 0-2 | 0-1 | ₹0 | ✅ Approve | Full amount | PASSED |
| 3 | 3 | ₹0 | ⚠️ Warning | Full amount | WARNING |
| 4-5 | 4 | ₹0 | 🚩 Flag | ₹1,200 | WARNING |
| >5 | >4 | ₹0 | 🚩 Flag | ₹1,200 | WARNING |
| Any | Any | >0 | ❌ Reject | ₹0 | WARNING |

---

## 5. Annual Maximum Enforcement

### The ₹1800 Hard Cap

The annual maximum of **₹1800** is a hard constraint that applies per trainee across **all invoices**.

### Enforcement Point: LedgerService

```python
def approve_invoice_and_post_to_ledger(invoice_number):
    for trainee_record in invoice:
        # Calculate current spending
        prior_entries = query(PaymentLedger).filter(trainee_id)
        running_total = sum(prior_entries.amount_paid)
        remaining = max(0, 1800 - running_total)
        
        # Cap joining amount
        joining_to_post = min(approved_joining, remaining)
        remaining -= joining_to_post
        
        # Cap 180-day amount with updated remaining
        days_180_to_post = min(approved_180, remaining)
        
        # Post ledger entries only if amounts > 0
        if joining_to_post > 0:
            post_ledger_entry(
                amount=joining_to_post,
                rejected=billed_joining - joining_to_post,
                running_total=running_total + joining_to_post,
                remaining=remaining
            )
```

### Scenario Examples

**Scenario 1: Multiple Invoices**
```
Invoice 1 (Jan): Joining ₹1,200, 180-Day ₹600
  ├─ Posted: ₹1,200 + ₹600 = ₹1,800
  ├─ Running Total: ₹1,800
  └─ Remaining: ₹0

Invoice 2 (May): Joining ₹500, 180-Day ₹400
  ├─ Posted: ₹0 (annual cap reached)
  ├─ Running Total: ₹1,800
  └─ Remaining: ₹0
```

**Scenario 2: Partial Spend**
```
Invoice 1 (Jan): Joining ₹1,200
  ├─ Posted: ₹1,200
  ├─ Running Total: ₹1,200
  └─ Remaining: ₹600

Invoice 2 (Apr): 180-Day ₹700 (claim exceeds ₹600 max)
  ├─ Posted: ₹600 (min of approved ₹600 and remaining ₹600)
  ├─ Running Total: ₹1,800
  └─ Remaining: ₹0
```

---

## 6. Service Methods

### LedgerService.get_trainee_payment_summary()
```python
def get_trainee_payment_summary(db, trainee_id) -> dict:
    """
    Returns:
    {
        "total_approved": float,      # Sum of all posted amounts
        "remaining_balance": float,   # Annual cap minus total
        "annual_cap": float,          # 1800.0
        "entries_count": int          # Number of ledger records
    }
    """
```

### LedgerService.approve_invoice_and_post_to_ledger()
```python
def approve_invoice_and_post_to_ledger(db, invoice_number) -> bool:
    """
    1. Retrieve all records for invoice
    2. Clear any prior ledger entries (prevent duplicates)
    3. For each record:
       - Calculate payment summary for trainee
       - Enforce annual cap on joining amount
       - Enforce annual cap on 180-day amount
       - Post ledger entries with extra_data (rejected, running_total, remaining_balance)
    4. Log audit entry with detailed breakdown
    5. Return: True if posted, False otherwise
    """
```

---

## 7. Testing

### Test Suite: `test_payment_ledger.py`

8 comprehensive tests covering:
1. ✅ Joining maximum (₹1200)
2. ✅ 180 days maximum (₹600)
3. ✅ Annual maximum (₹1800)
4. ✅ Kit quantity limits (3 shirts, 3 jeans)
5. ✅ Excess kit flagging (5 shirts, 4 jeans)
6. ✅ Running total accumulation
7. ✅ Remaining balance calculations
8. ✅ Invoice month tracking

**Run tests:**
```bash
cd backend
python -m pytest tests/test_payment_ledger.py -v
```

---

## 8. Configuration

### Settings File: `settings_config.json`

```json
{
  "joining_payment_max": 1200.0,
  "days180_payment_max": 600.0,
  "max_payable_per_trainee": 1800.0,
  "min_days_reimbursement": 30,
  "max_shirts": 3.0,
  "max_jeans": 3.0,
  "invoice_threshold_shirts": 5.0,
  "invoice_threshold_jeans": 4.0,
  "kit_approval_cap": 1200.0
}
```

---

## 9. Audit Trail

Each ledger transaction logs:
- ✅ Invoice number
- ✅ Trainee ID
- ✅ Payment type (JOINING/180_DAYS)
- ✅ Approved amount
- ✅ Rejected amount (if applicable)
- ✅ Running total (post-approval)
- ✅ Remaining balance (post-approval)
- ✅ Invoice month
- ✅ Payment date
- ✅ Timestamp

Example audit log:
```
Action: APPROVE_INVOICE
Module: LEDGER
Details: Approved invoice 'INV001'. Posted 2 payout entries. Total approved: ₹1800.
  Details: JOINING: ₹1200 posted (rejected: ₹0, remaining: ₹600);
           180_DAYS: ₹600 posted (rejected: ₹0, remaining: ₹0)
```

---

## 10. Implementation Checklist

- [x] **Kit Rules** - Updated max quantities (3/3), added threshold logic (5/4 → ₹1200 cap)
- [x] **Frontend UI** - Enhanced columns (month, rejected, running total, remaining balance)
- [x] **Ledger Service** - Strict annual cap enforcement, improved calculations
- [x] **Tests** - Comprehensive validation of all payment rules
- [x] **Documentation** - This guide + code comments

---

## 11. Migration Notes

If upgrading from previous version:
1. **No database schema changes** - Extra data fields are JSON, backward compatible
2. **Ledger entries already have** running_total and remaining_balance (old entries may lack these)
3. **Frontend shows** all fields from extra_data; missing fields display as "-" or "₹0"
4. **Rules are** applied at approval time, not retroactively

---

## 12. Future Enhancements

Potential improvements:
- [ ] Batch approval UI with preview of cap impacts
- [ ] Trainee-level cap visualization dashboard
- [ ] Export ledger to Excel with summaries
- [ ] Approval workflow with manager override audit trails
- [ ] Tier-based limits (different for different schemes: NAPS/B.Tech/M.Tech)

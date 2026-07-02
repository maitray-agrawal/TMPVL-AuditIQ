from typing import Optional, Dict, Any, List
from backend.app.services.rules.base import BaseRule, RuleResult

class Rule180Days(BaseRule):
    @property
    def name(self) -> str:
        return "Tenure < 180 Days"

    def evaluate(
        self,
        record: Any,
        trainee: Optional[Any],
        history: List[Any],
        config: Dict[str, Any],
        state: Dict[str, Any],
        current_joining: float,
        current_180: float
    ) -> RuleResult:
        if not trainee:
            return RuleResult(
                passed=True,
                severity=None,
                reason="",
                approved_amount=current_joining + current_180,
                rejected_amount=0.0,
                approved_joining=current_joining,
                approved_180=current_180,
                rejected_joining=0.0,
                rejected_180=0.0,
                stop_processing=False
            )

        min_days = config.get("min_days_reimbursement", 30)
        doj = trainee.doj
        dol = trainee.dol
        if dol:
            tenure_days = (dol - doj).days
        else:
            tenure_days = (record.invoice_date - doj).days

        # Skip if already handled by Under 30 Days check
        if dol is not None and tenure_days < min_days:
            return RuleResult(
                passed=True,
                severity=None,
                reason="",
                approved_amount=current_joining + current_180,
                rejected_amount=0.0,
                approved_joining=current_joining,
                approved_180=current_180,
                rejected_joining=0.0,
                rejected_180=0.0,
                stop_processing=False
            )

        failures = []
        new_joining = current_joining
        new_180 = current_180
        days180_max = config.get("days180_payment_max", 600.0)
        joining_max = config.get("joining_payment_max", 1200.0)

        joining_paid = sum(h.amount_paid for h in history if h.payment_type == "JOINING")

        # 1. Left before 180 days
        if dol is not None and tenure_days < 180:
            if record.billed_180_days_amount > 0:
                new_180 = 0.0
                failures.append({
                    "rule_name": "Tenure < 180 Days",
                    "status": "ERROR",
                    "message": f"Trainee left before 180 days (tenure: {tenure_days} days). Post-180 days payment of ₹{days180_max} not allowed.",
                    "reason_code": "SECOND_PAYMENT_BEFORE_180_DAYS",
                    "recommended_action": "Reject 180-days payment. Trainee left before completing 180 days tenure."
                })
            
            # Joining payment allowed ONLY if already approved
            if record.billed_joining_amount > 0:
                is_joining_duplicate = any(res.get("rule_name") == "Double Claiming (Same Cycle)" for res in state.get("record_results", []))
                if not is_joining_duplicate:
                    if joining_paid > 0:
                        remaining_j = max(0.0, joining_max - joining_paid)
                        new_joining = min(current_joining, remaining_j)
                    else:
                        new_joining = 0.0
                        failures.append({
                            "rule_name": "Tenure < 180 Days (Resigned)",
                            "status": "ERROR",
                            "message": f"Trainee left before 180 days (tenure: {tenure_days} days). New joining reimbursement not allowed as it was not approved prior to separation.",
                            "reason_code": "SECOND_PAYMENT_BEFORE_180_DAYS",
                            "recommended_action": "Reject joining payout. Trainee has resigned before 180 days and joining was not approved prior to separation."
                        })
 
        # 2. Active trainee under 180 days
        elif dol is None and tenure_days < 180:
            if record.billed_180_days_amount > 0:
                new_180 = 0.0
                failures.append({
                    "rule_name": "Tenure < 180 Days (Active)",
                    "status": "ERROR",
                    "message": f"Trainee tenure is {tenure_days} days. 180-days reimbursement requires minimum 180 days tenure.",
                    "reason_code": "SECOND_PAYMENT_BEFORE_180_DAYS",
                    "recommended_action": "Reject 180-days payment. Active trainee must complete at least 180 days of tenure before eligibility."
                })
 
        # 3. Enforce 180-days cap (₹600) and historical duplicates
        if new_180 > 0.0:
            is_180_duplicate = any(res.get("rule_name") == "Double Claiming (Same Cycle)" for res in state.get("record_results", []))
            if not is_180_duplicate:
                days180_paid = sum(h.amount_paid for h in history if h.payment_type == "180_DAYS")
                if days180_paid >= days180_max:
                    new_180 = 0.0
                    failures.append({
                        "rule_name": "Double Claiming (Historical)",
                        "status": "FRAUD",
                        "message": f"Historical double claim: Trainee '{trainee.id}' was already paid ₹{days180_paid} for 180-days reimbursement (Max: ₹{days180_max}).",
                        "reason_code": "ALREADY_RECEIVED_180DAYS_MAX",
                        "recommended_action": "Reject 180-days payout. Employee has already received the maximum ₹600 180-days amount."
                    })
                else:
                    remaining_180 = max(0.0, days180_max - days180_paid)
                    capped_180 = min(new_180, remaining_180)
                    if capped_180 < new_180:
                        failures.append({
                            "rule_name": "180 Days Payment Cap",
                            "status": "WARNING",
                            "message": f"Billed 180 days amount ₹{record.billed_180_days_amount} capped at remaining ₹{capped_180} (Total paid: ₹{days180_paid}).",
                            "reason_code": "EXCEEDS_PAYMENT_LIMITS",
                            "recommended_action": "Cap approved amounts to the standard maximum limit (₹1200 for Joining, ₹600 for 180-days) or the remaining balance."
                        })
                        new_180 = capped_180

        if failures:
            rejected_joining = current_joining - new_joining
            rejected_180_days = current_180 - new_180
            return RuleResult(
                passed=False,
                severity="ERROR" if any(f["status"] == "ERROR" for f in failures) else ("FRAUD" if any(f["status"] == "FRAUD" for f in failures) else "WARNING"),
                reason="; ".join(f["message"] for f in failures),
                approved_amount=new_joining + new_180,
                rejected_amount=rejected_joining + rejected_180_days,
                approved_joining=new_joining,
                approved_180=new_180,
                rejected_joining=rejected_joining,
                rejected_180=rejected_180_days,
                stop_processing=False,
                failures=failures
            )

        return RuleResult(
            passed=True,
            severity=None,
            reason="",
            approved_amount=current_joining + current_180,
            rejected_amount=0.0,
            approved_joining=current_joining,
            approved_180=current_180,
            rejected_joining=0.0,
            rejected_180=0.0,
            stop_processing=False
        )

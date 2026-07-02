from typing import Optional, Dict, Any, List
from backend.app.services.rules.base import BaseRule, RuleResult

class RuleJoiningLimit(BaseRule):
    @property
    def name(self) -> str:
        return "Joining Payment Cap"

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
        if not trainee or current_joining == 0.0 or record.billed_joining_amount == 0:
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

        is_joining_duplicate = any(res.get("rule_name") == "Double Claiming (Same Cycle)" for res in state.get("record_results", []))
        if is_joining_duplicate:
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

        new_joining = current_joining
        joining_max = config.get("joining_payment_max", 1200.0)
        joining_paid = sum(h.amount_paid for h in history if h.payment_type == "JOINING")

        if joining_paid >= joining_max:
            new_joining = 0.0
            msg = f"Historical double claim: Trainee '{trainee.id}' was already paid ₹{joining_paid} for joining reimbursement (Max: ₹{joining_max})."
            
            # Use custom rule name to match original expected database log
            state["custom_rule_name"] = "Double Claiming (Historical)"
            
            failures = [{
                "rule_name": "Double Claiming (Historical)",
                "status": "FRAUD",
                "message": msg,
                "reason_code": "ALREADY_RECEIVED_JOINING_MAX",
                "recommended_action": "Reject joining payout. Employee has already received the maximum ₹1200 joining amount."
            }]
            return RuleResult(
                passed=False,
                severity="FRAUD",
                reason=msg,
                approved_amount=new_joining + current_180,
                rejected_amount=current_joining - new_joining,
                approved_joining=new_joining,
                approved_180=current_180,
                rejected_joining=current_joining - new_joining,
                rejected_180=0.0,
                stop_processing=False,
                failures=failures
            )
        else:
            remaining_j = max(0.0, joining_max - joining_paid)
            new_joining = min(current_joining, remaining_j)
            if new_joining < current_joining:
                msg = f"Billed joining amount ₹{record.billed_joining_amount} capped at remaining ₹{new_joining} (Total paid: ₹{joining_paid})."
                failures = [{
                    "rule_name": "Joining Payment Cap",
                    "status": "WARNING",
                    "message": msg,
                    "reason_code": "EXCEEDS_PAYMENT_LIMITS",
                    "recommended_action": "Cap approved amounts to the standard maximum limit (₹1200 for Joining, ₹600 for 180-days) or the remaining balance."
                }]
                return RuleResult(
                    passed=False,
                    severity="WARNING",
                    reason=msg,
                    approved_amount=new_joining + current_180,
                    rejected_amount=current_joining - new_joining,
                    approved_joining=new_joining,
                    approved_180=current_180,
                    rejected_joining=current_joining - new_joining,
                    rejected_180=0.0,
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

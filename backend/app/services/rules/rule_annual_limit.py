from typing import Optional, Dict, Any, List
from backend.app.services.rules.base import BaseRule, RuleResult

class RuleAnnualLimit(BaseRule):
    @property
    def name(self) -> str:
        return "Maximum Trainee Cap"

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

        total_max = config.get("max_payable_per_trainee", 1800.0)
        joining_paid = sum(h.amount_paid for h in history if h.payment_type == "JOINING")
        days180_paid = sum(h.amount_paid for h in history if h.payment_type == "180_DAYS")
        total_paid = joining_paid + days180_paid

        if total_paid >= total_max:
            new_joining = 0.0
            new_180 = 0.0
            msg = f"Historical limit reached: Trainee '{trainee.id}' has already received the maximum ₹{total_paid} lifetime amount."
            failures = [{
                "rule_name": "Maximum Trainee Cap",
                "status": "FRAUD",
                "message": msg,
                "reason_code": "ALREADY_RECEIVED_TOTAL_MAX",
                "recommended_action": "Reject all payouts. Employee has already received the maximum total lifecycle limit of ₹1800."
            }]
            return RuleResult(
                passed=False,
                severity="FRAUD",
                reason=msg,
                approved_amount=0.0,
                rejected_amount=current_joining + current_180,
                approved_joining=0.0,
                approved_180=0.0,
                rejected_joining=current_joining,
                rejected_180=current_180,
                stop_processing=False,
                failures=failures
            )

        total_potential = total_paid + current_joining + current_180
        if total_potential > total_max:
            allowed_now = max(0.0, total_max - total_paid)
            old_joining = current_joining
            old_180 = current_180
            
            new_joining = min(current_joining, allowed_now)
            new_180 = min(current_180, max(0.0, allowed_now - new_joining))
            
            msg = f"Total payments exceed ₹{total_max} limit. Capped current approvals from ₹{old_joining + old_180} to ₹{new_joining + new_180} (Previous paid: ₹{total_paid})."
            
            rejected_j = old_joining - new_joining
            rejected_180_days = old_180 - new_180
            
            failures = [{
                "rule_name": "Maximum Trainee Cap",
                "status": "WARNING",
                "message": msg,
                "reason_code": "LIFETIME_LIMIT_EXCEEDED",
                "recommended_action": "Cap the payout to prevent the total cumulative disbursement from exceeding ₹1800."
            }]
            
            return RuleResult(
                passed=False,
                severity="WARNING",
                reason=msg,
                approved_amount=new_joining + new_180,
                rejected_amount=rejected_j + rejected_180_days,
                approved_joining=new_joining,
                approved_180=new_180,
                rejected_joining=rejected_j,
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

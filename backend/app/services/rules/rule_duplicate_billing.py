from typing import Optional, Dict, Any, List
from backend.app.services.rules.base import BaseRule, RuleResult

class RuleDuplicateBilling(BaseRule):
    @property
    def name(self) -> str:
        return "Double Claiming (Same Cycle)"

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

        reasons = []
        new_joining = current_joining
        new_180 = current_180
        rejected_j = 0.0
        rejected_180_days = 0.0

        failures = []
        if record.billed_joining_amount > 0:
            if trainee.id in state["seen_trainees_joining"]:
                new_joining = 0.0
                rejected_j = record.billed_joining_amount
                msg = f"Duplicate joining claim: Trainee '{trainee.id}' appears multiple times in this invoice for joining reimbursement."
                reasons.append(msg)
                failures.append({
                    "rule_name": "Double Claiming (Same Cycle)",
                    "status": "FRAUD",
                    "message": msg,
                    "reason_code": "DUP_CLAIM_SAME_CYCLE",
                    "recommended_action": "Reject duplicate row-level claims. Keep first instance only."
                })
            else:
                state["seen_trainees_joining"].add(trainee.id)

        if record.billed_180_days_amount > 0:
            if trainee.id in state["seen_trainees_180"]:
                new_180 = 0.0
                rejected_180_days = record.billed_180_days_amount
                msg = f"Duplicate 180 days claim: Trainee '{trainee.id}' appears multiple times in this invoice for 180-days reimbursement."
                reasons.append(msg)
                failures.append({
                    "rule_name": "Double Claiming (Same Cycle)",
                    "status": "FRAUD",
                    "message": msg,
                    "reason_code": "DUP_CLAIM_SAME_CYCLE",
                    "recommended_action": "Reject duplicate row-level claims. Keep first instance only."
                })
            else:
                state["seen_trainees_180"].add(trainee.id)

        if reasons:
            return RuleResult(
                passed=False,
                severity="FRAUD",
                reason="; ".join(reasons),
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

from typing import Optional, Dict, Any, List
from backend.app.services.rules.base import BaseRule, RuleResult

class RuleBlockedEmployee(BaseRule):
    @property
    def name(self) -> str:
        return "Blocked Trainee Billing"

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
        if trainee and trainee.status == "BLOCKED":
            msg = f"Trainee '{trainee.id}' is permanently BLOCKED from future billing. Reason: {trainee.blocked_reason}"
            failures = [{
                "rule_name": "Blocked Trainee Billing",
                "status": "FRAUD",
                "message": msg,
                "reason_code": "EMP_BLOCKED",
                "recommended_action": "Reject all payments. Trainee was flagged as blocked due to compliance violation."
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
                stop_processing=True,
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

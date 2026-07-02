from typing import Optional, Dict, Any, List
from backend.app.services.rules.base import BaseRule, RuleResult

class RuleAmountMismatch(BaseRule):
    @property
    def name(self) -> str:
        return "Invoice Amount Mismatch"

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
        if record.billed_total_amount is None or record.billed_total_amount == 0.0:
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

        billed_joining = getattr(record, "billed_joining_amount", 0.0) or 0.0
        billed_180 = getattr(record, "billed_180_days_amount", 0.0) or 0.0
        billed_other = getattr(record, "billed_other_amount", 0.0) or 0.0
        billed_total = getattr(record, "billed_total_amount", 0.0) or 0.0

        expected_total = billed_joining + billed_180 + billed_other
        
        if abs(billed_total - expected_total) > 0.01:
            msg = f"Invoice amount mismatch: Total billed (₹{billed_total}) does not match the sum of items (Joining: ₹{billed_joining}, 180-Days: ₹{billed_180}, Other/Kit: ₹{billed_other}, Sum: ₹{expected_total})."
            failures = [{
                "rule_name": "Invoice Amount Mismatch",
                "status": "ERROR",
                "message": msg,
                "reason_code": "AMOUNT_MISMATCH",
                "recommended_action": "Verify billed amounts. The total billed amount must equal the sum of billed joining, 180-days, and other/kit items."
            }]
            return RuleResult(
                passed=False,
                severity="ERROR",
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

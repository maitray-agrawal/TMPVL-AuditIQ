from typing import Optional, Dict, Any, List
from backend.app.services.rules.base import BaseRule, RuleResult

class RuleTraineeNotFound(BaseRule):
    @property
    def name(self) -> str:
        return "Trainee Not Found"

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
        if not record.trainee_id or not trainee:
            raw_id = "Unknown"
            if record.extra_data and isinstance(record.extra_data, dict):
                # Search for trainee id in key variations
                for k in ['trainee id', 'emp id', 'employee id', 'trainee_id', 'reg no']:
                    if k in record.extra_data:
                        raw_id = record.extra_data[k]
                        break
            msg = f"Trainee ID '{raw_id}' not found in BDC Master Workbook."
            failures = [{
                "rule_name": "Trainee Not Found",
                "status": "ERROR",
                "message": msg,
                "reason_code": "EMP_NOT_FOUND",
                "recommended_action": "Reject payment. Verify personnel/ticket number and prompt BDC workbook upload."
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

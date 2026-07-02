from typing import Optional, Dict, Any, List
from backend.app.services.rules.base import BaseRule, RuleResult

class RuleDuplicateAadhaar(BaseRule):
    @property
    def name(self) -> str:
        return "Duplicate Aadhaar Number"

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
        if not trainee or not trainee.aadhaar:
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

        aadhaar = trainee.aadhaar.strip().replace(" ", "").replace("-", "")
        seen_aadhaars = state.setdefault("seen_aadhaars", {})
        db_aadhaars = state.get("db_aadhaars", {})

        # 1. Check duplicate within the same invoice
        if aadhaar in seen_aadhaars and seen_aadhaars[aadhaar] != trainee.id:
            msg = f"Duplicate Aadhaar: Aadhaar '{aadhaar}' belongs to multiple trainees in same invoice ('{seen_aadhaars[aadhaar]}' and '{trainee.id}')."
            failures = [{
                "rule_name": "Duplicate Aadhaar Number",
                "status": "FRAUD",
                "message": msg,
                "reason_code": "DUP_AADHAAR",
                "recommended_action": "Block employee payouts, verify national identity records for duplication."
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
        seen_aadhaars[aadhaar] = trainee.id

        # 2. Check duplicate against other trainees in database
        if aadhaar in db_aadhaars and db_aadhaars[aadhaar] != trainee.id:
            msg = f"Duplicate Aadhaar: Aadhaar '{aadhaar}' already exists for another trainee '{db_aadhaars[aadhaar]}' in database."
            failures = [{
                "rule_name": "Duplicate Aadhaar Number",
                "status": "FRAUD",
                "message": msg,
                "reason_code": "DUP_AADHAAR",
                "recommended_action": "Block employee payouts, verify national identity records for duplication."
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

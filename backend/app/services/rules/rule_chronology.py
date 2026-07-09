import datetime
from typing import Optional, Dict, Any, List
from backend.app.services.rules.base import BaseRule, RuleResult

class RuleChronology(BaseRule):
    @property
    def name(self) -> str:
        return "Chronology Validation"

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

        failures = []
        reasons = []

        dist_date = record.distribution_date
        master_doj = trainee.doj
        invoice_date = record.invoice_date

        # 1. Distribution Date before DOJ check
        if dist_date and master_doj:
            if dist_date < master_doj:
                msg = f"Distribution Date Chronology: Distribution date '{dist_date}' is before trainee DOJ '{master_doj}'."
                reasons.append(msg)
                failures.append({
                    "rule_name": "Distribution Date Before DOJ",
                    "status": "FRAUD",
                    "message": msg,
                    "reason_code": "DIST_DATE_BEFORE_DOJ",
                    "recommended_action": "Reject billing. Trainee cannot receive kit prior to their joining date."
                })

        # 2. Future Distribution Date check
        if dist_date:
            today = datetime.date.today()
            # If dist_date is in the future relative to today or the invoice date
            ref_date = invoice_date if invoice_date else today
            if dist_date > today or dist_date > ref_date:
                msg = f"Future Distribution Date: Distribution date '{dist_date}' is in the future."
                reasons.append(msg)
                failures.append({
                    "rule_name": "Future Distribution Date",
                    "status": "FRAUD",
                    "message": msg,
                    "reason_code": "FUTURE_DIST_DATE",
                    "recommended_action": "Reject billing. Chronological impossibility: kit distribution cannot be in the future."
                })

        if failures:
            # If there's any chronology error, we reject both payouts
            return RuleResult(
                passed=False,
                severity="FRAUD",
                reason="; ".join(reasons),
                approved_amount=0.0,
                rejected_amount=current_joining + current_180,
                approved_joining=0.0,
                approved_180=0.0,
                rejected_joining=current_joining,
                rejected_180=current_180,
                stop_processing=True, # Stop evaluating further rules since this is a severe chronological error
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

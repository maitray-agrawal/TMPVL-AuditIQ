from typing import Optional, Dict, Any, List
from backend.app.services.rules.base import BaseRule, RuleResult

class Rule30Days(BaseRule):
    @property
    def name(self) -> str:
        return "Tenure < 30 Days"

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

        # Consult complete separation history for any lifecycle with tenure < min_days
        has_historical_early_sep = False
        for s in getattr(trainee, "separation_records", []):
            s_tenure = s.extra_data.get("tenure") if s.extra_data else None
            if s_tenure is None and s.dol:
                lifecycles = (trainee.extra_data or {}).get("lifecycles", [])
                matched_lc = next((lc for lc in lifecycles if lc.get("dol") == s.dol.strftime("%Y-%m-%d")), None)
                if matched_lc and matched_lc.get("doj"):
                    try:
                        import datetime as dt
                        lc_doj = dt.datetime.strptime(matched_lc["doj"], "%Y-%m-%d").date()
                        s_tenure = (s.dol - lc_doj).days
                    except Exception:
                        pass
                if s_tenure is None:
                    if trainee.doj and s.dol < trainee.doj:
                        s_tenure = min_days + 1  # Assume compliant for completed previous lifecycles
                    elif trainee.doj:
                        s_tenure = (s.dol - trainee.doj).days
            if s_tenure is not None and s_tenure < min_days:
                has_historical_early_sep = True
                tenure_days = min(tenure_days, s_tenure)

        if (dol is not None and tenure_days < min_days) or has_historical_early_sep:
            # Trainee left before 30 days - permanently block them and reject both payments
            msg = f"Trainee tenure was {tenure_days} days (resigned before {min_days} days). Reimbursement is ₹0. Trainee status set to BLOCKED."
            state["block_trainee_reason"] = f"Resigned before {min_days} days (tenure: {tenure_days} days)"
            
            # The rule name logged in database should be dynamic
            state["custom_rule_name"] = f"Tenure < {min_days} Days"

            failures = [{
                "rule_name": f"Tenure < {min_days} Days",
                "status": "ERROR",
                "message": msg,
                "reason_code": "LEFT_WITHIN_30_DAYS",
                "recommended_action": "Permanently block employee and reject all payments because tenure is less than 30 days."
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

from typing import Optional, Dict, Any, List
from backend.app.services.rules.base import BaseRule, RuleResult
import datetime

class RuleSeparationChecks(BaseRule):
    @property
    def name(self) -> str:
        return "Separation Status Validation"

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
        new_joining = current_joining
        new_180 = current_180

        # Check latest dol for the current lifecycle
        dol = trainee.dol
        if not dol and hasattr(trainee, "separation_records") and trainee.separation_records and trainee.doj:
            current_seps = [s.dol for s in trainee.separation_records if s.dol and s.dol >= trainee.doj]
            if current_seps:
                dol = max(current_seps)

        if dol:
            invoice_date = record.invoice_date
            
            # 1. Separated before invoice: dol month is strictly before invoice month
            if dol.year < invoice_date.year or (dol.year == invoice_date.year and dol.month < invoice_date.month):
                msg = f"Trainee separated in a prior calendar month ({dol.strftime('%B %Y')}). Invoice month is {invoice_date.strftime('%B %Y')}. Reimbursement rejected."
                failures.append({
                    "rule_name": "Separated before invoice",
                    "status": "ERROR",
                    "message": msg,
                    "reason_code": "SEP_BEFORE_INVOICE",
                    "recommended_action": "Reject invoice payouts. Employee has separated prior to this billing cycle."
                })
                new_joining = 0.0
                new_180 = 0.0
            
            # 2. Invoice after separation: invoice_date is strictly after dol (e.g. within same month but after dol)
            elif invoice_date > dol:
                msg = f"Billing date ({invoice_date.strftime('%Y-%m-%d')}) is after trainee's Date of Leaving ({dol.strftime('%Y-%m-%d')})."
                failures.append({
                    "rule_name": "Invoice after separation",
                    "status": "ERROR",
                    "message": msg,
                    "reason_code": "INVOICE_AFTER_SEPARATION",
                    "recommended_action": "Verify date of leaving. Do not approve payouts for claims submitted post-separation date."
                })
                new_joining = 0.0
                new_180 = 0.0

        if failures:
            rejected_j = current_joining - new_joining
            rejected_180 = current_180 - new_180
            return RuleResult(
                passed=False,
                severity="ERROR",
                reason="; ".join(f["message"] for f in failures),
                approved_amount=new_joining + new_180,
                rejected_amount=rejected_j + rejected_180,
                approved_joining=new_joining,
                approved_180=new_180,
                rejected_joining=rejected_j,
                rejected_180=rejected_180,
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

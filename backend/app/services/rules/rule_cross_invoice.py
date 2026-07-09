from typing import Optional, Dict, Any, List
from backend.app.services.rules.base import BaseRule, RuleResult

class RuleCrossInvoice(BaseRule):
    @property
    def name(self) -> str:
        return "Cross Invoice Validation"

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
        
        # Get historical items for this trainee
        hist_items = state.get("historical_items_map", {}).get(trainee.id, [])
        
        # Current details
        cur_joining_billed = record.billed_joining_amount > 0
        cur_180_billed = record.billed_180_days_amount > 0
        cur_dist_date = record.distribution_date
        cur_shirt_count = getattr(record, "shirt_count", 0) or 0
        cur_jeans_count = getattr(record, "jeans_count", 0) or 0
        
        for item in hist_items:
            # Skip checking against items of the current invoice number (though they shouldn't be in hist_items)
            if item.invoice_number == record.invoice_number:
                continue

            # 1. Duplicate Employee Billing & Repeated Monthly Billing Check
            if cur_joining_billed and (item.billed_joining_amount > 0 or item.approved_joining_amount > 0):
                msg = f"Repeated Monthly Billing / Duplicate Employee Billing: Trainee '{trainee.id}' was already billed for Joining stage in Invoice '{item.invoice_number}'."
                reasons.append(msg)
                failures.append({
                    "rule_name": "Repeated Monthly Billing",
                    "status": "FRAUD",
                    "message": msg,
                    "reason_code": "REPEATED_MONTHLY_BILLING",
                    "recommended_action": "Reject duplicate joining claim. Trainee was already billed in another monthly invoice."
                })
                
            if cur_180_billed and (item.billed_180_days_amount > 0 or item.approved_180_days_amount > 0):
                msg = f"Repeated Monthly Billing / Duplicate Employee Billing: Trainee '{trainee.id}' was already billed for 180-Days stage in Invoice '{item.invoice_number}'."
                reasons.append(msg)
                failures.append({
                    "rule_name": "Repeated Monthly Billing",
                    "status": "FRAUD",
                    "message": msg,
                    "reason_code": "REPEATED_MONTHLY_BILLING",
                    "recommended_action": "Reject duplicate 180-days claim. Trainee was already billed in another monthly invoice."
                })

            # 2. Duplicate Distribution Date
            if cur_dist_date and item.distribution_date:
                if cur_dist_date == item.distribution_date:
                    msg = f"Duplicate Distribution Date: Trainee '{trainee.id}' has another claim with distribution date '{cur_dist_date}' under Invoice '{item.invoice_number}'."
                    reasons.append(msg)
                    failures.append({
                        "rule_name": "Duplicate Distribution Date",
                        "status": "FRAUD",
                        "message": msg,
                        "reason_code": "DUP_DISTRIBUTION_DATE",
                        "recommended_action": "Reject claim. Same distribution date claimed repeatedly across invoices."
                    })

            # 3. Duplicate Kit Claim Check (exceeding kit limits historically)
            hist_shirts = item.shirt_count or 0
            hist_jeans = item.jeans_count or 0
            if (cur_shirt_count > 0 or cur_jeans_count > 0) and (hist_shirts > 0 or hist_jeans > 0):
                # If they have already received uniforms in the past and are claiming more parts
                msg = f"Duplicate Kit Claim: Trainee '{trainee.id}' already received kit garments historically (Shirts: {hist_shirts}, Jeans: {hist_jeans}) under Invoice '{item.invoice_number}'."
                reasons.append(msg)
                failures.append({
                    "rule_name": "Duplicate Kit Claim",
                    "status": "FRAUD",
                    "message": msg,
                    "reason_code": "DUP_KIT_CLAIM",
                    "recommended_action": "Reject kit claim. Candidate already received garments in a prior billing cycle."
                })

        if failures:
            # If there's any cross-invoice billing fraud detected, reject the current claim amounts
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
                stop_processing=True, # Stop processing further rules
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

from typing import Optional, Dict, Any, List
from backend.app.services.rules.base import BaseRule, RuleResult

class RuleKitLimit(BaseRule):
    @property
    def name(self) -> str:
        return "Excess Items Ignored"

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
        shirt_qty = 0.0
        jean_qty = 0.0
        extra_data = getattr(record, "extra_data", None)
        if extra_data and isinstance(extra_data, dict):
            try:
                shirt_qty = float(extra_data.get("shirt_quantity") or 0.0)
            except Exception:
                pass
            try:
                jean_qty = float(extra_data.get("jean_quantity") or 0.0)
            except Exception:
                pass

        # Updated limits: 3 Shirts, 3 Jeans (maximum approvable quantity)
        max_shirts = config.get("max_shirts", 3.0)
        max_jeans = config.get("max_jeans", 3.0)
        
        # Threshold limits: If invoice claims exceed these, flag and approve only ₹1200
        invoice_threshold_shirts = config.get("invoice_threshold_shirts", 5.0)
        invoice_threshold_jeans = config.get("invoice_threshold_jeans", 4.0)
        kit_approval_cap = config.get("kit_approval_cap", 1200.0)

        failures = []
        rejected_amt = 0.0
        approved_amt = current_joining + current_180

        # Check if vendor billed for excess items (uniform/jeans/shirts)
        if record.billed_other_amount > 0:
            msg = f"Vendor billed ₹{record.billed_other_amount} for other items (uniform/jeans/shirts), which is ignored/rejected per policy."
            failures.append({
                "rule_name": "Excess Items Ignored",
                "status": "WARNING",
                "message": msg,
                "reason_code": "KIT_OTHER_ITEMS",
                "recommended_action": "Deduct/reject excess garment charges. Kit limits are capped at 3 shirts and 3 jeans."
            })
            rejected_amt += record.billed_other_amount

        # Check if quantities exceed thresholds (invoice claims more than allowed)
        excess_shirts = max(0.0, shirt_qty - invoice_threshold_shirts)
        excess_jeans = max(0.0, jean_qty - invoice_threshold_jeans)
        
        if excess_shirts > 0 or excess_jeans > 0:
            msg = f"Excess kit quantity flagged: Invoice claims {int(shirt_qty)} shirts, {int(jean_qty)} jeans. Threshold: {int(invoice_threshold_shirts)} shirts, {int(invoice_threshold_jeans)} jeans."
            failures.append({
                "rule_name": "Excess Kit Quantity",
                "status": "WARNING",
                "message": msg,
                "reason_code": "KIT_EXCESS_THRESHOLD",
                "recommended_action": f"Flag for review. Approve only up to ₹{kit_approval_cap}. Excess: {int(excess_shirts)} shirts, {int(excess_jeans)} jeans."
            })
            # Cap approval at ₹1200 for excess kit claims
            approved_amt = min(approved_amt, kit_approval_cap)
        
        # Check if approved quantities exceed maximum approvable
        elif shirt_qty > max_shirts or jean_qty > max_jeans:
            msg = f"Excess kit quantity: Kit quantity exceeds maximum: {int(shirt_qty)} shirts, {int(jean_qty)} jeans. Maximum approvable: {int(max_shirts)} shirts, {int(max_jeans)} jeans."
            failures.append({
                "rule_name": "Kit Quantity Over Limit",
                "status": "WARNING",
                "message": msg,
                "reason_code": "KIT_QTY_MISMATCH",
                "recommended_action": "Approve only quantities within limits: max 3 shirts and 3 jeans."
            })

        app_joining = current_joining
        app_180 = current_180
        if approved_amt < current_joining + current_180:
            if current_joining > approved_amt:
                app_joining = approved_amt
                app_180 = 0.0
            else:
                app_180 = max(0.0, approved_amt - current_joining)

        rejected_j = current_joining - app_joining
        rejected_180 = current_180 - app_180
        total_rejected = rejected_j + rejected_180 + (record.billed_other_amount if record.billed_other_amount > 0 else 0.0)

        if failures:
            return RuleResult(
                passed=False,
                severity="WARNING",
                reason="; ".join(f["message"] for f in failures),
                approved_amount=approved_amt,
                rejected_amount=total_rejected,
                approved_joining=app_joining,
                approved_180=app_180,
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

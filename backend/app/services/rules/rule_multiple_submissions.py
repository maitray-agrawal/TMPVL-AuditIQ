from typing import Optional, Dict, Any, List
from backend.app.services.rules.base import BaseRule, RuleResult

class RuleMultipleSubmissions(BaseRule):
    @property
    def name(self) -> str:
        return "Multiple Invoice Submission"

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

        invoice_history = state.get("invoice_history_map", {}).get(trainee.id, [])
        if not invoice_history:
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
        # Check rule 15: Multiple invoice submission (different invoice numbers)
        other_invoice_numbers = {h["invoice_number"] for h in invoice_history if h["invoice_number"] != record.invoice_number}
        if other_invoice_numbers:
            msg1 = f"Multiple invoice submission detected: Trainee '{trainee.id}' was previously billed in invoice(s): {', '.join(other_invoice_numbers)}."
            failures.append({
                "rule_name": "Multiple Invoice Submission",
                "status": "FRAUD",
                "message": msg1,
                "reason_code": "MULTIPLE_INVOICES",
                "recommended_action": "Investigate duplicate invoice submissions for the same trainee across different billing cycles."
            })

        # Check rule 16: Duplicate invoice in same month
        if record.invoice_date:
            curr_month_year = (record.invoice_date.year, record.invoice_date.month)
            same_month_invoices = []
            for h in invoice_history:
                h_date = h["invoice_date"]
                if h_date and h["invoice_number"] != record.invoice_number:
                    if (h_date.year, h_date.month) == curr_month_year:
                        same_month_invoices.append(h["invoice_number"])
            if same_month_invoices:
                msg2 = f"Duplicate invoice in same month: Trainee '{trainee.id}' was already billed in another invoice for the same month in invoice(s): {', '.join(same_month_invoices)}."
                failures.append({
                    "rule_name": "Duplicate Invoice in Same Month",
                    "status": "FRAUD",
                    "message": msg2,
                    "reason_code": "DUP_INVOICE_SAME_MONTH",
                    "recommended_action": "Reject duplicate billing for the same trainee within the same calendar month."
                })

        if failures:
            # Reject approved amount if it is multiple invoice submission / duplicate same month
            return RuleResult(
                passed=False,
                severity="FRAUD",
                reason="; ".join(f["message"] for f in failures),
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

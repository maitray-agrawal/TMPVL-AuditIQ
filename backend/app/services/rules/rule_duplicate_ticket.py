from typing import Optional, Dict, Any, List
from backend.app.services.rules.base import BaseRule, RuleResult

class RuleDuplicateTicket(BaseRule):
    @property
    def name(self) -> str:
        return "Duplicate Ticket Number"

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
        if not trainee or not trainee.ticket_number:
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

        ticket = trainee.ticket_number.strip()
        seen_tickets = state.setdefault("seen_tickets", {})
        db_tickets = state.get("db_tickets", {})

        # 1. Check duplicate within the same invoice
        if ticket in seen_tickets and seen_tickets[ticket] != trainee.id:
            msg = f"Duplicate ticket: Ticket '{ticket}' belongs to multiple trainees in same invoice ('{seen_tickets[ticket]}' and '{trainee.id}')."
            failures = [{
                "rule_name": "Duplicate Ticket Number",
                "status": "FRAUD",
                "message": msg,
                "reason_code": "DUP_TICKET",
                "recommended_action": "Block employee payouts, investigate vendor billing data for ticketing abnormalities."
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
        seen_tickets[ticket] = trainee.id

        # 2. Check duplicate against other trainees in database
        if ticket in db_tickets and db_tickets[ticket] != trainee.id:
            msg = f"Duplicate ticket: Ticket '{ticket}' already belongs to another trainee '{db_tickets[ticket]}' in database."
            failures = [{
                "rule_name": "Duplicate Ticket Number",
                "status": "FRAUD",
                "message": msg,
                "reason_code": "DUP_TICKET",
                "recommended_action": "Block employee payouts, investigate vendor billing data for ticketing abnormalities."
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

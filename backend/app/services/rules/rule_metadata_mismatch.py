import re
import difflib
from typing import Optional, Dict, Any, List
from backend.app.services.rules.base import BaseRule, RuleResult

class RuleMetadataMismatch(BaseRule):
    @property
    def name(self) -> str:
        return "Metadata Mismatch"

    def _clean_name(self, name: str) -> str:
        if not name:
            return ""
        return re.sub(r'[^a-z0-9]', '', name.lower())

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

        # 1. Batch Mismatch Check
        inv_batch = record.batch
        master_batch = trainee.batch
        if inv_batch and master_batch:
            # Normalize batch strings (e.g. remove spaces, lower case)
            clean_inv = str(inv_batch).strip().lower().replace(" ", "")
            clean_master = str(master_batch).strip().lower().replace(" ", "")
            if clean_inv != clean_master:
                msg = f"Batch Mismatch: Invoice batch '{inv_batch}' differs from master batch '{master_batch}'."
                reasons.append(msg)
                failures.append({
                    "rule_name": "Batch Mismatch",
                    "status": "WARNING",
                    "message": msg,
                    "reason_code": "BATCH_MISMATCH",
                    "recommended_action": "Flag for vendor clarification. Verify if trainee shifted batches."
                })

        # 2. DOJ Mismatch Check
        inv_doj = record.joining_date
        master_doj = trainee.doj
        if inv_doj and master_doj:
            if inv_doj != master_doj:
                msg = f"Joining Date Mismatch: Invoice DOJ '{inv_doj}' differs from master DOJ '{master_doj}'."
                reasons.append(msg)
                failures.append({
                    "rule_name": "Joining Date Mismatch",
                    "status": "WARNING",
                    "message": msg,
                    "reason_code": "DOJ_MISMATCH",
                    "recommended_action": "Flag for review. Check whether candidate joining date was updated."
                })

        # 3. Name Mismatch Check
        billed_name = record.candidate_name
        master_name = trainee.name
        if billed_name and master_name:
            clean_billed = self._clean_name(billed_name)
            clean_master = self._clean_name(master_name)
            
            # Using SequenceMatcher to get similarity
            similarity = difflib.SequenceMatcher(None, clean_billed, clean_master).ratio()
            if similarity < 0.8:
                msg = f"Name Mismatch: Billed candidate name '{billed_name}' differs significantly from master name '{master_name}' (similarity: {similarity * 100:.1f}%)."
                reasons.append(msg)
                failures.append({
                    "rule_name": "Name Mismatch",
                    "status": "WARNING",
                    "message": msg,
                    "reason_code": "NAME_MISMATCH",
                    "recommended_action": "Flag for verification. Check Aadhaar or Ticket to confirm candidate identity."
                })

        if failures:
            return RuleResult(
                passed=False,
                severity="WARNING",
                reason="; ".join(reasons),
                approved_amount=current_joining + current_180,
                rejected_amount=0.0,
                approved_joining=current_joining,
                approved_180=current_180,
                rejected_joining=0.0,
                rejected_180=0.0,
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

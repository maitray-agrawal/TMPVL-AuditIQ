from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod

class RuleResult:
    def __init__(
        self,
        passed: bool,
        severity: Optional[str],  # "WARNING", "ERROR", "FRAUD", or None
        reason: str,
        approved_amount: float,    # total approved
        rejected_amount: float,    # total rejected
        approved_joining: float = 0.0,
        approved_180: float = 0.0,
        rejected_joining: float = 0.0,
        rejected_180: float = 0.0,
        stop_processing: bool = False,
        failures: Optional[List[Dict[str, Any]]] = None
    ):
        self.passed = passed
        self.severity = severity
        self.reason = reason
        self.approved_amount = approved_amount
        self.rejected_amount = rejected_amount
        self.approved_joining = approved_joining
        self.approved_180 = approved_180
        self.rejected_joining = rejected_joining
        self.rejected_180 = rejected_180
        self.stop_processing = stop_processing
        self.failures = failures or []

class BaseRule(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
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
        pass

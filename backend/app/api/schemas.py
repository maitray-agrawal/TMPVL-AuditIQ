"""
Pydantic request/response schemas for the TMPVL Billing Audit API.
Centralising schemas here keeps endpoint signatures clean and enables
automatic OpenAPI documentation and input validation.
"""
from pydantic import BaseModel, Field
from typing import Optional


class BlockTraineeRequest(BaseModel):
    """Body for POST /trainees/{id}/block"""
    reason: str = Field(
        default="Manually blocked by admin",
        min_length=3,
        max_length=500,
        description="Human-readable reason for flagging this trainee."
    )


class SettingsPayload(BaseModel):
    """Body for POST /settings — all policy thresholds."""
    joining_payment_max: float = Field(
        default=1200.0, gt=0,
        description="Maximum joining stipend payable per trainee (₹)."
    )
    days180_payment_max: float = Field(
        default=600.0, gt=0,
        description="Maximum 180-day completion stipend payable per trainee (₹)."
    )
    max_payable_per_trainee: float = Field(
        default=1800.0, gt=0,
        description="Absolute lifetime cap per trainee across all invoices (₹)."
    )
    min_days_reimbursement: int = Field(
        default=30, ge=1,
        description="Minimum days of tenure required before any reimbursement is eligible."
    )

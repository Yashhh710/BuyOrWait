"""
models.py
Pydantic models used for request validation (incoming purchase data)
and response validation (the structured AI decision).
"""

from datetime import date

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal


class PurchaseAnalysisRequest(BaseModel):
    """Payload sent from the frontend when the user clicks 'Analyze with AI'."""

    request_id: Optional[str] = None
    product_name: str = Field("Official dataset request", min_length=1, max_length=200)
    product_price: float = Field(0, ge=0)
    available_balance: float = Field(0, ge=0)
    monthly_income: float = Field(0, ge=0)
    monthly_expenses: float = Field(0, ge=0)
    savings: float = Field(0, ge=0)
    existing_commitments: float = Field(0, ge=0)
    can_reduce_spending: Optional[bool] = False
    currency: str = Field("₹", max_length=10)

    @field_validator("product_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


# The five allowed recommendation actions, as required by the spec.
RecommendationType = Literal[
    "PAY_IN_FULL",
    "PAY_PARTIALLY",
    "USE_INSTALLMENTS",
    "WAIT",
    "DO_NOT_PROCEED",
]

RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
PaymentStrategy = Literal["PAY_IN_FULL", "PAY_PARTIALLY", "SAVE_AND_BUY", "USE_INSTALLMENTS", "WAIT"]


class AIDecision(BaseModel):
    """
    The structured JSON contract the AI must return.
    We validate the raw AI output against this model before it is
    ever sent back to the frontend - if the AI returns malformed
    or out-of-range data, this will raise and trigger our fallback
    rule-based engine instead.
    """

    recommendation: RecommendationType
    confidence: int = Field(..., ge=0, le=100)
    risk_level: RiskLevel
    reasoning: str = Field(..., min_length=1)
    financial_impact: str = Field(..., min_length=1)
    months_to_wait: int = Field(..., ge=0, le=120)
    recommended_purchase_date: str = Field(..., min_length=10)
    monthly_saving_target: float = Field(..., ge=0)
    payment_strategy: PaymentStrategy
    next_step: str = Field(..., min_length=1)

    @field_validator("recommended_purchase_date")
    @classmethod
    def validate_purchase_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("recommended_purchase_date must use YYYY-MM-DD format") from exc
        return value


class HealthResponse(BaseModel):
    status: str
    csv_loaded: bool
    total_requests: int
    ai_provider_configured: bool

from __future__ import annotations

from pydantic import BaseModel, Field


class SavingsKpi(BaseModel):
    total_estimated_savings_krw: float = Field(ge=0)
    campaigns_with_calculable_savings: int = Field(ge=0)
    campaigns_missing_actual_spend: int = Field(ge=0)

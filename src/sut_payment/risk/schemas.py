from __future__ import annotations

from pydantic import BaseModel, Field


class RiskSummaryKpi(BaseModel):
    at_risk_campaign_count: int = Field(ge=0)
    high_risk_campaign_count: int = Field(ge=0)

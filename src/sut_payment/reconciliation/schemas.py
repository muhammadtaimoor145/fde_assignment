from __future__ import annotations

from pydantic import BaseModel


class ReconciliationKpis(BaseModel):
    under_settled_campaign_count: int
    total_unresolved_sut_gap: float
    average_settlement_coverage_ratio: float

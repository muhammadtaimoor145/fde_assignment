from __future__ import annotations

from pydantic import BaseModel, Field


class DataQualityIssue(BaseModel):
    dataset: str
    record_key: str
    issue_type: str
    action_taken: str


class CleanedDataBundle(BaseModel):
    partners_clean_count: int = Field(ge=0)
    campaigns_clean_count: int = Field(ge=0)
    wallets_clean_count: int = Field(ge=0)
    transactions_clean_count: int = Field(ge=0)
    balances_clean_count: int = Field(ge=0)
    issue_count: int = Field(ge=0)

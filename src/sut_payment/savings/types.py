from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class SavingsOutput:
    campaign_savings: pd.DataFrame
    partner_savings: pd.DataFrame
    savings_kpis: pd.DataFrame

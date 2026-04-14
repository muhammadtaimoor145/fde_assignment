from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RiskOutput:
    top_risky_campaigns: pd.DataFrame
    risk_distribution: pd.DataFrame

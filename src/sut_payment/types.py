from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class CleanOutput:
    partners_clean: pd.DataFrame
    campaigns_clean: pd.DataFrame
    wallets_clean: pd.DataFrame
    transactions_clean: pd.DataFrame
    balances_clean: pd.DataFrame
    data_quality_issues: pd.DataFrame
    data_quality_summary: pd.DataFrame

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ReconciliationOutput:
    reconciliation_table: pd.DataFrame
    reconciliation_kpis: pd.DataFrame

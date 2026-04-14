from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class SavingsStrategy(ABC):
    @abstractmethod
    def compute(self, actual_spend: pd.Series, discount_rate: pd.Series) -> pd.Series:
        """Compute campaign savings."""


class ActualSpendDiscountStrategy(SavingsStrategy):
    def compute(self, actual_spend: pd.Series, discount_rate: pd.Series) -> pd.Series:
        return actual_spend * discount_rate

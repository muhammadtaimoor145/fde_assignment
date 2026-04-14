from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from .models import DataQualityIssue


def issue(
    dataset: str,
    record_key: str,
    issue_type: str,
    action_taken: str,
) -> DataQualityIssue:
    return DataQualityIssue(
        dataset=dataset,
        record_key=record_key,
        issue_type=issue_type,
        action_taken=action_taken,
    )


def issues_to_df(issues: Iterable[DataQualityIssue]) -> pd.DataFrame:
    rows = [item.model_dump() for item in issues]
    return pd.DataFrame(rows, columns=["dataset", "record_key", "issue_type", "action_taken"])


def summarize_issues(issues_df: pd.DataFrame) -> pd.DataFrame:
    if issues_df.empty:
        return pd.DataFrame([{"dataset": "none", "issue_type": "none", "count": 0}])
    return (
        issues_df.groupby(["dataset", "issue_type"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["dataset", "count"], ascending=[True, False])
    )

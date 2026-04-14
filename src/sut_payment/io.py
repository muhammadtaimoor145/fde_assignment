from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def load_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return pd.DataFrame(rows)

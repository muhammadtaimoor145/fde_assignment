from __future__ import annotations

import re

WALLET_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")
VALID_TX_STATUSES = {"confirmed", "pending", "failed"}


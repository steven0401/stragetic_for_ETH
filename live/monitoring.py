from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd

import config

DAILY_SIGNAL_CSV = config.STORAGE_LIVE / "daily_trade_prob_history.csv"
EQUITY_CSV = config.STORAGE_LIVE / "equity_history.csv"
TRADE_LEDGER_FILE = config.STORAGE_LIVE / "bybit_trade_ledger.json"
TRADE_STATE_FILE = config.STORAGE_LIVE / "bybit_active_positions.json"


def append_daily_signal(result: dict[str, Any], csv_path: Path = DAILY_SIGNAL_CSV) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow([
                "timestamp",
                "symbol",
                "probability",
                "threshold",
                "signal",
                "close",
                "bull_score",
                "risk_score",
            ])
        writer.writerow([
            result["timestamp"],
            result["symbol"],
            result["probability"],
            result["threshold"],
            result["signal"],
            result["close"],
            result["literature_bull_score"],
            result["literature_long_risk_score"],
        ])


def append_equity_snapshot(
    timestamp: pd.Timestamp,
    equity: Any,
    source: str,
    csv_path: Path = EQUITY_CSV,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["timestamp", "equity", "source"])
        writer.writerow([timestamp.isoformat(), str(equity), source])


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def read_csv_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        df = pd.read_csv(path)
        return df.tail(500).to_dict(orient="records")
    except Exception:
        return []

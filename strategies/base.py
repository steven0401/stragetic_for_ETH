from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd


@dataclass(frozen=True)
class StrategyContext:
    symbol: str
    df: pd.DataFrame
    feature_cols: list[str]
    models_dir: Path
    backtest_dir: Path
    initial_equity: float
    default_risk_pct: float
    default_max_concurrent: int
    fee_pct: float
    bars_per_year: float = 8760.0


def load_fold_models(models_dir: Path, symbol: str, target: str) -> list:
    fold_paths = [Path(models_dir) / f"{symbol}_{target}_fold{k}.pkl" for k in range(1, 6)]
    missing = [p for p in fold_paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"[{symbol}][{target}] Missing fold models: {missing}. Run Phase 3 first.")
    return [joblib.load(p) for p in fold_paths]


class Strategy(ABC):
    """Replaceable strategy module between prepared data and backtest engine."""

    name: str
    description: str

    @abstractmethod
    def run(self, context: StrategyContext) -> dict:
        """Run this strategy against the prepared feature matrix."""

    @abstractmethod
    def save(self, context: StrategyContext, results: dict) -> None:
        """Persist reports/charts for this strategy."""

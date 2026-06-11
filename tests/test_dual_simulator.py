import numpy as np
import pandas as pd

from backtest.dual_simulator import build_dual_signal_trades, run_dual_portfolio_simulation


class _ConstantModel:
    def __init__(self, p: float):
        self.p = p

    def predict_proba(self, X):
        n = len(X)
        return np.column_stack([np.full(n, 1 - self.p), np.full(n, self.p)])


def _make_df(n: int = 300, close: float = 1000.0) -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": pd.date_range("2022-01-01", periods=n, freq="1h"),
        "open": close,
        "high": close * 1.005,
        "low": close * 0.995,
        "close": close,
        "volume": 1.0,
        "atr_14": close * 0.01,
    })


def test_dual_signals_skip_ambiguous_probabilities():
    df = _make_df(300)
    long_models = [_ConstantModel(0.80)] * 5
    short_models = [_ConstantModel(0.78)] * 5

    trades, stats = build_dual_signal_trades(
        df,
        [],
        long_models,
        short_models,
        long_target="target_fixed",
        short_target="target_fixed_short",
        long_threshold=0.75,
        short_threshold=0.75,
        direction_margin=0.05,
    )

    assert len(trades) == 0
    assert stats["ambiguous_signals"] > 0
    assert stats["long_signals"] == 0
    assert stats["short_signals"] == 0


def test_dual_signals_choose_long_when_prob_edge_is_large_enough():
    df = _make_df(300)
    long_models = [_ConstantModel(0.82)] * 5
    short_models = [_ConstantModel(0.75)] * 5

    trades, stats = build_dual_signal_trades(
        df,
        [],
        long_models,
        short_models,
        long_target="target_fixed",
        short_target="target_fixed_short",
        long_threshold=0.75,
        short_threshold=0.75,
        direction_margin=0.05,
    )

    assert len(trades) > 0
    assert set(trades["side"]) == {"long"}
    assert stats["long_signals"] > 0
    assert stats["short_signals"] == 0


def test_dual_portfolio_counts_short_trades():
    df = _make_df(300)
    # Make short trades hit TP quickly: future lows below fixed short TP=980.
    df.loc[1:, "low"] = 970.0
    long_models = [_ConstantModel(0.70)] * 5
    short_models = [_ConstantModel(0.82)] * 5

    results = run_dual_portfolio_simulation(
        df,
        [],
        long_models,
        short_models,
        long_target="target_fixed",
        short_target="target_fixed_short",
        long_threshold=0.75,
        short_threshold=0.75,
        direction_margin=0.05,
        initial_equity=100_000,
        risk_pct=0.02,
        max_concurrent=2,
    )

    assert results["executed_trades"] > 0
    assert results["side_metrics"]["long"]["trades"] == 0
    assert results["side_metrics"]["short"]["trades"] > 0
    assert results["final_equity"] > 100_000

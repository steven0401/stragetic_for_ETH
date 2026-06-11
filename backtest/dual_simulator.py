import numpy as np
import pandas as pd

from backtest.engine import compute_trade_pnl, generate_oof_probabilities


def build_dual_signal_trades(
    df: pd.DataFrame,
    feature_cols: list,
    long_fold_models: list,
    short_fold_models: list,
    long_target: str = "target_atr",
    short_target: str = "target_atr_short",
    long_threshold: float = 0.75,
    short_threshold: float = 0.75,
    direction_margin: float = 0.05,
    fee: float = 0.002,
) -> tuple[pd.DataFrame, dict]:
    """Build one-sided long/short candidate trades from competing OOF probabilities.

    A bar can emit at most one signal. Long wins only when it clears its threshold
    and beats short_prob by direction_margin; short follows the symmetric rule.
    """
    long_proba = generate_oof_probabilities(df, feature_cols, long_fold_models)
    short_proba = generate_oof_probabilities(df, feature_cols, short_fold_models)

    long_indices = []
    short_indices = []
    ambiguous = 0
    inactive = 0

    valid_mask = long_proba.notna() & short_proba.notna()
    for idx in np.where(valid_mask.to_numpy())[0]:
        lp = float(long_proba.iloc[idx])
        sp = float(short_proba.iloc[idx])
        long_ok = lp >= long_threshold and lp >= sp + direction_margin
        short_ok = sp >= short_threshold and sp >= lp + direction_margin

        if long_ok and not short_ok:
            long_indices.append(idx)
        elif short_ok and not long_ok:
            short_indices.append(idx)
        elif lp >= long_threshold or sp >= short_threshold:
            ambiguous += 1
        else:
            inactive += 1

    long_trades = compute_trade_pnl(df, long_indices, long_target, fee=fee)
    short_trades = compute_trade_pnl(df, short_indices, short_target, fee=fee)
    trades = pd.concat([long_trades, short_trades], ignore_index=True)
    if len(trades):
        trades = trades.sort_values("entry_idx").reset_index(drop=True)

    stats = {
        "valid_bars": int(valid_mask.sum()),
        "long_signals": len(long_indices),
        "short_signals": len(short_indices),
        "ambiguous_signals": ambiguous,
        "inactive_bars": inactive,
        "dropped_near_end": len(long_indices) + len(short_indices) - len(trades),
    }
    return trades, stats


def run_dual_portfolio_simulation(
    df: pd.DataFrame,
    feature_cols: list,
    long_fold_models: list,
    short_fold_models: list,
    long_target: str = "target_atr",
    short_target: str = "target_atr_short",
    long_threshold: float = 0.75,
    short_threshold: float = 0.75,
    direction_margin: float = 0.05,
    initial_equity: float = 1_000_000,
    risk_pct: float = 0.02,
    max_concurrent: int = 3,
    fee: float = 0.002,
) -> dict:
    """Event-driven portfolio simulation for a combined long/short strategy."""
    raw_trades_df, signal_stats = build_dual_signal_trades(
        df=df,
        feature_cols=feature_cols,
        long_fold_models=long_fold_models,
        short_fold_models=short_fold_models,
        long_target=long_target,
        short_target=short_target,
        long_threshold=long_threshold,
        short_threshold=short_threshold,
        direction_margin=direction_margin,
        fee=fee,
    )

    if len(raw_trades_df) == 0:
        return _empty_results(
            initial_equity=initial_equity,
            signal_stats=signal_stats,
            long_target=long_target,
            short_target=short_target,
            long_threshold=long_threshold,
            short_threshold=short_threshold,
            direction_margin=direction_margin,
            risk_pct=risk_pct,
            max_concurrent=max_concurrent,
        )

    raw_trades_df = raw_trades_df.copy()
    raw_trades_df["exit_bar"] = (
        raw_trades_df["entry_idx"] + raw_trades_df["holding_bars"]
    ).astype(int)
    raw_trades_df["atr_at_entry"] = (
        df["atr_14"].values[raw_trades_df["entry_idx"].values.astype(int)]
    )

    equity = float(initial_equity)
    open_slots = []
    closed_trades = []
    equity_log = []
    skipped = 0

    for row in raw_trades_df.itertuples(index=False):
        to_close = [t for t in open_slots if t["exit_bar"] <= row.entry_idx]
        to_close.sort(key=lambda t: t["exit_bar"])
        for t in to_close:
            equity += t["pnl_usd"]
            equity_log.append((t["exit_bar"], equity))
            closed_trades.append({**t, "trade_roe": t["pnl_usd"] / t["equity_at_entry"]})
        open_slots = [t for t in open_slots if t["exit_bar"] > row.entry_idx]

        if len(open_slots) >= max_concurrent:
            skipped += 1
            continue

        sl_distance = 1.5 * row.atr_at_entry
        if sl_distance <= 0:
            skipped += 1
            continue

        risk_budget = equity * risk_pct
        position_qty = risk_budget / sl_distance
        position_usd = position_qty * row.entry_price
        pnl_usd = position_usd * row.pnl

        open_slots.append({
            "entry_idx": row.entry_idx,
            "exit_bar": row.exit_bar,
            "timestamp": row.timestamp,
            "side": row.side,
            "outcome": row.outcome,
            "entry_price": row.entry_price,
            "exit_price": row.exit_price,
            "atr_at_entry": row.atr_at_entry,
            "sl_distance": sl_distance,
            "position_qty": position_qty,
            "position_usd": position_usd,
            "pnl_pct": row.pnl,
            "pnl_usd": pnl_usd,
            "equity_at_entry": equity,
        })

    for t in sorted(open_slots, key=lambda t: t["exit_bar"]):
        equity += t["pnl_usd"]
        equity_log.append((t["exit_bar"], equity))
        closed_trades.append({**t, "trade_roe": t["pnl_usd"] / t["equity_at_entry"]})

    metrics = _compute_metrics(closed_trades, equity_log, initial_equity, equity, len(df))
    side_metrics = _compute_side_metrics(closed_trades)

    return {
        "strategy": "dual_long_short",
        "closed_trades": closed_trades,
        "equity_log": equity_log,
        "final_equity": equity,
        "total_signals": len(raw_trades_df),
        "executed_trades": len(closed_trades),
        "skipped_signals": skipped,
        "signal_stats": signal_stats,
        "metrics": metrics,
        "side_metrics": side_metrics,
        "initial_equity": initial_equity,
        "risk_pct": risk_pct,
        "max_concurrent": max_concurrent,
        "long_target": long_target,
        "short_target": short_target,
        "long_threshold": long_threshold,
        "short_threshold": short_threshold,
        "direction_margin": direction_margin,
    }


def _compute_metrics(
    closed_trades: list,
    equity_log: list,
    initial_equity: float,
    final_equity: float,
    df_len: int,
) -> dict:
    if not closed_trades:
        return {}

    total_years = df_len / 8760.0
    n_trades = len(closed_trades)
    roe_arr = np.array([t["trade_roe"] for t in closed_trades])
    mean_roe = float(roe_arr.mean())
    std_roe = float(roe_arr.std(ddof=1))
    sharpe = float(mean_roe / std_roe * np.sqrt(n_trades / total_years)) if std_roe > 0 else 0.0

    equity_arr = np.array([initial_equity] + [e for _, e in equity_log])
    running_peak = np.maximum.accumulate(equity_arr)
    dd_arr = equity_arr - running_peak
    mdd_usd_val = float(dd_arr.min())
    peak_at_trough = running_peak[np.argmin(dd_arr)]
    mdd_pct = float(mdd_usd_val / peak_at_trough * 100) if peak_at_trough > 0 else 0.0

    total_return = final_equity / initial_equity
    cagr = (total_return ** (1.0 / total_years) - 1.0) * 100 if total_years > 0 else 0.0
    win_rate = float(sum(1 for t in closed_trades if t["pnl_usd"] > 0) / n_trades)

    return {
        "total_return_pct": round((total_return - 1) * 100, 4),
        "cagr_pct": round(cagr, 4),
        "sharpe_ratio": round(sharpe, 4),
        "max_drawdown_usd": round(mdd_usd_val, 2),
        "max_drawdown_pct": round(mdd_pct, 4),
        "win_rate": round(win_rate, 4),
        "avg_position_usd": round(float(np.mean([t["position_usd"] for t in closed_trades])), 2),
        "avg_holding_bars": round(float(np.mean([t["exit_bar"] - t["entry_idx"] for t in closed_trades])), 2),
    }


def _compute_side_metrics(closed_trades: list) -> dict:
    side_metrics = {}
    for side in ["long", "short"]:
        trades = [t for t in closed_trades if t["side"] == side]
        if not trades:
            side_metrics[side] = {"trades": 0}
            continue
        pnl = np.array([t["pnl_usd"] for t in trades])
        side_metrics[side] = {
            "trades": len(trades),
            "win_rate": round(float((pnl > 0).sum() / len(pnl)), 4),
            "pnl_usd": round(float(pnl.sum()), 2),
            "avg_pnl_usd": round(float(pnl.mean()), 2),
        }
    return side_metrics


def _empty_results(
    initial_equity: float,
    signal_stats: dict,
    long_target: str,
    short_target: str,
    long_threshold: float,
    short_threshold: float,
    direction_margin: float,
    risk_pct: float,
    max_concurrent: int,
) -> dict:
    return {
        "strategy": "dual_long_short",
        "closed_trades": [],
        "equity_log": [],
        "final_equity": initial_equity,
        "total_signals": 0,
        "executed_trades": 0,
        "skipped_signals": 0,
        "signal_stats": signal_stats,
        "metrics": {},
        "side_metrics": {"long": {"trades": 0}, "short": {"trades": 0}},
        "initial_equity": initial_equity,
        "risk_pct": risk_pct,
        "max_concurrent": max_concurrent,
        "long_target": long_target,
        "short_target": short_target,
        "long_threshold": long_threshold,
        "short_threshold": short_threshold,
        "direction_margin": direction_margin,
    }

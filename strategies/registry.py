from __future__ import annotations

import config
from strategies.dual_long_short import DualLongShortStrategy
from strategies.literature_long import LiteratureLongStrategy
from strategies.long_only import LongOnlyStrategy


STRATEGIES = {
    "eth_long_current": LongOnlyStrategy(
        name="eth_long_current",
        description="Current conservative ETH long-only ATR strategy.",
        target="target_atr",
        threshold=0.73,
        risk_pct=config.RISK_PCT,
        max_concurrent=config.MAX_CONCURRENT,
        report_suffix="long_current",
    ),
    "eth_long_balanced": LongOnlyStrategy(
        name="eth_long_balanced",
        description="Balanced ETH long-only profile; higher risk with controlled MDD.",
        target="target_atr",
        threshold=config.LONG_BALANCED_THRESHOLD,
        risk_pct=config.LONG_BALANCED_RISK_PCT,
        max_concurrent=config.LONG_BALANCED_MAX_CONCURRENT,
        report_suffix="long_balanced",
    ),
    "eth_long_target20": LongOnlyStrategy(
        name="eth_long_target20",
        description="Aggressive ETH long-only research profile targeting about 20% CAGR.",
        target="target_atr",
        threshold=config.LONG_TARGET20_THRESHOLD,
        risk_pct=config.LONG_TARGET20_RISK_PCT,
        max_concurrent=config.LONG_TARGET20_MAX_CONCURRENT,
        report_suffix="long_target20",
    ),
    "eth_dual_strict_short": DualLongShortStrategy(
        name="eth_dual_strict_short",
        description="Research-only combined long/short profile with stricter short threshold.",
        long_target="target_atr",
        short_target="target_atr_short",
        long_threshold=config.LONG_BALANCED_THRESHOLD,
        short_threshold=config.STRICT_SHORT_THRESHOLD_FLOOR,
        direction_margin=config.DUAL_DIRECTION_MARGIN,
        risk_pct=config.RISK_PCT,
        max_concurrent=config.MAX_CONCURRENT,
        report_name="dual_strict_short",
    ),
    "eth_literature_long": LiteratureLongStrategy(
        name="eth_literature_long",
        description="Literature-inspired long strategy using binary indicators, candlestick states, and multi-indicator confirmation.",
        target="target_atr",
        threshold=config.LITERATURE_LONG_THRESHOLD,
        risk_pct=config.LITERATURE_LONG_RISK_PCT,
        max_concurrent=config.LITERATURE_LONG_MAX_CONCURRENT,
        min_bull_score=config.LITERATURE_LONG_MIN_BULL_SCORE,
        max_risk_score=config.LITERATURE_LONG_MAX_RISK_SCORE,
        report_suffix="literature_long",
    ),
    "eth_literature_long_daily": LiteratureLongStrategy(
        name="eth_literature_long_daily",
        description="Daily-candle literature-inspired ETH long strategy with stricter risk-state confirmation.",
        target="target_atr",
        threshold=config.LITERATURE_LONG_DAILY_THRESHOLD,
        risk_pct=config.LITERATURE_LONG_DAILY_RISK_PCT,
        max_concurrent=config.LITERATURE_LONG_DAILY_MAX_CONCURRENT,
        min_bull_score=config.LITERATURE_LONG_DAILY_MIN_BULL_SCORE,
        max_risk_score=config.LITERATURE_LONG_DAILY_MAX_RISK_SCORE,
        report_suffix="literature_long_daily",
    ),
}


def get_strategy(name: str):
    try:
        return STRATEGIES[name]
    except KeyError as exc:
        available = ", ".join(sorted(STRATEGIES))
        raise KeyError(f"Unknown strategy '{name}'. Available: {available}") from exc

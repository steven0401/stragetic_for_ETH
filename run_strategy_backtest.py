import argparse
import json
import logging

import pandas as pd

import config
from strategies.base import StrategyContext
from strategies.registry import STRATEGIES, get_strategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _filter_model_features(feature_cols: list[str]) -> list[str]:
    excluded = set(getattr(config, "MODEL_FEATURE_EXCLUDE_COLUMNS", ()))
    prefixes = tuple(getattr(config, "MODEL_FEATURE_EXCLUDE_PREFIXES", ()))
    return [
        col for col in feature_cols
        if col not in excluded and not col.startswith(prefixes)
    ]


def _asset_name(symbol: str, timeframe: str) -> str:
    return symbol if timeframe == "1h" else f"{symbol}_{timeframe}"


def _load_feature_matrix(symbol: str, timeframe: str):
    asset_name = _asset_name(symbol, timeframe)
    feature_path = config.STORAGE_FEATURES / f"{asset_name}_features.parquet"
    report_path = config.STORAGE_FEATURES / f"{asset_name}_validation_report.json"
    if not feature_path.exists():
        raise FileNotFoundError(f"[{asset_name}] Features not found: {feature_path}. Run build_features.py first.")
    if not report_path.exists():
        raise FileNotFoundError(f"[{asset_name}] Validation report not found: {report_path}.")

    df = pd.read_parquet(feature_path)
    with open(report_path, encoding="utf-8") as f:
        feature_cols = _filter_model_features(json.load(f)["metadata"]["feature_columns"])
    return df, feature_cols


def _build_context(symbol: str, timeframe: str = "1h") -> StrategyContext:
    asset_name = _asset_name(symbol, timeframe)
    df, feature_cols = _load_feature_matrix(symbol, timeframe)
    return StrategyContext(
        symbol=asset_name,
        df=df,
        feature_cols=feature_cols,
        models_dir=config.STORAGE_MODELS,
        backtest_dir=config.STORAGE_BACKTEST,
        initial_equity=config.INITIAL_EQUITY,
        default_risk_pct=config.RISK_PCT,
        default_max_concurrent=config.MAX_CONCURRENT,
        fee_pct=config.FEE_PCT,
        bars_per_year=config.TIMEFRAME_TO_BARS_PER_YEAR[timeframe],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one replaceable strategy against the prepared feature matrix."
    )
    parser.add_argument(
        "--strategy",
        default="eth_long_balanced",
        choices=sorted(STRATEGIES),
        help="Strategy registered in strategies/registry.py.",
    )
    parser.add_argument(
        "--symbol",
        default="ETHUSDT",
        help="Symbol feature matrix to backtest.",
    )
    parser.add_argument(
        "--timeframe",
        choices=["1h", "4h", "1d"],
        default=config.DEFAULT_TIMEFRAME,
        help="Primary candle timeframe for features/models.",
    )
    args = parser.parse_args()

    strategy = get_strategy(args.strategy)
    context = _build_context(args.symbol, args.timeframe)

    logger.info(
        "[%s][%s] Running strategy: %s",
        context.symbol,
        strategy.name,
        strategy.description,
    )
    results = strategy.run(context)
    strategy.save(context, results)

    metrics = results.get("metrics", {})
    logger.info(
        "[%s][%s] final_equity=%0.0f total=%s%% CAGR=%s%% MDD=%s%% Sharpe=%s trades=%s",
        context.symbol,
        strategy.name,
        results.get("final_equity", 0),
        metrics.get("total_return_pct", "N/A"),
        metrics.get("cagr_pct", "N/A"),
        metrics.get("max_drawdown_pct", "N/A"),
        metrics.get("sharpe_ratio", "N/A"),
        results.get("executed_trades", "N/A"),
    )
    logger.info("[%s][%s] Reports saved to %s", context.symbol, strategy.name, context.backtest_dir)


if __name__ == "__main__":
    main()

import json
import logging

import joblib
import pandas as pd

import config
from backtest import reporter, simulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SYMBOL = "ETHUSDT"
TARGET = "target_atr"

PROFILES = [
    {
        "name": "long_balanced",
        "threshold": config.LONG_BALANCED_THRESHOLD,
        "risk_pct": config.LONG_BALANCED_RISK_PCT,
        "max_concurrent": config.LONG_BALANCED_MAX_CONCURRENT,
    },
    {
        "name": "long_target20",
        "threshold": config.LONG_TARGET20_THRESHOLD,
        "risk_pct": config.LONG_TARGET20_RISK_PCT,
        "max_concurrent": config.LONG_TARGET20_MAX_CONCURRENT,
    },
]


def _load_assets():
    feature_path = config.STORAGE_FEATURES / f"{SYMBOL}_features.parquet"
    report_path = config.STORAGE_FEATURES / f"{SYMBOL}_validation_report.json"
    if not feature_path.exists():
        raise FileNotFoundError(f"Features not found: {feature_path}. Run Phase 2 first.")
    if not report_path.exists():
        raise FileNotFoundError(f"Validation report not found: {report_path}.")

    df = pd.read_parquet(feature_path)
    with open(report_path, encoding="utf-8") as f:
        feature_cols = json.load(f)["metadata"]["feature_columns"]

    fold_paths = [config.STORAGE_MODELS / f"{SYMBOL}_{TARGET}_fold{k}.pkl" for k in range(1, 6)]
    missing = [p for p in fold_paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing fold models: {missing}. Run Phase 3 first.")

    fold_models = [joblib.load(p) for p in fold_paths]
    return df, feature_cols, fold_models


def main() -> None:
    config.STORAGE_BACKTEST.mkdir(parents=True, exist_ok=True)
    df, feature_cols, fold_models = _load_assets()

    for profile in PROFILES:
        logger.info(
            "[%s][%s] Running %s: threshold=%.2f risk=%.2f max_concurrent=%d",
            SYMBOL,
            TARGET,
            profile["name"],
            profile["threshold"],
            profile["risk_pct"],
            profile["max_concurrent"],
        )
        results = simulator.run_portfolio_simulation(
            df=df,
            feature_cols=feature_cols,
            fold_models=fold_models,
            target=TARGET,
            optimal_threshold=profile["threshold"],
            initial_equity=config.INITIAL_EQUITY,
            risk_pct=profile["risk_pct"],
            max_concurrent=profile["max_concurrent"],
        )
        metrics = results["metrics"]
        logger.info(
            "[%s] final_equity=%0.0f total=%s%% CAGR=%s%% MDD=%s%% Sharpe=%s trades=%s",
            profile["name"],
            results["final_equity"],
            metrics.get("total_return_pct", "N/A"),
            metrics.get("cagr_pct", "N/A"),
            metrics.get("max_drawdown_pct", "N/A"),
            metrics.get("sharpe_ratio", "N/A"),
            results["executed_trades"],
        )
        reporter.save_portfolio_report(
            results,
            SYMBOL,
            f"{TARGET}_{profile['name']}",
            config.STORAGE_BACKTEST,
        )
        reporter.save_portfolio_equity_curve(
            results,
            SYMBOL,
            f"{TARGET}_{profile['name']}",
            config.STORAGE_BACKTEST,
        )


if __name__ == "__main__":
    main()

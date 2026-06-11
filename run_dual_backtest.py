import json
import logging

import joblib
import pandas as pd

import config
from backtest import dual_simulator, reporter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

LONG_TARGET = "target_atr"
SHORT_TARGET = "target_atr_short"


def _load_fold_models(symbol: str, target: str):
    models_dir = config.STORAGE_MODELS
    fold_paths = [models_dir / f"{symbol}_{target}_fold{k}.pkl" for k in range(1, 6)]
    missing = [p for p in fold_paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"[{symbol}][{target}] Missing fold models: {missing}. Run Phase 3 first.")
    return [joblib.load(p) for p in fold_paths]


def _load_threshold(symbol: str, target: str) -> float:
    path = config.STORAGE_BACKTEST / f"{symbol}_{target}_threshold_scan.json"
    if not path.exists():
        raise FileNotFoundError(f"[{symbol}][{target}] Threshold scan not found: {path}. Run Phase 4.1 first.")
    with open(path, encoding="utf-8") as f:
        threshold = json.load(f)["optimal_threshold"]
    if threshold is None:
        raise ValueError(f"[{symbol}][{target}] optimal_threshold is None.")
    return float(threshold)


def _load_feature_matrix(symbol: str):
    feature_path = config.STORAGE_FEATURES / f"{symbol}_features.parquet"
    report_path = config.STORAGE_FEATURES / f"{symbol}_validation_report.json"
    if not feature_path.exists():
        raise FileNotFoundError(f"[{symbol}] Features not found: {feature_path}. Run Phase 2 first.")
    if not report_path.exists():
        raise FileNotFoundError(f"[{symbol}] Validation report not found: {report_path}.")

    df = pd.read_parquet(feature_path)
    with open(report_path, encoding="utf-8") as f:
        feature_cols = json.load(f)["metadata"]["feature_columns"]
    return df, feature_cols


def main() -> None:
    backtest_dir = config.STORAGE_BACKTEST
    backtest_dir.mkdir(parents=True, exist_ok=True)

    for symbol in config.LIVE_SYMBOLS:
        logger.info(f"[{symbol}] Loading feature matrix, thresholds, and long/short models...")
        try:
            df, feature_cols = _load_feature_matrix(symbol)
            long_models = _load_fold_models(symbol, LONG_TARGET)
            short_models = _load_fold_models(symbol, SHORT_TARGET)
            long_threshold = _load_threshold(symbol, LONG_TARGET)
            short_threshold = _load_threshold(symbol, SHORT_TARGET)
        except (FileNotFoundError, ValueError) as exc:
            logger.error(str(exc))
            continue

        logger.info(
            f"[{symbol}] Running dual backtest: "
            f"long_thr={long_threshold}, short_thr={short_threshold}, "
            f"margin={config.DUAL_DIRECTION_MARGIN}"
        )
        results = dual_simulator.run_dual_portfolio_simulation(
            df=df,
            feature_cols=feature_cols,
            long_fold_models=long_models,
            short_fold_models=short_models,
            long_target=LONG_TARGET,
            short_target=SHORT_TARGET,
            long_threshold=long_threshold,
            short_threshold=short_threshold,
            direction_margin=config.DUAL_DIRECTION_MARGIN,
            initial_equity=config.INITIAL_EQUITY,
            risk_pct=config.RISK_PCT,
            max_concurrent=config.MAX_CONCURRENT,
            fee=config.FEE_PCT / 100,
        )

        metrics = results["metrics"]
        side_metrics = results["side_metrics"]
        logger.info(
            f"[{symbol}] Dual result | "
            f"final_equity={results['final_equity']:,.0f} | "
            f"executed={results['executed_trades']} | "
            f"long={side_metrics.get('long', {}).get('trades', 0)} | "
            f"short={side_metrics.get('short', {}).get('trades', 0)} | "
            f"MDD={metrics.get('max_drawdown_pct', 'N/A')}% | "
            f"Sharpe={metrics.get('sharpe_ratio', 'N/A')}"
        )

        reporter.save_dual_portfolio_report(results, symbol, backtest_dir)
        reporter.save_dual_portfolio_equity_curve(results, symbol, backtest_dir)
        logger.info(f"[{symbol}] Dual outputs saved to {backtest_dir}")


if __name__ == "__main__":
    main()

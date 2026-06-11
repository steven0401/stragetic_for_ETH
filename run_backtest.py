import json
import logging
import argparse
import joblib
import pandas as pd

import config
from backtest import engine, reporter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _filter_model_features(feature_cols: list[str]) -> list[str]:
    excluded = set(getattr(config, "MODEL_FEATURE_EXCLUDE_COLUMNS", ()))
    prefixes = tuple(getattr(config, "MODEL_FEATURE_EXCLUDE_PREFIXES", ()))
    return [
        col for col in feature_cols
        if col not in excluded and not col.startswith(prefixes)
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeframe", choices=["1h", "4h", "1d"], default=config.DEFAULT_TIMEFRAME)
    args = parser.parse_args()
    suffix = "" if args.timeframe == "1h" else f"_{args.timeframe}"
    bars_per_year = config.TIMEFRAME_TO_BARS_PER_YEAR[args.timeframe]

    features_dir = config.STORAGE_FEATURES
    models_dir   = config.STORAGE_MODELS
    backtest_dir = config.STORAGE_BACKTEST
    backtest_dir.mkdir(parents=True, exist_ok=True)

    for symbol in config.SYMBOLS:
        asset_name = f"{symbol}{suffix}"
        feature_path = features_dir / f"{asset_name}_features.parquet"
        report_path  = features_dir / f"{asset_name}_validation_report.json"

        if not feature_path.exists():
            logger.error(f"Features not found: {feature_path}. Run Phase 2 first.")
            continue

        df = pd.read_parquet(feature_path)
        with open(report_path, encoding='utf-8') as f:
            feature_cols = _filter_model_features(json.load(f)["metadata"]["feature_columns"])

        for target in [
            "target_fixed",
            "target_atr",
            "target_fixed_short",
            "target_atr_short",
        ]:
            logger.info(f"[{asset_name}][{target}] Loading fold models...")
            fold_paths = [models_dir / f"{asset_name}_{target}_fold{k}.pkl" for k in range(1, 6)]
            missing = [p for p in fold_paths if not p.exists()]
            if missing:
                logger.error(f"[{asset_name}][{target}] Missing models: {missing}. Run Phase 3 first.")
                continue
            fold_models = [joblib.load(p) for p in fold_paths]

            logger.info(f"[{asset_name}][{target}] Running threshold scan...")
            results = engine.run_threshold_scan(
                df,
                feature_cols,
                fold_models,
                target,
                bars_per_year=bars_per_year,
            )
            opt = results['optimal_threshold']
            m   = results['optimal_metrics']
            logger.info(
                f"[{asset_name}][{target}] optimal_threshold={opt}, "
                f"n_trades={m['n_trades'] if m else 'N/A'}, "
                f"sharpe={m['sharpe_ratio'] if m else 'N/A'}"
            )

            reporter.save_threshold_scan(results, asset_name, target, backtest_dir)
            reporter.save_threshold_tradeoff_chart(results, asset_name, target, backtest_dir)
            reporter.save_equity_curve(results, asset_name, target, backtest_dir)
            logger.info(f"[{asset_name}][{target}] Saved to {backtest_dir}")


if __name__ == "__main__":
    main()

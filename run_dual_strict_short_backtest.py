import logging

import config
from backtest import dual_simulator, reporter
from run_dual_backtest import (
    LONG_TARGET,
    SHORT_TARGET,
    _load_feature_matrix,
    _load_fold_models,
    _load_threshold,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


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
            short_threshold = max(
                _load_threshold(symbol, SHORT_TARGET),
                config.STRICT_SHORT_THRESHOLD_FLOOR,
            )
        except (FileNotFoundError, ValueError) as exc:
            logger.error(str(exc))
            continue

        logger.info(
            f"[{symbol}] Running strict-short dual backtest: "
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
            f"[{symbol}] Strict-short dual result | "
            f"final_equity={results['final_equity']:,.0f} | "
            f"executed={results['executed_trades']} | "
            f"long={side_metrics.get('long', {}).get('trades', 0)} | "
            f"short={side_metrics.get('short', {}).get('trades', 0)} | "
            f"MDD={metrics.get('max_drawdown_pct', 'N/A')}% | "
            f"Sharpe={metrics.get('sharpe_ratio', 'N/A')}"
        )

        reporter.save_dual_portfolio_report(
            results, symbol, backtest_dir, name="dual_strict_short",
        )
        reporter.save_dual_portfolio_equity_curve(
            results, symbol, backtest_dir, name="dual_strict_short",
        )
        logger.info(f"[{symbol}] Strict-short dual outputs saved to {backtest_dir}")


if __name__ == "__main__":
    main()

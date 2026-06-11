from __future__ import annotations

from dataclasses import dataclass

from backtest import reporter, simulator
from strategies.base import Strategy, StrategyContext, load_fold_models


@dataclass(frozen=True)
class LiteratureLongStrategy(Strategy):
    name: str
    description: str
    target: str = "target_atr"
    threshold: float = 0.72
    risk_pct: float = 0.08
    max_concurrent: int = 2
    min_bull_score: int = 5
    max_risk_score: int = 1
    report_suffix: str = "literature_long"

    def run(self, context: StrategyContext) -> dict:
        required_cols = [
            "literature_bull_score",
            "literature_long_risk_score",
        ]
        missing = [c for c in required_cols if c not in context.df.columns]
        if missing:
            raise ValueError(
                f"Missing literature feature columns: {missing}. "
                "Run build_features.py after updating features/indicators.py."
            )

        signal_filter = (
            (context.df["literature_bull_score"] >= self.min_bull_score) &
            (context.df["literature_long_risk_score"] <= self.max_risk_score)
        )

        fold_models = load_fold_models(context.models_dir, context.symbol, self.target)
        return simulator.run_portfolio_simulation(
            df=context.df,
            feature_cols=context.feature_cols,
            fold_models=fold_models,
            target=self.target,
            optimal_threshold=self.threshold,
            initial_equity=context.initial_equity,
            risk_pct=self.risk_pct,
            max_concurrent=self.max_concurrent,
            signal_filter=signal_filter,
            bars_per_year=context.bars_per_year,
        )

    def save(self, context: StrategyContext, results: dict) -> None:
        output_target = f"{self.target}_{self.report_suffix}"
        reporter.save_portfolio_report(
            results,
            context.symbol,
            output_target,
            context.backtest_dir,
        )
        reporter.save_portfolio_equity_curve(
            results,
            context.symbol,
            output_target,
            context.backtest_dir,
        )

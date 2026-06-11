from __future__ import annotations

from dataclasses import dataclass

from backtest import reporter, simulator
from strategies.base import Strategy, StrategyContext, load_fold_models


@dataclass(frozen=True)
class LongOnlyStrategy(Strategy):
    name: str
    description: str
    target: str = "target_atr"
    threshold: float = 0.73
    risk_pct: float = 0.02
    max_concurrent: int = 3
    report_suffix: str = "long_only"

    def run(self, context: StrategyContext) -> dict:
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

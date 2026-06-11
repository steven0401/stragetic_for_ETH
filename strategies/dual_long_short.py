from __future__ import annotations

from dataclasses import dataclass

from backtest import dual_simulator, reporter
from strategies.base import Strategy, StrategyContext, load_fold_models


@dataclass(frozen=True)
class DualLongShortStrategy(Strategy):
    name: str
    description: str
    long_target: str = "target_atr"
    short_target: str = "target_atr_short"
    long_threshold: float = 0.73
    short_threshold: float = 0.80
    direction_margin: float = 0.05
    risk_pct: float = 0.02
    max_concurrent: int = 3
    report_name: str = "dual"

    def run(self, context: StrategyContext) -> dict:
        long_models = load_fold_models(context.models_dir, context.symbol, self.long_target)
        short_models = load_fold_models(context.models_dir, context.symbol, self.short_target)
        return dual_simulator.run_dual_portfolio_simulation(
            df=context.df,
            feature_cols=context.feature_cols,
            long_fold_models=long_models,
            short_fold_models=short_models,
            long_target=self.long_target,
            short_target=self.short_target,
            long_threshold=self.long_threshold,
            short_threshold=self.short_threshold,
            direction_margin=self.direction_margin,
            initial_equity=context.initial_equity,
            risk_pct=self.risk_pct,
            max_concurrent=self.max_concurrent,
            fee=context.fee_pct / 100,
        )

    def save(self, context: StrategyContext, results: dict) -> None:
        reporter.save_dual_portfolio_report(
            results,
            context.symbol,
            context.backtest_dir,
            name=self.report_name,
        )
        reporter.save_dual_portfolio_equity_curve(
            results,
            context.symbol,
            context.backtest_dir,
            name=self.report_name,
        )


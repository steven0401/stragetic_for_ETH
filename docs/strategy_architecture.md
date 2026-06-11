# Strategy Architecture

This project is organized as a replaceable strategy pipeline:

```text
Prepared data
    |
    v
strategies/
    |-- strategy A
    |-- strategy B
    `-- strategy C
    |
    v
backtest/
```

## Layers

### Data Layer

Responsible for fetching, cleaning, aligning, validating, and storing reusable market data.

```text
data/          raw Bybit fetch, cleaning, export
features/      indicators, labels, validation, feature matrix build
storage/raw/   raw parquet files
storage/features/ prepared feature matrices and validation reports
```

Run order:

```bash
python main.py
python build_features.py
python train_models.py
```

### Strategy Layer

Each strategy lives under `strategies/` and implements the same interface:

```text
Strategy.run(context)  -> backtest result dict
Strategy.save(context, results) -> reports/charts
```

Registered strategies are in:

```text
strategies/registry.py
```

Current strategy names:

```text
eth_long_current
eth_long_balanced
eth_long_target20
eth_dual_strict_short
```

### Backtest Layer

The backtest engine stays independent from any one strategy:

```text
backtest/engine.py          OOF probabilities and trade PnL
backtest/simulator.py       single-direction portfolio simulation
backtest/dual_simulator.py  competing long/short simulation
backtest/reporter.py        JSON and chart outputs
```

Unified strategy runner:

```bash
python run_strategy_backtest.py --strategy eth_long_balanced --symbol ETHUSDT
python run_strategy_backtest.py --strategy eth_long_target20 --symbol ETHUSDT
```

## Adding A New Strategy

1. Add a new file under `strategies/`.
2. Implement `Strategy.run()` and `Strategy.save()`.
3. Register it in `strategies/registry.py`.
4. Run it through:

```bash
python run_strategy_backtest.py --strategy your_strategy_name --symbol ETHUSDT
```

No data-fetching code or backtest-engine code should need to change when swapping strategies.


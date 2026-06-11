import logging
import argparse
import pandas as pd
import config
from features import builder

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeframe", choices=["1h", "4h", "1d"], default=config.DEFAULT_TIMEFRAME)
    args = parser.parse_args()

    suffix = "" if args.timeframe == "1h" else f"_{args.timeframe}"

    # Pre-load all primary-timeframe data for cross-asset features.
    all_primary = {}
    for symbol in config.SYMBOLS:
        path = config.STORAGE_RAW / f"{symbol}_{args.timeframe}.parquet"
        if path.exists():
            all_primary[symbol] = pd.read_parquet(path)

    for symbol in config.SYMBOLS:
        try:
            builder.build(
                symbol,
                all_primary=all_primary,
                timeframe=args.timeframe,
                output_suffix=suffix,
            )
        except Exception as exc:
            logging.error("[%s] build failed: %s", symbol, exc, exc_info=True)

import logging
import argparse
import config
from models import builder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeframe", choices=["1h", "1d"], default=config.DEFAULT_TIMEFRAME)
    args = parser.parse_args()
    suffix = "" if args.timeframe == "1h" else f"_{args.timeframe}"

    for symbol in config.SYMBOLS:
        for target in [
            "target_fixed",
            "target_atr",
            "target_fixed_short",
            "target_atr_short",
        ]:
            builder.build(symbol, target, asset_suffix=suffix)

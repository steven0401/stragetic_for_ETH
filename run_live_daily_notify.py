from __future__ import annotations

import logging
import time

import pandas as pd
import schedule

import config
from live import monitoring, notifier, pipeline, state

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

NOTIFY_STATE_FILE = config.STORAGE_LIVE / "daily_notify_state.json"
_assets_cache: dict[str, tuple[list[str], list]] = {}


def _get_assets(symbol: str, target: str, timeframe: str = "1d") -> tuple[list[str], list]:
    key = f"{symbol}_{timeframe}_{target}"
    if key not in _assets_cache:
        _assets_cache[key] = pipeline.load_assets(symbol, target, timeframe=timeframe)
        logger.info("[%s] Loaded %s %s fold models", symbol, timeframe, len(_assets_cache[key][1]))
    return _assets_cache[key]


def _format_signal_message(result: dict) -> str:
    status = "ENTRY SIGNAL" if result["signal"] else "NO ENTRY"
    return (
        f"[stragetic_for_ETH] {result['symbol']} daily signal: {status}\n"
        f"time:{result['timestamp']}\n"
        f"close:{result['close']:.4f}\n"
        f"prob:{result['probability']:.4f} threshold:{result['threshold']:.2f}\n"
        f"bull:{result['literature_bull_score']} risk:{result['literature_long_risk_score']}"
    )


def heartbeat() -> None:
    now = pd.Timestamp.now("UTC")
    logger.info("[notify heartbeat] %s", now.isoformat())
    notify_state = state.load_state(NOTIFY_STATE_FILE)

    for symbol in config.LIVE_SYMBOLS:
        feature_cols, fold_models = _get_assets(symbol, config.LIVE_TARGET, timeframe="1d")
        result = pipeline.compute_daily_literature_signal(
            symbol=symbol,
            feature_cols=feature_cols,
            fold_models=fold_models,
            threshold=config.LITERATURE_LONG_DAILY_THRESHOLD,
        )
        monitoring.append_daily_signal(result)

        last_notified_key = f"last_notified_{symbol}_1d"
        if notify_state.get(last_notified_key) == result["timestamp"]:
            logger.info("[%s] already notified for %s", symbol, result["timestamp"])
            continue

        notify_state[last_notified_key] = result["timestamp"]
        notifier.send(_format_signal_message(result))
        logger.info("[%s] notified prob=%.4f signal=%s", symbol, result["probability"], result["signal"])

    state.save_state(notify_state, NOTIFY_STATE_FILE)


def main() -> None:
    if not config.DISCORD_WEBHOOK_URL:
        logger.warning("DISCORD_WEBHOOK_URL not set - Discord notifications disabled")

    notifier.send(
        f"[stragetic_for_ETH] daily notify daemon started\n"
        f"threshold:{config.LITERATURE_LONG_DAILY_THRESHOLD}"
    )
    heartbeat()
    schedule.every(config.LIVE_DAILY_INTERVAL_MINUTES).minutes.do(heartbeat)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()

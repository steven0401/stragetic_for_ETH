from __future__ import annotations

import logging
import time
from decimal import Decimal
from pathlib import Path

import pandas as pd
import schedule

import config
from live import ledger, monitoring, notifier, pipeline, state
from live.bybit_trader import BybitTrader, _decimal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DISABLE_FLAG = config.BASE_DIR / ".disabled"
TRADE_STATE_FILE = config.STORAGE_LIVE / "bybit_active_positions.json"
TRADE_LEDGER_FILE = config.STORAGE_LIVE / "bybit_trade_ledger.json"
_assets_cache: dict[str, tuple[list[str], list]] = {}


def _is_disabled(flag_path: Path = None) -> bool:
    return (flag_path or DISABLE_FLAG).exists()


def _parse_utc(ts_str: str) -> pd.Timestamp:
    ts = pd.Timestamp(ts_str)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts


def _asset_key(symbol: str, target: str, timeframe: str) -> str:
    return f"{symbol}_{timeframe}_{target}"


def _get_assets(symbol: str, target: str, timeframe: str = "1d") -> tuple[list[str], list]:
    key = _asset_key(symbol, target, timeframe)
    if key not in _assets_cache:
        _assets_cache[key] = pipeline.load_assets(symbol, target, timeframe=timeframe)
        logger.info("[%s] Loaded %s %s fold models", symbol, timeframe, len(_assets_cache[key][1]))
    return _assets_cache[key]


def _sl_tp(close: float, atr_14: float) -> tuple[Decimal, Decimal]:
    entry = _decimal(close)
    atr = _decimal(atr_14)
    return entry - Decimal("1.5") * atr, entry + Decimal("3.0") * atr


def _order_link_id(prefix: str, symbol: str, now: pd.Timestamp) -> str:
    compact = now.strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{symbol[:3].lower()}-{compact}"


def _taipei_minute(ts: pd.Timestamp) -> str:
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("Asia/Taipei").strftime("%Y/%m/%d %H:%M")


def _status_message(
    symbol: str,
    result: dict,
    now: pd.Timestamp,
    equity: Decimal | None,
    current_state: dict,
) -> str:
    status = "進場訊號" if result["signal"] else "尚未進場"
    equity_text = f"{equity} USDT" if equity is not None else "讀取失敗"
    active_count = len(_positions_for_symbol(current_state, symbol))
    return (
        f"[stragetic_for_ETH] 例行檢查\n"
        f"偵測時間：{_taipei_minute(now)}\n"
        f"幣種：{symbol}\n"
        f"模型機率：{result['probability']:.4f} / 進場門檻：{result['threshold']:.2f}\n"
        f"訊號：{status}\n"
        f"多頭分數：{result['literature_bull_score']} / 風險分數：{result['literature_long_risk_score']}\n"
        f"目前持倉：{active_count}\n"
        f"帳戶權益：{equity_text}"
    )


def _positions_for_symbol(current_state: dict, symbol: str) -> list[dict]:
    return [p for p in current_state.get("positions", []) if p.get("symbol") == symbol]


def _replace_positions(current_state: dict, positions: list[dict]) -> dict:
    next_state = dict(current_state)
    next_state["positions"] = positions
    return next_state


def _reconcile_exchange_positions(trader: BybitTrader, current_state: dict, now: pd.Timestamp) -> dict:
    remaining = []
    for pos in current_state.get("positions", []):
        symbol = pos["symbol"]
        exchange_pos = trader.get_long_position(symbol)
        if exchange_pos is None:
            ledger.append_entry({
                **pos,
                "status": "closed_on_exchange",
                "exit_time_actual": now.isoformat(),
                "note": "Position no longer exists on Bybit; likely TP, SL, or manual close.",
            }, ledger_file=TRADE_LEDGER_FILE)
            notifier.send(
                f"[stragetic_for_ETH] {symbol} 倉位已在 Bybit 關閉\n"
                f"進場價：{pos.get('entry_price')} / 機率：{pos.get('probability')}\n"
                f"原因：偵測到倉位消失，可能是 TP、SL 或手動平倉"
            )
            continue

        exit_time = _parse_utc(pos["exit_time"])
        if now >= exit_time:
            qty = _decimal(exchange_pos.get("size", "0"))
            if qty > 0:
                close_result = trader.close_long(
                    symbol=symbol,
                    qty=qty,
                    order_link_id=_order_link_id("close", symbol, now),
                )
                ledger.append_entry({
                    **pos,
                    "status": "timeout_close_submitted",
                    "exit_time_actual": now.isoformat(),
                    "close_order": close_result,
                }, ledger_file=TRADE_LEDGER_FILE)
                notifier.send(
                    f"[stragetic_for_ETH] {symbol} 到期平倉單已送出\n"
                    f"數量：{qty} / 進場價：{pos.get('entry_price')}\n"
                    f"原定到期時間：{pos.get('exit_time')}"
                )
            continue

        remaining.append(pos)

    return _replace_positions(current_state, remaining)


def _open_position(
    trader: BybitTrader,
    current_state: dict,
    symbol: str,
    result: dict,
    now: pd.Timestamp,
) -> dict:
    entry = _decimal(result["close"])
    stop_loss, take_profit = _sl_tp(result["close"], result["atr_14"])
    rules = trader.get_instrument_rules(symbol)
    equity = trader.get_usdt_equity()
    qty = trader.calculate_qty(equity, entry, stop_loss, rules)
    order_link_id = _order_link_id("open", symbol, now)

    order_result = trader.open_long(
        symbol=symbol,
        qty=qty,
        stop_loss=stop_loss,
        take_profit=take_profit,
        order_link_id=order_link_id,
    )
    confirmed_position = trader.wait_for_position(symbol)

    entry_ts = _parse_utc(result["timestamp"])
    exit_time = (
        entry_ts + pd.Timedelta(days=config.LITERATURE_LONG_DAILY_HOLDING_BARS)
    ).isoformat()

    avg_price = confirmed_position.get("avgPrice") or result["close"]
    actual_size = confirmed_position.get("size") or str(qty)
    position = {
        "symbol": symbol,
        "target": config.LIVE_TARGET,
        "timeframe": "1d",
        "entry_time": result["timestamp"],
        "entry_price": float(avg_price),
        "signal_close": result["close"],
        "sl_price": float(stop_loss),
        "tp_price": float(take_profit),
        "atr_14": result["atr_14"],
        "probability": result["probability"],
        "threshold": result["threshold"],
        "literature_bull_score": result["literature_bull_score"],
        "literature_long_risk_score": result["literature_long_risk_score"],
        "qty": str(actual_size),
        "equity_usdt": str(equity),
        "order_link_id": order_link_id,
        "open_order": order_result,
        "exit_time": exit_time,
    }

    ledger.append_entry({**position, "status": "open_submitted"}, ledger_file=TRADE_LEDGER_FILE)
    notifier.send(
        f"[stragetic_for_ETH] {symbol} 做多單已送出\n"
        f"模型機率：{result['probability']:.4f} / 進場門檻：{result['threshold']:.2f}\n"
        f"數量：{actual_size} / 進場價：{avg_price}\n"
        f"停損：{float(stop_loss):.4f} / 止盈：{float(take_profit):.4f}\n"
        f"帳戶權益：{equity} USDT\n"
        f"最晚出場時間：{exit_time}"
    )

    return _replace_positions(
        current_state,
        current_state.get("positions", []) + [position],
    )


def heartbeat() -> None:
    now = pd.Timestamp.now("UTC")
    logger.info("[heartbeat] %s", now.isoformat())

    trader = BybitTrader()
    equity = None
    try:
        equity = trader.get_usdt_equity()
        monitoring.append_equity_snapshot(now, equity, "bybit_wallet")
    except Exception as exc:
        logger.warning("Equity snapshot failed: %s", exc)

    current_state = state.load_state(TRADE_STATE_FILE)
    current_state.setdefault("positions", [])
    current_state = _reconcile_exchange_positions(trader, current_state, now)

    if _is_disabled():
        logger.warning("Kill switch active (.disabled exists); skipping new entries")
        state.save_state(current_state, TRADE_STATE_FILE)
        return

    for symbol in config.LIVE_SYMBOLS:
        target = config.LIVE_TARGET
        feature_cols, fold_models = _get_assets(symbol, target, timeframe="1d")
        result = pipeline.compute_daily_literature_signal(
            symbol=symbol,
            feature_cols=feature_cols,
            fold_models=fold_models,
            threshold=config.LITERATURE_LONG_DAILY_THRESHOLD,
        )
        monitoring.append_daily_signal(result)
        notifier.send(_status_message(symbol, result, now, equity, current_state))
        logger.info(
            "[%s] prob=%.4f signal=%s bull=%s risk=%s",
            symbol,
            result["probability"],
            result["signal"],
            result["literature_bull_score"],
            result["literature_long_risk_score"],
        )

        last_checked_key = f"last_checked_{symbol}_1d"
        if current_state.get(last_checked_key) == result["timestamp"]:
            logger.info("[%s] Daily bar already processed: %s", symbol, result["timestamp"])
            continue

        current_state[last_checked_key] = result["timestamp"]

        if not result["signal"]:
            state.save_state(current_state, TRADE_STATE_FILE)
            continue

        tracked_positions = _positions_for_symbol(current_state, symbol)
        exchange_position = trader.get_long_position(symbol)
        if len(tracked_positions) >= config.LIVE_MAX_ACTIVE_PER_SYMBOL or exchange_position is not None:
            notifier.send(
                f"[stragetic_for_ETH] {symbol} 訊號略過\n"
                f"原因：偵測到目前已有持倉\n"
                f"模型機率：{result['probability']:.4f}\n"
                f"訊號時間：{result['timestamp']}"
            )
            state.save_state(current_state, TRADE_STATE_FILE)
            continue

        current_state = _open_position(trader, current_state, symbol, result, now)
        state.save_state(current_state, TRADE_STATE_FILE)

    state.save_state(current_state, TRADE_STATE_FILE)


def main() -> None:
    if not config.DISCORD_WEBHOOK_URL:
        logger.warning("DISCORD_WEBHOOK_URL not set - Discord notifications disabled")

    logger.info(
        "Daily live trading daemon starting; testnet=%s interval=%sm",
        config.BYBIT_TESTNET,
        config.LIVE_DAILY_INTERVAL_MINUTES,
    )
    notifier.send(
        f"[stragetic_for_ETH] 日K實盤交易程式已啟動\n"
        f"Testnet：{config.BYBIT_TESTNET}\n"
        f"進場門檻：{config.LITERATURE_LONG_DAILY_THRESHOLD}"
    )
    heartbeat()
    schedule.every(config.LIVE_DAILY_INTERVAL_MINUTES).minutes.do(heartbeat)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()

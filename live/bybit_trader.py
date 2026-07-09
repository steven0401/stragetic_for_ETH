from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Any

from pybit.unified_trading import HTTP

import config


@dataclass(frozen=True)
class InstrumentRules:
    qty_step: Decimal
    min_qty: Decimal
    max_market_qty: Decimal
    tick_size: Decimal


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _floor_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ValueError("step must be positive")
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


class BybitTrader:
    def __init__(self, session=None) -> None:
        self._validate_execution_lock()
        self.session = session or HTTP(
            testnet=config.BYBIT_TESTNET,
            api_key=config.API_KEY,
            api_secret=config.API_SECRET,
        )

    @staticmethod
    def _validate_execution_lock() -> None:
        if not config.LIVE_TRADING_ENABLED:
            raise RuntimeError("LIVE_TRADING_ENABLED is false; order execution is locked")
        if not config.API_KEY or not config.API_SECRET:
            raise RuntimeError("BYBIT_API_KEY and BYBIT_API_SECRET are required")
        expected = (
            "I_UNDERSTAND_TESTNET"
            if config.BYBIT_TESTNET
            else "I_UNDERSTAND_MAINNET_RISK"
        )
        if config.LIVE_TRADING_CONFIRM != expected:
            raise RuntimeError(
                f"LIVE_TRADING_CONFIRM must equal {expected} for this environment"
            )

    def get_instrument_rules(self, symbol: str) -> InstrumentRules:
        response = self.session.get_instruments_info(
            category=config.BYBIT_CATEGORY,
            symbol=symbol,
        )
        rows = response.get("result", {}).get("list", [])
        if not rows:
            raise RuntimeError(f"No instrument metadata returned for {symbol}")
        row = rows[0]
        lot = row["lotSizeFilter"]
        return InstrumentRules(
            qty_step=_decimal(lot["qtyStep"]),
            min_qty=_decimal(lot["minOrderQty"]),
            max_market_qty=_decimal(lot["maxMktOrderQty"]),
            tick_size=_decimal(row["priceFilter"]["tickSize"]),
        )

    def get_usdt_equity(self) -> Decimal:
        response = self.session.get_wallet_balance(
            accountType="UNIFIED",
            coin=config.BYBIT_SETTLE_COIN,
        )
        accounts = response.get("result", {}).get("list", [])
        if not accounts:
            raise RuntimeError("No unified wallet balance returned")
        equity = _decimal(accounts[0].get("totalEquity", "0"))
        if equity <= 0:
            raise RuntimeError(f"Invalid account equity: {equity}")
        return equity

    def get_long_position(self, symbol: str) -> dict | None:
        response = self.session.get_positions(
            category=config.BYBIT_CATEGORY,
            symbol=symbol,
        )
        for row in response.get("result", {}).get("list", []):
            if row.get("side") == "Buy" and _decimal(row.get("size", "0")) > 0:
                return row
        return None

    def calculate_qty(
        self,
        equity: Decimal,
        entry_price: Decimal,
        stop_price: Decimal,
        rules: InstrumentRules,
    ) -> Decimal:
        stop_distance = entry_price - stop_price
        if stop_distance <= 0:
            raise ValueError("stop price must be below entry price for a long")

        risk_budget = equity * _decimal(config.LITERATURE_LONG_DAILY_RISK_PCT)
        risk_qty = risk_budget / stop_distance
        notional_cap = equity * _decimal(config.LIVE_MAX_NOTIONAL_PCT)
        capped_qty = min(risk_qty, notional_cap / entry_price, rules.max_market_qty)
        qty = _floor_step(capped_qty, rules.qty_step)
        if qty < rules.min_qty:
            raise ValueError(
                f"Calculated qty {qty} is below minimum {rules.min_qty}"
            )
        return qty

    def open_long(
        self,
        symbol: str,
        qty: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
        order_link_id: str,
    ) -> dict:
        rules = self.get_instrument_rules(symbol)
        stop_loss = _floor_step(stop_loss, rules.tick_size)
        take_profit = _floor_step(take_profit, rules.tick_size)
        response = self.session.place_order(
            category=config.BYBIT_CATEGORY,
            symbol=symbol,
            side="Buy",
            orderType="Market",
            qty=_format_decimal(qty),
            positionIdx=config.BYBIT_POSITION_IDX,
            orderLinkId=order_link_id,
            reduceOnly=False,
            takeProfit=_format_decimal(take_profit),
            stopLoss=_format_decimal(stop_loss),
            tpTriggerBy="MarkPrice",
            slTriggerBy="MarkPrice",
            tpslMode="Full",
        )
        self._require_ok(response, "open long")
        return response["result"]

    def close_long(self, symbol: str, qty: Decimal, order_link_id: str) -> dict:
        response = self.session.place_order(
            category=config.BYBIT_CATEGORY,
            symbol=symbol,
            side="Sell",
            orderType="Market",
            qty=_format_decimal(qty),
            positionIdx=config.BYBIT_POSITION_IDX,
            orderLinkId=order_link_id,
            reduceOnly=True,
        )
        self._require_ok(response, "close long")
        return response["result"]

    def wait_for_position(self, symbol: str, attempts: int = 10) -> dict:
        for _ in range(attempts):
            position = self.get_long_position(symbol)
            if position is not None:
                return position
            time.sleep(1)
        raise RuntimeError(f"{symbol} order accepted but position was not confirmed")

    @staticmethod
    def _require_ok(response: dict, action: str) -> None:
        if response.get("retCode") != 0:
            raise RuntimeError(
                f"Bybit {action} failed: "
                f"{response.get('retCode')} {response.get('retMsg')}"
            )

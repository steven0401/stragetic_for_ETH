from decimal import Decimal

import pytest


def _unlock(monkeypatch, testnet=True):
    import config

    monkeypatch.setattr(config, "LIVE_TRADING_ENABLED", True)
    monkeypatch.setattr(config, "BYBIT_TESTNET", testnet)
    monkeypatch.setattr(config, "API_KEY", "key")
    monkeypatch.setattr(config, "API_SECRET", "secret")
    monkeypatch.setattr(
        config,
        "LIVE_TRADING_CONFIRM",
        "I_UNDERSTAND_TESTNET" if testnet else "I_UNDERSTAND_MAINNET_RISK",
    )


class FakeSession:
    def __init__(self):
        self.orders = []

    def get_instruments_info(self, **kwargs):
        return {
            "retCode": 0,
            "result": {
                "list": [{
                    "lotSizeFilter": {
                        "qtyStep": "0.001",
                        "minOrderQty": "0.001",
                        "maxMktOrderQty": "100",
                    },
                    "priceFilter": {"tickSize": "0.01"},
                }]
            },
        }

    def get_wallet_balance(self, **kwargs):
        return {"retCode": 0, "result": {"list": [{"totalEquity": "1000"}]}}

    def get_positions(self, **kwargs):
        return {"retCode": 0, "result": {"list": []}}

    def place_order(self, **kwargs):
        self.orders.append(kwargs)
        return {"retCode": 0, "result": {"orderId": "abc"}}


def test_execution_lock_requires_explicit_confirmation(monkeypatch):
    import config
    from live.bybit_trader import BybitTrader

    monkeypatch.setattr(config, "LIVE_TRADING_ENABLED", True)
    monkeypatch.setattr(config, "BYBIT_TESTNET", True)
    monkeypatch.setattr(config, "API_KEY", "key")
    monkeypatch.setattr(config, "API_SECRET", "secret")
    monkeypatch.setattr(config, "LIVE_TRADING_CONFIRM", "")

    with pytest.raises(RuntimeError, match="LIVE_TRADING_CONFIRM"):
        BybitTrader(session=FakeSession())


def test_calculate_qty_respects_risk_and_notional_cap(monkeypatch):
    import config
    from live.bybit_trader import BybitTrader

    _unlock(monkeypatch)
    monkeypatch.setattr(config, "LITERATURE_LONG_DAILY_RISK_PCT", 0.03)
    monkeypatch.setattr(config, "LIVE_MAX_NOTIONAL_PCT", 1.0)

    trader = BybitTrader(session=FakeSession())
    rules = trader.get_instrument_rules("ETHUSDT")
    qty = trader.calculate_qty(
        equity=Decimal("1000"),
        entry_price=Decimal("2000"),
        stop_price=Decimal("1900"),
        rules=rules,
    )

    # Risk qty would be 0.3 ETH, but 100% notional cap limits it to 0.5 ETH;
    # therefore the risk formula is the active constraint.
    assert qty == Decimal("0.3")


def test_open_long_submits_market_order_with_tp_sl(monkeypatch):
    import config
    from live.bybit_trader import BybitTrader

    _unlock(monkeypatch)
    monkeypatch.setattr(config, "BYBIT_CATEGORY", "linear")
    monkeypatch.setattr(config, "BYBIT_POSITION_IDX", 0)

    session = FakeSession()
    trader = BybitTrader(session=session)
    result = trader.open_long(
        symbol="ETHUSDT",
        qty=Decimal("0.123"),
        stop_loss=Decimal("1900.129"),
        take_profit=Decimal("2300.999"),
        order_link_id="open-eth-test",
    )

    assert result == {"orderId": "abc"}
    assert session.orders[0]["category"] == "linear"
    assert session.orders[0]["side"] == "Buy"
    assert session.orders[0]["orderType"] == "Market"
    assert session.orders[0]["qty"] == "0.123"
    assert session.orders[0]["stopLoss"] == "1900.12"
    assert session.orders[0]["takeProfit"] == "2300.99"
    assert session.orders[0]["reduceOnly"] is False

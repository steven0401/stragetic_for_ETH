from strategies.base import Strategy
from strategies.registry import STRATEGIES, get_strategy


def test_registry_contains_expected_strategies():
    assert "eth_long_current" in STRATEGIES
    assert "eth_long_balanced" in STRATEGIES
    assert "eth_long_target20" in STRATEGIES
    assert "eth_dual_strict_short" in STRATEGIES
    assert "eth_literature_long" in STRATEGIES


def test_registered_strategies_implement_interface():
    for strategy in STRATEGIES.values():
        assert isinstance(strategy, Strategy)
        assert strategy.name
        assert strategy.description


def test_get_strategy_returns_registered_instance():
    strategy = get_strategy("eth_long_balanced")
    assert strategy is STRATEGIES["eth_long_balanced"]


def test_get_strategy_error_lists_available_names():
    try:
        get_strategy("missing_strategy")
    except KeyError as exc:
        msg = str(exc)
        assert "missing_strategy" in msg
        assert "eth_long_balanced" in msg
    else:
        raise AssertionError("Expected KeyError for unknown strategy")

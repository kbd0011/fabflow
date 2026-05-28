import pytest

from fabflow.model.dispatching import RULES, get_rule
from fabflow.model.entities import Lot, Product, Step


def _lot_product():
    route = (Step(0, 0, 2.0), Step(1, 1, 3.0))
    prod = Product(id=0, name="P1", route=route, planned_cycle_time=15.0)
    lot = Lot(id=0, product_id=0, release_time=0.0, due_date=15.0, wafers=25)
    lot.history.append({"enqueue_time": 1.0})
    return lot, prod


def test_all_rules_callable():
    lot, prod = _lot_product()
    for name in RULES:
        score = get_rule(name)(lot, prod, now=5.0)
        assert isinstance(score, float)


def test_spt_uses_imminent_step():
    lot, prod = _lot_product()
    assert get_rule("spt")(lot, prod, 0.0) == 2.0   # first step proc time


def test_unknown_rule_raises():
    with pytest.raises(ValueError):
        get_rule("nope")

"""Dispatching rules: choose the next lot to process when a tool frees up.

Each rule scores waiting lots; the lowest score is selected next. These are the
classic fab dispatching heuristics whose effect on cycle time and on-time
delivery the improvement study quantifies.
"""
from __future__ import annotations

from collections.abc import Callable

from fabflow.model.entities import Lot, Product

# A scorer maps (lot, product, now) -> float; lower is dispatched first.
Scorer = Callable[[Lot, Product, float], float]


def _fifo(lot: Lot, product: Product, now: float) -> float:
    # First in (earliest arrival at this queue) first out.
    return lot.history[-1]["enqueue_time"] if lot.history else lot.release_time


def _spt(lot: Lot, product: Product, now: float) -> float:
    # Shortest processing time for the imminent step.
    return product.route[lot.step_index].proc_time


def _edd(lot: Lot, product: Product, now: float) -> float:
    # Earliest due date.
    return lot.due_date


def _critical_ratio(lot: Lot, product: Product, now: float) -> float:
    # CR = time remaining to due / work remaining. <1 means already behind.
    # Dispatch the most critical (smallest CR) first -> negate for "lower=first".
    remaining_work = max(lot.remaining_work(product), 1e-6)
    time_to_due = lot.due_date - now
    cr = time_to_due / remaining_work
    return cr


def _least_slack(lot: Lot, product: Product, now: float) -> float:
    # Slack = time to due - work remaining. Least slack first.
    return (lot.due_date - now) - lot.remaining_work(product)


RULES: dict[str, Scorer] = {
    "fifo": _fifo,
    "spt": _spt,
    "edd": _edd,
    "cr": _critical_ratio,
    "ls": _least_slack,
}


def get_rule(name: str) -> Scorer:
    if name not in RULES:
        raise ValueError(f"Unknown dispatching rule '{name}'. Options: {list(RULES)}")
    return RULES[name]

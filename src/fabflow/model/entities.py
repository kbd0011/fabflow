"""Fab entity definitions: tool groups, steps, routes, products, lots.

A wafer fab is a re-entrant flow shop: products follow routes (ordered steps),
each step is performed at a tool group (work center) holding one or more identical
parallel tools. Lots compete for tools; a dispatching rule breaks ties.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolGroup:
    """A work center holding `n_tools` identical parallel tools."""
    id: int
    name: str
    n_tools: int


@dataclass(frozen=True)
class Step:
    """One operation on a product route."""
    seq: int                 # position in the route (0-based)
    tool_group_id: int
    proc_time: float         # base processing time (hours) per lot


@dataclass(frozen=True)
class Product:
    """A product family with a fixed route and a planned cycle-time allowance."""
    id: int
    name: str
    route: tuple[Step, ...]
    planned_cycle_time: float   # for due-date setting (flow-factor * raw process time)

    @property
    def raw_process_time(self) -> float:
        return sum(s.proc_time for s in self.route)


@dataclass
class Lot:
    """A work unit moving through the fab."""
    id: int
    product_id: int
    release_time: float
    due_date: float
    wafers: int
    step_index: int = 0                 # current position in the route
    completion_time: float | None = None
    history: list[dict] = field(default_factory=list)   # per-step event records

    def remaining_work(self, product: Product) -> float:
        return sum(s.proc_time for s in product.route[self.step_index:])


@dataclass
class FabSpec:
    """The full static description of a fab: tool groups + products."""
    name: str
    tool_groups: dict[int, ToolGroup]
    products: dict[int, Product]
    wafers_per_lot: int

    def tool_group_load(self) -> dict[int, float]:
        """Aggregate base processing time demanded at each tool group across one lot of
        each product (a rough static workload signature, useful for sanity checks)."""
        load: dict[int, float] = dict.fromkeys(self.tool_groups, 0.0)
        for prod in self.products.values():
            for s in prod.route:
                load[s.tool_group_id] += s.proc_time
        return load

"""The SimPy wafer-fab digital twin.

Models lots flowing through re-entrant routes, competing for parallel tools at
each work center. Tools fail and are repaired during processing (tools mostly
fail while in use), extending the effective step time. When a tool becomes free
it pulls the best waiting lot per the dispatching rule. Every state change is
logged to a flat event list that the DuckDB layer turns into a star schema.

Design notes
------------
- Each ToolGroup is a pool of `n_tools` identical tools sharing one queue.
- The queue + dispatching is implemented manually (not simpy.Resource) so that
  arbitrary dispatching rules apply and queue/wait events are captured.
- Failures are sampled per processing job from the MTBF, adding MTTR repair time
  to that step. This keeps the model single-process-per-job and deterministic
  given a seed, while still degrading throughput at the busy (bottleneck) groups.
- Setup time is incurred when a tool group switches to a different product than
  the lot it last ran (sequence-dependent setup, simplified to per-group memory).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import simpy

from fabflow.config import FabCfg, SimCfg
from fabflow.model.dispatching import Scorer, get_rule
from fabflow.model.entities import FabSpec, Lot


@dataclass
class _Queue:
    waiting: list[Lot] = field(default_factory=list)
    busy_tools: int = 0
    last_product: int | None = None       # last product run at this group (setup memory)


class FabSim:
    def __init__(self, spec: FabSpec, fab_cfg: FabCfg, sim_cfg: SimCfg,
                 dispatching_rule: str, extra_tools: dict[int, int] | None = None,
                 seed: int = 0):
        self.spec = spec
        self.fab_cfg = fab_cfg
        self.sim_cfg = sim_cfg
        self.rule: Scorer = get_rule(dispatching_rule)
        self.rule_name = dispatching_rule
        self.rng = np.random.default_rng(seed)
        self.env = simpy.Environment()

        extra_tools = extra_tools or {}
        self.tool_counts = {g: tg.n_tools + extra_tools.get(g, 0)
                            for g, tg in spec.tool_groups.items()}

        self.queues: dict[int, _Queue] = {g: _Queue() for g in spec.tool_groups}
        self.events: list[dict] = []
        self.lots: dict[int, Lot] = {}
        self._lot_counter = 0
        self._wip = 0
        self.wip_trace: list[tuple[float, int]] = []
        self.busy_time: dict[int, float] = dict.fromkeys(spec.tool_groups, 0.0)
        self.repair_time: dict[int, float] = dict.fromkeys(spec.tool_groups, 0.0)
        self._conwip_ready: simpy.Container | None = None

    # ---- logging ---------------------------------------------------------
    def _log(self, kind: str, **kw) -> None:
        self.events.append({"time": round(self.env.now, 4), "kind": kind, **kw})

    def _record_wip(self, delta: int) -> None:
        self._wip += delta
        self.wip_trace.append((round(self.env.now, 4), self._wip))

    # ---- lot release -----------------------------------------------------
    def _make_lot(self) -> Lot:
        pid = int(self.rng.integers(0, len(self.spec.products)))
        product = self.spec.products[pid]
        now = self.env.now
        due = now + product.planned_cycle_time
        lot = Lot(id=self._lot_counter, product_id=pid, release_time=now,
                  due_date=due, wafers=self.spec.wafers_per_lot)
        self._lot_counter += 1
        self.lots[lot.id] = lot
        self._log("release", lot=lot.id, product=pid, due=round(due, 3))
        return lot

    def _release_uniform(self):
        while True:
            yield self.env.timeout(self.sim_cfg.uniform_interarrival_hours)
            lot = self._make_lot()
            self._record_wip(+1)
            self._enqueue(lot)

    def _release_conwip(self, ready: simpy.Container):
        for _ in range(self.sim_cfg.conwip_level):
            lot = self._make_lot()
            self._record_wip(+1)
            self._enqueue(lot)
        while True:
            yield ready.get(1)
            lot = self._make_lot()
            self._record_wip(+1)
            self._enqueue(lot)

    # ---- routing + queueing ---------------------------------------------
    def _enqueue(self, lot: Lot):
        product = self.spec.products[lot.product_id]
        if lot.step_index >= len(product.route):
            self._complete(lot)
            return
        step = product.route[lot.step_index]
        g = step.tool_group_id
        lot.history.append({"step": lot.step_index, "tool_group": g,
                            "enqueue_time": self.env.now, "start_time": None,
                            "end_time": None, "proc_time": None, "setup_time": None,
                            "repair_time": 0.0})
        self._log("enqueue", lot=lot.id, tool_group=g, step=lot.step_index)
        self.queues[g].waiting.append(lot)
        self._try_dispatch(g)

    def _try_dispatch(self, g: int):
        q = self.queues[g]
        while q.waiting and q.busy_tools < self.tool_counts[g]:
            now = self.env.now
            best = min(q.waiting, key=lambda lot: self.rule(
                lot, self.spec.products[lot.product_id], now))
            q.waiting.remove(best)
            q.busy_tools += 1
            self.env.process(self._process(g, best))

    def _process(self, g: int, lot: Lot):
        product = self.spec.products[lot.product_id]
        step = product.route[lot.step_index]
        rec = lot.history[-1]
        q = self.queues[g]

        # sequence-dependent setup if the group switches product family
        setup = 0.0
        if q.last_product is not None and q.last_product != lot.product_id:
            setup = step.proc_time * self.fab_cfg.setup_time_frac
        q.last_product = lot.product_id

        cv = self.fab_cfg.proc_time_cv
        ptime = float(step.proc_time * max(0.1, self.rng.normal(1.0, cv)))

        # sample failures during this job: number of failures ~ Poisson(ptime/MTBF)
        n_fail = int(self.rng.poisson(ptime / max(self.fab_cfg.mtbf_hours, 1e-6)))
        repair = float(sum(self.rng.exponential(self.fab_cfg.mttr_hours) for _ in range(n_fail)))

        rec["start_time"] = self.env.now
        rec["setup_time"] = round(setup, 4)
        self._log("start", lot=lot.id, tool_group=g, step=lot.step_index)

        total = setup + ptime + repair
        yield self.env.timeout(total)

        # Only accumulate busy/repair time for work that STARTED post-warmup, so the
        # utilization numerator matches the post-warmup denominator used in kpis.py
        # (n_tools * (horizon - warmup)). Mixing a full-horizon numerator with a
        # post-warmup denominator is what produced the impossible ">100%" utilization.
        if rec["start_time"] >= self.sim_cfg.warmup_hours:
            self.busy_time[g] += setup + ptime
            self.repair_time[g] += repair
        if n_fail:
            self._log("tool_repair", tool_group=g, n_fail=n_fail, repair=round(repair, 3))

        rec["end_time"] = self.env.now
        rec["proc_time"] = round(ptime, 4)
        rec["repair_time"] = round(repair, 4)
        self._log("end", lot=lot.id, tool_group=g, step=lot.step_index)

        q.busy_tools -= 1
        lot.step_index += 1
        self._enqueue(lot)
        self._try_dispatch(g)

    def _complete(self, lot: Lot):
        lot.completion_time = self.env.now
        self._record_wip(-1)
        product = self.spec.products[lot.product_id]
        ct = lot.completion_time - lot.release_time
        self._log("complete", lot=lot.id, product=lot.product_id,
                  cycle_time=round(ct, 4),
                  raw_process_time=round(product.raw_process_time, 4),
                  due=round(lot.due_date, 4),
                  tardy=int(lot.completion_time > lot.due_date))
        if self._conwip_ready is not None:
            self._conwip_ready.put(1)

    # ---- run -------------------------------------------------------------
    def run(self) -> dict:
        if self.sim_cfg.release_policy == "conwip":
            self._conwip_ready = simpy.Container(self.env, init=0)
            self.env.process(self._release_conwip(self._conwip_ready))
        else:
            self.env.process(self._release_uniform())
        self.env.run(until=self.sim_cfg.horizon_hours)
        return {"events": self.events, "lots": self.lots, "wip_trace": self.wip_trace,
                "busy_time": self.busy_time, "repair_time": self.repair_time,
                "tool_counts": dict(self.tool_counts), "rule": self.rule_name}

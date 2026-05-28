# Methods

## Discrete-event simulation (DES)

Time advances event-to-event (lot release, step start/end, completion), not in fixed
ticks. SimPy provides the event loop; each lot is modeled as it requests a tool at each
route step, waits in the work center's queue, is processed, and advances. This is the
standard approach for factory-physics questions where queueing, not just raw processing,
drives cycle time.

## Re-entrant routes

Wafer fabs are **re-entrant flow shops**: a lot visits the same work centers (especially
Litho/Etch/CMP) many times across its route. The synthetic generator biases route
sampling toward these "hot" centers, which produces a natural, emergent bottleneck rather
than a hand-placed one.

## Release policy: CONWIP

**CONstant Work In Process** holds the number of lots in the system fixed: a new lot is
released only when one completes. CONWIP is a well-known lever for controlling cycle time
— it caps WIP (and therefore, by Little's Law, cycle time) at the cost of some throughput
if set too low. The default level is tuned so the baseline X-factor is ~2.8, a realistic
regime. A uniform-interarrival release is also available.

## Dispatching rules

When a tool frees up and several lots wait, the dispatching rule picks the next one:

| Rule | Picks | Optimizes for |
|---|---|---|
| **FIFO** | earliest arrival at this queue | fairness / simplicity (baseline) |
| **SPT** | shortest imminent processing time | raw throughput, mean flow time |
| **EDD** | earliest due date | due-date adherence |
| **CR** (critical ratio) | smallest (time-to-due ÷ work-remaining) | due-date adherence under load |
| **LS** (least slack) | smallest (time-to-due − work-remaining) | due-date adherence, tight deadlines |

The study uses **critical ratio** as the "improved dispatch" lever because it directly
targets on-time delivery, which is exactly where it shows its effect.

## X-factor (flow factor)

`X = cycle time / raw process time`. It strips out how long the work *actually takes* and
exposes how much time is lost to queueing and disruptions. An X-factor of 1 is a
perfectly flowing fab; 3 means a lot spends two-thirds of its life waiting. Reducing
X-factor without adding capacity is "free" cycle-time reduction.

## Tool failures

Each processing job samples its failure count from `Poisson(proc_time / MTBF)` and adds
`Exponential(MTTR)` repair time per failure. Because failure exposure scales with
processing time, the busiest work centers absorb the most downtime — which is why
availability loss compounds at the bottleneck.

## Little's Law cross-check

`WIP = throughput × cycle time` must hold in steady state. `analysis/kpis.littles_law_check`
compares the law's WIP estimate against the time-average observed WIP as a sanity check on
the simulation and the warmup exclusion.

## Statistical replication

Each scenario runs `reps` independent replications (different seeds). KPIs are averaged
across reps so reported deltas reflect the policy change, not single-seed noise. Warmup
hours are excluded from all KPIs so transient fill-up doesn't bias steady-state metrics.

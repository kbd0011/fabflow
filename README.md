# FabFlow-Cortex

[![ci](https://github.com/kbd0011/fabflow/actions/workflows/ci.yml/badge.svg)](https://github.com/kbd0011/fabflow/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)
[![Live demo](https://img.shields.io/badge/%F0%9F%A4%97%20demo-Hugging%20Face%20Space-ffce1c.svg)](https://huggingface.co/spaces/kbdev0011/fabflow)

▶ **Live demo:** https://huggingface.co/spaces/kbdev0011/fabflow

**A SimPy discrete-event digital twin of a wafer fab, a DuckDB analytics layer, and a
pre/post improvement study that quantifies what a smarter dispatching rule and a
bottleneck capacity add are worth — in cycle time, X-factor, throughput, and on-time delivery.**

This is an industrial-engineering / operations problem end to end: model the line,
find the constraint, change one lever at a time, and measure the result across
replications. The fab is synthetic (no proprietary data), but the methodology is the
real thing a fab IE, yield-enhancement, or operations-improvement engineer applies.

---

## What it does

1. **Builds a synthetic fab** — work centers (Litho, Etch, CMP, Implant, Deposition,
   Diffusion, Metrology, Clean) with parallel tools, three product families with
   re-entrant routes, stochastic processing, sequence-dependent setups, and tool
   failures (MTBF/MTTR).
2. **Simulates it** with a custom SimPy model under a CONWIP release policy and a
   choice of dispatching rules (FIFO, SPT, EDD, critical-ratio, least-slack).
3. **Lands the event log in DuckDB** as a star schema (`fact_step`, `fact_lot`,
   `fact_util`, `dim_*`) — one source of truth for the report, the dashboard, and BI.
4. **Runs an improvement study** — baseline vs. scenarios across multiple seeded
   replications — auto-identifies the bottleneck and targets capacity there.
5. **Reports the result** — an HTML improvement report, a Streamlit dashboard, and a
   Parquet export ready for Tableau / Power BI.

## The headline result (default synthetic fab)

The bottleneck is **CMP — the binding constraint at ~95% utilization** (the next-busiest
work center sits well below it). Against a FIFO baseline:

| Scenario | Mean cycle time | X-factor | Throughput | On-time delivery |
|---|---|---|---|---|
| **Critical-ratio dispatching** | ~unchanged | ~unchanged | ~unchanged | **+27.5%** |
| **+1 tool at CMP (FIFO)** | **−6.3%** | **−4.8%** | **+6.8%** | +18% (but wider tail) |
| **Combined** | **−8.5%** | **−6.8%** | **+9.7%** | **+21.6%** |

The story isn't "everything got better." Critical-ratio dispatching buys on-time
delivery *for free* (no capex) because it sequences by due-date urgency; adding a tool
at the constraint buys throughput and mean cycle time but **widens the p95 tail** under
FIFO (more lots flowing through a fuller system). Only the combined change improves
every headline KPI at once. Quantifying that tradeoff is the point.

---

## Quickstart (macOS / Linux)

```bash
# one-time setup (installs uv, creates .venv, installs the package)
bash setup_fabflow.sh
source .venv/bin/activate

# run the whole pipeline: study -> warehouse -> report -> BI export
make run

# explore interactively
make dashboard          # Streamlit dashboard (opens in browser)
open artifacts/reports/improvement_report_*.html   # the HTML report
```

Or step by step with the CLI:

```bash
fabflow study           # run all scenarios x reps, build the DuckDB warehouse
fabflow analyze         # print KPI table + improvement deltas
fabflow report          # render the HTML improvement report
fabflow bi-export       # write artifacts/bi_export/*.parquet for Tableau/Power BI
fabflow simulate --scenario combined   # quick single-scenario run
```

Everything is driven by `configs/config.yaml` (fab size, CONWIP level, horizon,
reps, scenarios). Runs in seconds on a laptop, CPU-only.

---

## KPI glossary

| KPI | Meaning |
|---|---|
| **Cycle time (CT)** | Wall-clock time from lot release to completion. |
| **X-factor (flow factor)** | CT ÷ raw process time. The canonical fab metric: 1.0 = perfect flow, 3+ = heavy queueing. Lower is better. |
| **Throughput** | Lots / wafers completed per simulated week. |
| **WIP** | Work in progress (lots in the system); CONWIP caps it. |
| **Tool utilization** | Busy ÷ available time per work center; the highest is the bottleneck. |
| **On-time delivery (OTD)** | Fraction of lots finishing by their due date. |
| **Cycle-time CV** | Within-run std ÷ mean of CT; a predictability measure (lower = more predictable). |

Little's Law (WIP = throughput × cycle time) is cross-checked in `analysis/kpis.py`.

---


## Honest limitations

- The fab is **synthetic**. Absolute numbers (cycle times, utilizations) are
  illustrative, not a real fab; **the deltas and the method are the deliverable.**
- Failures and setups are **simplified** (per-job Poisson failures; per-group setup
  memory) rather than full SEMI-style equipment state machines.
- No operators, no reticle/batch constraints, no lot priorities/hot-lots, no
  preventive-maintenance scheduling. These are natural extensions, not present here.
- Due dates are derived from a planned flow factor, so OTD is internally consistent
  but not tied to external customer commits.

---

## Repo layout

```
src/fabflow/
  config.py              pydantic config
  model/                 entities, dispatching rules, the SimPy fab (fab.py)
  data/                  synthetic fab generator, DuckDB warehouse
  analysis/              KPIs, the study runner, scenario comparison
  reports/               HTML improvement report + Jinja template
  dashboard/app.py       Streamlit dashboard
  export/bi_export.py    Parquet export + KPI definitions (Python/DAX/Tableau)
  cli.py                 Typer CLI
configs/config.yaml      all parameters + scenarios
docs/                    architecture, methods, references, tableau_guide, sample report
notebooks/               00 overview -> 03 dashboard preview
tests/                   pytest suite
```

## License

MIT — see `LICENSE`. Synthetic data; no proprietary or customer information.

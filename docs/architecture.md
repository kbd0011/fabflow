# Architecture

```
                 configs/config.yaml  (pydantic-validated)
                          |
        +-----------------+------------------+
        |                                    |
  data/synthetic_fab.py                model/fab.py  (SimPy digital twin)
  builds FabSpec:                      - CONWIP / uniform release
  tool groups, products,               - manual queue + dispatching rule
  re-entrant routes                    - stochastic proc time, setups, failures
        |                                    |
        +----------------+-------------------+
                         |  run() -> event log + wip trace + busy/repair time
                         v
              data/warehouse.py
              run_to_frames() -> tidy fact/dim tables (warmup excluded)
              load_warehouse() -> DuckDB star schema
                         |
        +----------------+--------------------------------+
        |                |                                |
  analysis/kpis.py   reports/improvement_report.py   data/warehouse.export_parquet()
  scenario KPIs,     HTML report (matplotlib PNGs)    artifacts/bi_export/*.parquet
  bottleneck,        embedded                         -> Tableau / Power BI
  Little's law            |                                |
        |                 |                          dashboard/app.py (Streamlit)
        +-----------------+--------------------------------+
                          |
                    analysis/study.py  (orchestrates scenarios x reps)
                    analysis/compare.py (signed % deltas vs baseline)
                          |
                       cli.py (Typer): simulate | study | analyze | report | bi-export | run
```

## Star schema

| Table | Grain | Key columns |
|---|---|---|
| `fact_step` | one lot-step | scenario, rep, lot_id, tool_group_id, wait/proc/setup/repair time |
| `fact_lot` | one completed lot | scenario, rep, lot_id, cycle_time, x_factor, tardy, lateness |
| `fact_util` | one (scenario, rep, tool group) | busy_time, repair_time, n_tools |
| `wip_trace` | WIP timepoints | scenario, rep, time, wip |
| `dim_tool_group` | work center | tool_group_id, name, n_tools |
| `dim_product` | product family | product_id, route_length, raw_process_time, planned_cycle_time |

`scenario` + `rep` are the slicers; the facts join to the dims on
`tool_group_id` / `product_id`.

## Reproducibility

Every run is seeded. The fab spec is deterministic in `fab.seed`; each replication
uses `fab.seed + 1000 * rep`. Re-running `make run` reproduces the warehouse and the
reported deltas exactly.

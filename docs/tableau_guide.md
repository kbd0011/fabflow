# Building the FabFlow dashboard in Tableau Public (macOS)

The DuckDB warehouse is the single source of truth; `fabflow bi-export` writes it out as
Parquet so any BI tool can consume the same star schema with the same KPI math. Tableau
Public is free and runs natively on macOS.

## 1. Generate the data

```bash
make run                      # or: fabflow study && fabflow bi-export
ls artifacts/bi_export/       # fact_lot.parquet, fact_util.parquet, dim_*.parquet, ...
```

## 2. Connect Tableau to the Parquet files

Tableau Public reads Parquet directly:

1. **Connect → To a File → More… → Parquet**, open `artifacts/bi_export/fact_lot.parquet`.
2. Add the other files to the same data source (drag them onto the canvas).

## 3. Build the star-schema relationships

On the data-source canvas, relate the facts to the dims:

| From | To | On |
|---|---|---|
| `fact_lot` | `dim_product` | `product_id = product_id` |
| `fact_util` | `dim_tool_group` | `tool_group_id = tool_group_id` |
| `fact_step` | `dim_tool_group` | `tool_group_id = tool_group_id` |

Use `scenario` (and `rep`) as the slicers across all facts.

## 4. Calculated fields (mirror the Python KPIs)

These match `src/fabflow/export/bi_export.py::KPI_DEFINITIONS` exactly, so Tableau,
Power BI, and the Python report agree:

```
Mean Cycle Time (h)   :  AVG([cycle_time])
Mean X-Factor         :  AVG([x_factor])
On-Time Delivery      :  1 - (SUM([tardy]) / COUNT([lot_id]))
Wafers Out            :  SUM([wafers])
Tool Utilization      :  SUM([busy_time]) / (SUM([n_tools]) * [Avail Hours])
```

`[Avail Hours]` is a parameter = `horizon_hours - warmup_hours` (default 1512 − 168 = 1344).
This is the post-warmup window, and it must match the numerator: `fact_util.busy_time`
only accumulates work that **started after warmup**, so both numerator and denominator
cover the same window. (Dividing a full-horizon busy time by this post-warmup span is the
windowing bug that made CMP read >100%; with the windows aligned, true utilization is ≤ 100%.)

## 5. Suggested sheets

1. **KPI scorecard** — `scenario` on rows; Mean Cycle Time, Mean X-Factor, On-Time
   Delivery, Wafers Out as columns. Filter to compare baseline vs. combined.
2. **Cycle-time distribution** — histogram of `cycle_time`, color by `scenario`.
3. **Utilization by work center** — bars of Tool Utilization by `dim_tool_group.name`,
   color by `scenario`, reference line at 1.0 (the bottleneck pokes above the rest).
4. **WIP over time** — line of `wip` vs `time` from `wip_trace`, color by `scenario`.

Combine the four onto a dashboard with a `scenario` filter applied to all. That filter
turns it into an interactive pre/post improvement view — the same story as the HTML report,
but explorable.

## Power BI note

The identical Parquet files import into Power BI; use the DAX in `KPI_DEFINITIONS`
(`AVERAGE(fact_lot[cycle_time])`, etc.). Power BI Desktop is Windows-only, which is why
Tableau Public is the macOS-native recommendation here.

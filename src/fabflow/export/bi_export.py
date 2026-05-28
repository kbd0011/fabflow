"""BI export helpers (Parquet star schema) + DAX/Tableau measure definitions.

The same star schema feeds the Streamlit dashboard, the HTML report, and any
external BI tool. Keeping the measure math in one place (here, as documented
strings) means Power BI DAX and Tableau calculated fields stay consistent with
the Python KPIs.
"""
from __future__ import annotations

# Canonical KPI definitions, mirrored across Python / DAX / Tableau.
KPI_DEFINITIONS = {
    "Mean Cycle Time (h)": {
        "python": "fact_lot.cycle_time.mean()",
        "dax": "AVERAGE(fact_lot[cycle_time])",
        "tableau": "AVG([cycle_time])",
    },
    "Mean X-Factor": {
        "python": "fact_lot.x_factor.mean()",
        "dax": "AVERAGE(fact_lot[x_factor])",
        "tableau": "AVG([x_factor])",
    },
    "On-Time Delivery": {
        "python": "1 - fact_lot.tardy.mean()",
        "dax": "1 - DIVIDE(SUM(fact_lot[tardy]), COUNTROWS(fact_lot))",
        "tableau": "1 - (SUM([tardy]) / COUNT([lot_id]))",
    },
    "Tool Utilization": {
        "python": "busy_time / (n_tools * available_hours)",
        "dax": "DIVIDE(SUM(fact_util[busy_time]), SUMX(fact_util, fact_util[n_tools]) * [AvailHours])",
        "tableau": "SUM([busy_time]) / (SUM([n_tools]) * [Avail Hours])",
    },
    "Wafers Out / Week": {
        "python": "fact_lot.wafers.sum() / span_weeks",
        "dax": "DIVIDE(SUM(fact_lot[wafers]), [SpanWeeks])",
        "tableau": "SUM([wafers]) / [Span Weeks]",
    },
}

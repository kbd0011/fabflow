"""Streamlit dashboard for FabFlow-Cortex.

Run: streamlit run src/fabflow/dashboard/app.py
Reads the DuckDB warehouse produced by `fabflow study`.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import plotly.express as px
import streamlit as st

from fabflow.analysis.compare import improvement_deltas
from fabflow.analysis.kpis import identify_bottleneck, scenario_kpis, utilization
from fabflow.config import load_config

st.set_page_config(page_title="FabFlow-Cortex", layout="wide", page_icon="🏭")
st.title("FabFlow-Cortex")
st.caption("SimPy wafer-fab digital twin · DuckDB analytics · pre/post improvement study")
st.info(
    "Synthetic fab model — absolute numbers are illustrative; the **deltas and the "
    "method** (find the constraint → intervene → measure across replications) are the "
    "deliverable. The warehouse is built on first load by running the study.",
    icon="🏭",
)


@st.cache_resource
def get_cfg():
    return load_config("configs/config.yaml")


cfg = get_cfg()
db = cfg.output.warehouse


@st.cache_resource(show_spinner=False)
def ensure_warehouse() -> str:
    """Build the DuckDB warehouse on first load if it isn't present (Spaces ship no warehouse)."""
    if not Path(db).exists():
        with st.spinner("Building the synthetic-fab warehouse (running all scenarios x reps)…"):
            from fabflow.analysis.study import run_study
            run_study(cfg)
    return str(db)


ensure_warehouse()

H, Wm = cfg.sim.horizon_hours, cfg.sim.warmup_hours


@st.cache_data
def load_kpi():
    return scenario_kpis(db, H, Wm)


@st.cache_data
def load_util():
    return utilization(db, H, Wm)


@st.cache_data
def load_deltas():
    return improvement_deltas(db, H, Wm)


@st.cache_data
def load_table(name):
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(f"SELECT * FROM {name}").df()
    finally:
        con.close()


kpi = load_kpi()
bn = identify_bottleneck(db, H, Wm)

# --- headline metrics ---
st.subheader("Baseline vs best scenario")
deltas = load_deltas()
best = deltas["mean_cycle_time_h"].idxmax() if not deltas.empty else None
c1, c2, c3, c4 = st.columns(4)
c1.metric("Baseline X-factor", f"{kpi.loc['baseline','mean_x_factor']:.2f}")
c1.metric("Baseline OTD", f"{kpi.loc['baseline','on_time_delivery']*100:.0f}%")
if best:
    c2.metric("Best scenario", best)
    c2.metric("Cycle-time cut", f"{deltas.loc[best,'mean_cycle_time_h']:.1f}%")
    c3.metric("X-factor cut", f"{deltas.loc[best,'mean_x_factor']:.1f}%")
    c3.metric("Throughput gain", f"{deltas.loc[best,'wafers_out_per_week']:.1f}%")
    c4.metric("OTD gain", f"{deltas.loc[best,'on_time_delivery']:.1f}%")
if bn:
    c4.metric("Bottleneck", f"{bn['name']} ({bn['utilization']*100:.0f}%)")

# --- KPI table ---
st.subheader("KPI summary (mean across reps)")
st.dataframe(kpi.round(3), use_container_width=True)

# --- charts ---
left, right = st.columns(2)
with left:
    st.markdown("**Cycle-time distribution by scenario**")
    lot = load_table("fact_lot")
    fig = px.histogram(lot, x="cycle_time", color="scenario", barmode="overlay",
                       nbins=50, histnorm="probability density", opacity=0.55)
    fig.update_layout(height=360, xaxis_title="cycle time (h)")
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.markdown("**Tool-group utilization**")
    u = load_util()
    fig2 = px.bar(u, x="name", y="utilization", color="scenario", barmode="group")
    fig2.add_hline(y=1.0, line_dash="dash", line_color="red")
    fig2.update_layout(height=360, xaxis_title="", yaxis_title="utilization")
    st.plotly_chart(fig2, use_container_width=True)

# --- improvement deltas ---
st.subheader("Improvement vs baseline (%, + = better)")
st.dataframe(deltas.round(2), use_container_width=True)

# --- WIP trace ---
st.subheader("WIP over time")
wip = load_table("wip_trace")
wip_s = wip[wip["rep"] == wip["rep"].min()]
figw = px.line(wip_s, x="time", y="wip", color="scenario")
figw.update_layout(height=320, xaxis_title="sim time (h)", yaxis_title="lots in system")
st.plotly_chart(figw, use_container_width=True)

st.caption("Synthetic fab model for methodology demonstration; absolute numbers are not a real fab.")

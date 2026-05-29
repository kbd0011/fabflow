---
title: FabFlow-Cortex
emoji: 🏭
colorFrom: green
colorTo: gray
sdk: streamlit
sdk_version: "1.36.0"
app_file: app.py
pinned: false
license: mit
python_version: "3.12"
---

# FabFlow-Cortex

Interactive dashboard for a SimPy wafer-fab digital twin + DuckDB analytics + a
pre/post improvement study (FIFO vs critical-ratio dispatching vs +1 tool at the
bottleneck vs combined, across seeded replications).

The DuckDB warehouse is built on first load by running the study (a few seconds),
so the Space runs with no uploaded data. Synthetic fab — absolute numbers are
illustrative; the deltas and the method are the deliverable. See the
[main repo](https://github.com/kbd0011/fabflow).

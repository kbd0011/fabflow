---
title: FabFlow-Cortex
emoji: 🏭
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# FabFlow-Cortex

Interactive dashboard for a SimPy wafer-fab digital twin + DuckDB analytics + a
pre/post improvement study (FIFO vs critical-ratio dispatching vs +1 tool at the
bottleneck vs combined, across seeded replications).

The DuckDB warehouse is built on first load by running the study (a few seconds),
so the Space runs with no uploaded data. Synthetic fab — absolute numbers are
illustrative; the deltas and the method are the deliverable. See the
[main repo](https://github.com/kbd0011/fabflow).

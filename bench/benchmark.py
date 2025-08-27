# bench/benchmark.py
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

from orderbook.sim import SimConfig, Simulator
from orderbook.metrics import summarize_latency_ns
from orderbook.viz import plot_latency_hist


def main() -> None:
    cfg = SimConfig(seed=123, n_events=200_000)
    sim = Simulator(cfg)
    art = sim.run()

    Path("results").mkdir(parents=True, exist_ok=True)
    summary = summarize_latency_ns(art.latencies_ns)
    lat_png = plot_latency_hist(art.latencies_ns, "results")
    pd.DataFrame([summary]).to_csv("results/benchmark_summary.csv", index=False)
    print(json.dumps({"benchmark": summary, "latency_hist": lat_png}, indent=2))


if __name__ == "__main__":
    main()

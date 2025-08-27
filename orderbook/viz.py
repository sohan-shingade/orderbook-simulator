# orderbook/viz.py
from __future__ import annotations

from pathlib import Path
from typing import Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .metrics import SeriesMetrics, l1_metrics_from_snapshots


def plot_timeseries_metrics(snaps: pd.DataFrame, out_dir: str) -> Dict[str, str]:
    paths: Dict[str, str] = {}
    metrics = l1_metrics_from_snapshots(snaps)

    figdir = Path(out_dir) / "figures"
    figdir.mkdir(parents=True, exist_ok=True)

    plt.figure()
    metrics.spread.plot(title="Spread (L1)")
    p = figdir / "spread.png"
    plt.xlabel("snapshot")
    plt.ylabel("price")
    plt.tight_layout()
    plt.savefig(p)
    plt.close()
    paths["spread_png"] = str(p)

    plt.figure()
    metrics.mid.plot(title="Midprice")
    p = figdir / "midprice.png"
    plt.xlabel("snapshot")
    plt.ylabel("price")
    plt.tight_layout()
    plt.savefig(p)
    plt.close()
    paths["midprice_png"] = str(p)

    plt.figure()
    metrics.bid_depth.plot(label="bid_depth")
    metrics.ask_depth.plot(label="ask_depth")
    plt.legend()
    plt.title("L1 Depths")
    plt.xlabel("snapshot")
    plt.ylabel("shares")
    p = figdir / "depths.png"
    plt.tight_layout()
    plt.savefig(p)
    plt.close()
    paths["depths_png"] = str(p)

    plt.figure()
    metrics.imbalance.plot(title="Order Book Imbalance")
    plt.xlabel("snapshot")
    plt.ylabel("imbalance")
    p = figdir / "imbalance.png"
    plt.tight_layout()
    plt.savefig(p)
    plt.close()
    paths["imbalance_png"] = str(p)

    return paths


def plot_latency_hist(latencies_ns: np.ndarray, out_dir: str) -> str:
    figdir = Path(out_dir) / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    plt.figure()
    us = latencies_ns / 1_000.0
    plt.hist(us, bins=50)
    plt.title("Operation Latency Histogram (μs)")
    plt.xlabel("latency (μs)")
    plt.ylabel("count")
    p = figdir / "latency_hist.png"
    plt.tight_layout()
    plt.savefig(p)
    plt.close()
    return str(p)

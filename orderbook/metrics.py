# orderbook/metrics.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd


@dataclass(slots=True)
class SeriesMetrics:
    spread: pd.Series
    mid: pd.Series
    bid_depth: pd.Series
    ask_depth: pd.Series
    imbalance: pd.Series


def l1_metrics_from_snapshots(df: pd.DataFrame) -> SeriesMetrics:
    best_bid = df["best_bid"].astype(float)
    best_ask = df["best_ask"].astype(float)
    spread = (best_ask - best_bid).fillna(method="ffill")
    mid = ((best_ask + best_bid) / 2.0).fillna(method="ffill")
    bid_depth = df["bid_depth"].astype(float)
    ask_depth = df["ask_depth"].astype(float)
    imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth + 1e-9)
    return SeriesMetrics(spread=spread, mid=mid, bid_depth=bid_depth, ask_depth=ask_depth, imbalance=imbalance)


def summarize_latency_ns(latencies: np.ndarray) -> Dict[str, float]:
    if latencies.size == 0:
        return {"p50_ns": 0.0, "p90_ns": 0.0, "p99_ns": 0.0, "ops_per_sec": 0.0}
    p50 = float(np.percentile(latencies, 50))
    p90 = float(np.percentile(latencies, 90))
    p99 = float(np.percentile(latencies, 99))
    mean_ns = float(latencies.mean())
    ops = 1e9 / mean_ns if mean_ns > 0 else 0.0
    return {"p50_ns": p50, "p90_ns": p90, "p99_ns": p99, "ops_per_sec": ops}

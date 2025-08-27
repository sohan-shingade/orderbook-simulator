# tests/test_metrics.py
from __future__ import annotations

import pandas as pd

from orderbook.metrics import l1_metrics_from_snapshots


def test_l1_metrics_basic():
    df = pd.DataFrame(
        {
            "event": [1, 2, 3, 4],
            "best_bid": [9.9, 10.0, 10.0, 10.1],
            "best_ask": [10.1, 10.2, 10.2, 10.3],
            "bid_depth": [100, 120, 130, 110],
            "ask_depth": [90, 100, 95, 105],
        }
    )
    m = l1_metrics_from_snapshots(df)
    assert (m.spread.values == (df["best_ask"] - df["best_bid"]).values).all()
    assert (m.mid.values == ((df["best_ask"] + df["best_bid"]) / 2.0).values).all()
    assert len(m.imbalance) == 4

# orderbook/sim.py
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .core import OrderBook
from .models import Order, OrderType, Side, TimeInForce, Trade


@dataclass(slots=True)
class SimConfig:
    seed: int = 30
    n_events: int = 50_000
    tick_size: float = 0.01
    p_limit: float = 0.65
    p_market: float = 0.20
    p_cancel: float = 0.10
    p_replace: float = 0.05
    mid0: float = 100.0
    sigma_ticks: float = 1.5
    drift_per_1k: float = 0.0
    size_mean: float = 100.0
    size_min: int = 10
    p_ioc: float = 0.05
    p_fok: float = 0.02
    snapshot_every: int = 250


@dataclass(slots=True)
class SimArtifacts:
    trades: pd.DataFrame
    snapshots: pd.DataFrame
    latencies_ns: np.ndarray
    order_count: int
    cancel_count: int
    replace_count: int


class Simulator:
    def __init__(self, cfg: SimConfig) -> None:
        self.cfg = cfg
        self.rs = np.random.RandomState(cfg.seed)
        self.next_id = 1
        self.book = OrderBook(tick_size=cfg.tick_size, check_invariants=False)
        self.queue_ahead: Dict[int, int] = {}
        self.filled_qty: Dict[int, int] = {}

    def _gen_size(self) -> int:
        size = max(int(self.rs.lognormal(mean=math.log(self.cfg.size_mean), sigma=0.5)), self.cfg.size_min)
        return int(round(size / 10.0) * 10)

    def _side(self) -> Side:
        return Side.BUY if self.rs.rand() < 0.5 else Side.SELL

    def _limit_price_near_mid(self, mid: float, side: Side) -> float:
        ticks = int(round(self.rs.normal(loc=1.0 if side is Side.BUY else -1.0, scale=self.cfg.sigma_ticks)))
        px = mid + ticks * self.cfg.tick_size
        return max(self.cfg.tick_size, round(px / self.cfg.tick_size) * self.cfg.tick_size)

    def _pick_tif(self) -> TimeInForce:
        r = self.rs.rand()
        if r < self.cfg.p_fok:
            return TimeInForce.FOK
        if r < self.cfg.p_fok + self.cfg.p_ioc:
            return TimeInForce.IOC
        return TimeInForce.GTC

    def _initial_queue_ahead(self, side: Side, price: float) -> int:
        if side is Side.BUY:
            depth = self.book.depth_at_price(Side.BUY, price)
        else:
            depth = self.book.depth_at_price(Side.SELL, price)
        return depth

    def run(self) -> SimArtifacts:
        cfg = self.cfg
        rs = self.rs
        latencies: List[int] = []
        mid = cfg.mid0

        trades: List[Trade] = []
        snaps: List[Tuple[int, Optional[float], Optional[float], int, int]] = []

        for k in range(10):
            self._seed_initial_levels(mid, base_qty=200)

        for i in range(cfg.n_events):
            r = rs.rand()
            mid += (cfg.drift_per_1k / 1000.0) * self.cfg.tick_size

            if r < cfg.p_limit:
                side = self._side()
                price = self._limit_price_near_mid(mid, side)
                tif = self._pick_tif()
                qty = self._gen_size()
                oid = self.next_id
                self.next_id += 1
                order = Order(id=oid, side=side, qty=qty, price=price, order_type=OrderType.LIMIT, tif=tif)
                if tif is TimeInForce.GTC:
                    self.queue_ahead[oid] = self._initial_queue_ahead(side, price)
                t0 = time.perf_counter_ns()
                new_trades = self.book.add(order)
                dt = time.perf_counter_ns() - t0
                latencies.append(dt)
                trades.extend(new_trades)
                for tr in new_trades:
                    self.filled_qty[tr.maker_id] = self.filled_qty.get(tr.maker_id, 0) + tr.qty
                    self.filled_qty[tr.taker_id] = self.filled_qty.get(tr.taker_id, 0) + tr.qty

            elif r < cfg.p_limit + cfg.p_market:
                side = self._side()
                qty = self._gen_size()
                oid = self.next_id
                self.next_id += 1
                order = Order(id=oid, side=side, qty=qty, price=None, order_type=OrderType.MARKET, tif=TimeInForce.IOC)
                t0 = time.perf_counter_ns()
                new_trades = self.book.add(order)
                dt = time.perf_counter_ns() - t0
                latencies.append(dt)
                trades.extend(new_trades)
                for tr in new_trades:
                    self.filled_qty[tr.maker_id] = self.filled_qty.get(tr.maker_id, 0) + tr.qty
                    self.filled_qty[tr.taker_id] = self.filled_qty.get(tr.taker_id, 0) + tr.qty

            elif r < cfg.p_limit + cfg.p_market + cfg.p_cancel:
                victim = self._random_resting_id()
                if victim is not None:
                    t0 = time.perf_counter_ns()
                    _canceled = self.book.cancel(victim)
                    dt = time.perf_counter_ns() - t0
                    latencies.append(dt)

            else:
                victim = self._random_resting_id()
                if victim is not None:
                    side, price = self.book._id_index[victim]
                    delta_ticks = int(self.rs.choice([-1, 1]))
                    new_price = price + delta_ticks * cfg.tick_size
                    t0 = time.perf_counter_ns()
                    _ok, new_trades = self.book.replace(victim, new_price=new_price)
                    dt = time.perf_counter_ns() - t0
                    latencies.append(dt)
                    trades.extend(new_trades)
                    for tr in new_trades:
                        self.filled_qty[tr.maker_id] = self.filled_qty.get(tr.maker_id, 0) + tr.qty
                        self.filled_qty[tr.taker_id] = self.filled_qty.get(tr.taker_id, 0) + tr.qty

            if (i + 1) % cfg.snapshot_every == 0:
                bb, ba, bd, ad = self.book.snapshot_top()
                snaps.append((i + 1, bb, ba, bd, ad))

        trades_df = pd.DataFrame(list(map(__import__('dataclasses').asdict, trades)))
        snap_df = pd.DataFrame(snaps, columns=["event", "best_bid", "best_ask", "bid_depth", "ask_depth"])
        return SimArtifacts(
            trades=trades_df,
            snapshots=snap_df,
            latencies_ns=np.array(latencies, dtype=np.int64),
            order_count=self.next_id - 1,
            cancel_count=0,
            replace_count=0,
        )

    def _random_resting_id(self) -> Optional[int]:
        if not self.book._id_index:
            return None
        keys = list(self.book._id_index.keys())
        k = self.rs.randint(0, len(keys))
        return keys[k]

    def _seed_initial_levels(self, mid: float, base_qty: int = 100) -> None:
        for d in range(1, 4):
            bid_px = round(mid - d * self.cfg.tick_size, 2)
            ask_px = round(mid + d * self.cfg.tick_size, 2)
            b = Order(id=self.next_id, side=Side.BUY, qty=base_qty, price=bid_px, order_type=OrderType.LIMIT)
            self.next_id += 1
            a = Order(id=self.next_id, side=Side.SELL, qty=base_qty, price=ask_px, order_type=OrderType.LIMIT)
            self.next_id += 1
            self.book.add(b)
            self.book.add(a)


def save_artifacts(art: SimArtifacts, out_dir: str) -> Dict[str, str]:
    ts = pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S")
    base = Path(out_dir)
    (base / "figures").mkdir(parents=True, exist_ok=True)
    files = {}
    trades_path = base / f"trades_{ts}.csv"
    art.trades.to_csv(trades_path, index=False)
    files["trades_csv"] = str(trades_path)

    snaps_path = base / f"snapshots_{ts}.csv"
    art.snapshots.to_csv(snaps_path, index=False)
    files["snapshots_csv"] = str(snaps_path)

    lat_path = base / f"latencies_{ts}.csv"
    pd.DataFrame({"latency_ns": art.latencies_ns}).to_csv(lat_path, index=False)
    files["latencies_csv"] = str(lat_path)

    return files

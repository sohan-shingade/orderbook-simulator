# orderbook/core.py
from __future__ import annotations

import heapq
from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple

from .models import Order, Trade, Side, OrderType, TimeInForce, OrderId


@dataclass(slots=True)
class LevelQueue:
    """FIFO queue at a single price level."""
    price: float
    orders: Deque[Order]


class OrderBook:
    """
    Price-time priority order book with:
      - LIMIT and MARKET orders
      - partial fills
      - cancel by order id
      - replace/modify (price and/or qty)
      - IOC and FOK
    Data structures:
      - dict[price]->deque FIFO per side
      - heaps for best price discovery (lazy cleanup)
      - id_index for locating an order's side & price level
    Invariants (enforced via check_invariants on demand):
      - No crossed book (best_bid < best_ask) unless one side empty
      - FIFO within price level
      - Deterministic sequencing (integer ts increases)
    """

    def __init__(self, tick_size: float = 0.01, check_invariants: bool = False) -> None:
        self.tick: float = tick_size
        self._bids: Dict[float, Deque[Order]] = defaultdict(deque)
        self._asks: Dict[float, Deque[Order]] = defaultdict(deque)
        self._bid_heap: List[float] = []  # store negative prices for max-heap behavior
        self._ask_heap: List[float] = []  # store positive prices (min-heap)
        self._id_index: Dict[OrderId, Tuple[Side, float]] = {}  # id -> (side, price)
        self._seq: int = 0
        self._check: bool = check_invariants
        self.trades: List[Trade] = []

    def _best_bid_price(self) -> Optional[float]:
        while self._bid_heap:
            p = -self._bid_heap[0]
            if p in self._bids and self._bids[p]:
                return p
            heapq.heappop(self._bid_heap)  # stale
        return None

    def _best_ask_price(self) -> Optional[float]:
        while self._ask_heap:
            p = self._ask_heap[0]
            if p in self._asks and self._asks[p]:
                return p
            heapq.heappop(self._ask_heap)  # stale
        return None

    def best_bid(self) -> Optional[float]:
        return self._best_bid_price()

    def best_ask(self) -> Optional[float]:
        return self._best_ask_price()

    def add(self, order: Order) -> List[Trade]:
        self._seq += 1
        order.ts = self._seq
        if order.remaining is None:
            order.remaining = order.qty

        trades: List[Trade] = []
        if order.order_type is OrderType.MARKET:
            trades = self._execute_market(order)
        else:
            trades = self._execute_limit_against_opposite(order)
            if order.is_active and order.tif is not TimeInForce.IOC and order.tif is not TimeInForce.FOK:
                self._rest_limit(order)
            elif order.tif is TimeInForce.FOK and order.is_active:
                order.remaining = 0
        if self._check:
            self.assert_invariants()
        return trades

    def cancel(self, order_id: OrderId) -> int:
        idx = self._id_index.get(order_id)
        if idx is None:
            return 0
        side, price = idx
        book = self._bids if side is Side.BUY else self._asks
        q = book.get(price)
        if not q:
            self._id_index.pop(order_id, None)
            return 0
        canceled = 0
        new_q: Deque[Order] = deque()
        found = False
        while q:
            o = q.popleft()
            if o.id == order_id and not found:
                canceled = o.remaining or 0
                o.remaining = 0
                found = True
            else:
                new_q.append(o)
        if new_q:
            book[price] = new_q
        else:
            book.pop(price, None)
        self._id_index.pop(order_id, None)
        if self._check:
            self.assert_invariants()
        return canceled

    def replace(self, order_id: OrderId, new_price: Optional[float] = None, new_qty: Optional[int] = None, new_tif: Optional[TimeInForce] = None) -> Tuple[bool, List[Trade]]:
        idx = self._id_index.get(order_id)
        if idx is None:
            return (False, [])
        side, _price = idx
        removed = self._extract_order(order_id)
        if removed is None:
            return (False, [])
        price = removed.price if new_price is None else new_price
        remaining = removed.remaining or 0
        if new_qty is not None:
            if new_qty <= 0:
                return (False, [])
            already_filled = removed.qty - (removed.remaining or 0)
            if new_qty < already_filled:
                remaining = 0
            else:
                remaining = new_qty - already_filled
        tif = removed.tif if new_tif is None else new_tif
        new_order = Order(
            id=order_id,
            side=side,
            qty=(removed.qty if new_qty is None else new_qty),
            price=price,
            order_type=(OrderType.LIMIT if price is not None else OrderType.MARKET),
            tif=tif,
            remaining=remaining,
        )
        trades = self.add(new_order)
        return (True, trades)

    def _extract_order(self, order_id: OrderId) -> Optional[Order]:
        idx = self._id_index.get(order_id)
        if idx is None:
            return None
        side, price = idx
        book = self._bids if side is Side.BUY else self._asks
        q = book.get(price)
        if not q:
            self._id_index.pop(order_id, None)
            return None
        new_q: Deque[Order] = deque()
        target: Optional[Order] = None
        while q:
            o = q.popleft()
            if o.id == order_id and target is None:
                target = o
            else:
                new_q.append(o)
        if new_q:
            book[price] = new_q
        else:
            book.pop(price, None)
        self._id_index.pop(order_id, None)
        return target

    def _rest_limit(self, order: Order) -> None:
        price = float(order.price)
        if order.side is Side.BUY:
            if price not in self._bids or not self._bids[price]:
                heapq.heappush(self._bid_heap, -price)
            self._bids[price].append(order)
        else:
            if price not in self._asks or not self._asks[price]:
                heapq.heappush(self._ask_heap, price)
            self._asks[price].append(order)
        self._id_index[order.id] = (order.side, price)

    def _execute_market(self, order: Order) -> List[Trade]:
        if order.side is Side.BUY:
            return self._take_from_asks(order, limit_price=None, tif=order.tif)
        else:
            return self._take_from_bids(order, limit_price=None, tif=order.tif)

    def _execute_limit_against_opposite(self, order: Order) -> List[Trade]:
        trades: List[Trade] = []
        if order.tif is TimeInForce.FOK:
            need = order.remaining or 0
            available = self._executable_available(order)
            if available < need:
                order.remaining = 0
                return []
        if order.side is Side.BUY:
            trades = self._take_from_asks(order, limit_price=float(order.price), tif=order.tif)
        else:
            trades = self._take_from_bids(order, limit_price=float(order.price), tif=order.tif)
        return trades

    def _executable_available(self, order: Order) -> int:
        remaining = order.remaining or 0
        side = order.side
        if side is Side.BUY:
            limit = float(order.price) if order.order_type is OrderType.LIMIT else float("inf")
            total = 0
            asks = sorted(self._asks.keys())
            for p in asks:
                if p > limit:
                    break
                q = sum(o.remaining or 0 for o in self._asks[p])
                total += q
                if total >= remaining:
                    return total
            return total
        else:
            limit = float(order.price) if order.order_type is OrderType.LIMIT else 0.0
            total = 0
            bids = sorted(self._bids.keys(), reverse=True)
            for p in bids:
                if p < limit:
                    break
                q = sum(o.remaining or 0 for o in self._bids[p])
                total += q
                if total >= remaining:
                    return total
            return total

    def _take_from_asks(self, order: Order, limit_price: Optional[float], tif: TimeInForce) -> List[Trade]:
        trades: List[Trade] = []
        while order.is_active:
            best = self._best_ask_price()
            if best is None:
                break
            if limit_price is not None and best > limit_price:
                break
            level = self._asks.get(best)
            if not level:
                heapq.heappop(self._ask_heap)
                continue
            while order.is_active and level:
                maker = level[0]
                maker_remaining = maker.remaining or 0
                take_qty = min(order.remaining or 0, maker_remaining)
                if take_qty <= 0:
                    break
                maker.remaining = maker_remaining - take_qty
                order.remaining = (order.remaining or 0) - take_qty
                self._seq += 1
                trade = Trade(maker_id=maker.id, taker_id=order.id, price=best, qty=take_qty, ts=self._seq)
                self.trades.append(trade)
                trades.append(trade)
                if maker.remaining == 0:
                    level.popleft()
                    self._id_index.pop(maker.id, None)
            if not level:
                self._asks.pop(best, None)
        if tif is TimeInForce.IOC:
            order.remaining = 0
        return trades

    def _take_from_bids(self, order: Order, limit_price: Optional[float], tif: TimeInForce) -> List[Trade]:
        trades: List[Trade] = []
        while order.is_active:
            best = self._best_bid_price()
            if best is None:
                break
            if limit_price is not None and best < limit_price:
                break
            level = self._bids.get(best)
            if not level:
                heapq.heappop(self._bid_heap)
                continue
            while order.is_active and level:
                maker = level[0]
                maker_remaining = maker.remaining or 0
                take_qty = min(order.remaining or 0, maker_remaining)
                if take_qty <= 0:
                    break
                maker.remaining = maker_remaining - take_qty
                order.remaining = (order.remaining or 0) - take_qty
                self._seq += 1
                trade = Trade(maker_id=maker.id, taker_id=order.id, price=best, qty=take_qty, ts=self._seq)
                self.trades.append(trade)
                trades.append(trade)
                if maker.remaining == 0:
                    level.popleft()
                    self._id_index.pop(maker.id, None)
            if not level:
                self._bids.pop(best, None)
        if tif is TimeInForce.IOC:
            order.remaining = 0
        return trades

    def depth_at_price(self, side: Side, price: float) -> int:
        book = self._bids if side is Side.BUY else self._asks
        return sum((o.remaining or 0) for o in book.get(price, deque()))

    def total_depth(self, side: Side) -> int:
        book = self._bids if side is Side.BUY else self._asks
        return sum((o.remaining or 0) for q in book.values() for o in q)

    def levels(self, side: Side) -> List[Tuple[float, int]]:
        if side is Side.BUY:
            keys = sorted(self._bids.keys(), reverse=True)
            return [(p, self.depth_at_price(Side.BUY, p)) for p in keys]
        keys = sorted(self._asks.keys())
        return [(p, self.depth_at_price(Side.SELL, p)) for p in keys]

    def assert_invariants(self) -> None:
        bb = self._best_bid_price()
        ba = self._best_ask_price()
        if bb is not None and ba is not None:
            assert bb < ba, f"Crossed book: best_bid={bb} best_ask={ba}"
        for p, q in self._bids.items():
            last_ts = -1
            for o in q:
                assert o.ts >= last_ts, f"FIFO violated at BID {p}"
                last_ts = o.ts
        for p, q in self._asks.items():
            last_ts = -1
            for o in q:
                assert o.ts >= last_ts, f"FIFO violated at ASK {p}"
                last_ts = o.ts

    def snapshot_top(self) -> Tuple[Optional[float], Optional[float], int, int]:
        bb = self._best_bid_price()
        ba = self._best_ask_price()
        bid_depth = self.depth_at_price(Side.BUY, bb) if bb is not None else 0
        ask_depth = self.depth_at_price(Side.SELL, ba) if ba is not None else 0
        return (bb, ba, bid_depth, ask_depth)

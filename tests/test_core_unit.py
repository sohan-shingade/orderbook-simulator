# tests/test_core_unit.py
from __future__ import annotations

import math
import pytest

from orderbook.core import OrderBook
from orderbook.models import Order, OrderType, Side, TimeInForce


def test_limit_matching_partial_fill():
    ob = OrderBook()
    ask = Order(id=1, side=Side.SELL, qty=100, price=10.0, order_type=OrderType.LIMIT)
    ob.add(ask)
    buy = Order(id=2, side=Side.BUY, qty=50, price=12.0, order_type=OrderType.LIMIT)
    trades = ob.add(buy)
    assert sum(t.qty for t in trades) == 50
    bb, ba, bd, ad = ob.snapshot_top()
    assert ba == 10.0
    assert ad == 50


def test_market_order_executes_immediately():
    ob = OrderBook()
    ob.add(Order(id=1, side=Side.SELL, qty=30, price=10.0, order_type=OrderType.LIMIT))
    ob.add(Order(id=2, side=Side.SELL, qty=30, price=10.01, order_type=OrderType.LIMIT))
    mkt = Order(id=3, side=Side.BUY, qty=20, price=None, order_type=OrderType.MARKET, tif=TimeInForce.IOC)
    trades = ob.add(mkt)
    assert sum(t.qty for t in trades) == 20
    assert ob.depth_at_price(Side.SELL, 10.0) == 10


def test_cancel_removes_order():
    ob = OrderBook()
    ob.add(Order(id=1, side=Side.BUY, qty=40, price=9.90, order_type=OrderType.LIMIT))
    ob.add(Order(id=2, side=Side.BUY, qty=60, price=9.90, order_type=OrderType.LIMIT))
    canceled = ob.cancel(1)
    assert canceled == 40
    assert ob.depth_at_price(Side.BUY, 9.90) == 60


def test_replace_price_move_loses_priority():
    ob = OrderBook()
    ob.add(Order(id=1, side=Side.BUY, qty=50, price=9.95, order_type=OrderType.LIMIT))
    ob.add(Order(id=2, side=Side.BUY, qty=50, price=9.95, order_type=OrderType.LIMIT))
    ok, trades = ob.replace(1, new_price=9.96)
    assert ok
    levels_996 = ob.levels(Side.BUY)
    assert any(math.isclose(p, 9.96) and d == 50 for p, d in levels_996)
    assert ob.depth_at_price(Side.BUY, 9.95) == 50


def test_ioc_discard_remainder():
    ob = OrderBook()
    ob.add(Order(id=1, side=Side.SELL, qty=50, price=10.0, order_type=OrderType.LIMIT))
    ioc = Order(id=2, side=Side.BUY, qty=100, price=10.0, order_type=OrderType.LIMIT, tif=TimeInForce.IOC)
    trades = ob.add(ioc)
    assert sum(t.qty for t in trades) == 50
    assert ob.depth_at_price(Side.BUY, 10.0) == 0


def test_fok_requires_full_available():
    ob = OrderBook()
    ob.add(Order(id=1, side=Side.SELL, qty=50, price=10.0, order_type=OrderType.LIMIT))
    fok = Order(id=2, side=Side.BUY, qty=100, price=12.0, order_type=OrderType.LIMIT, tif=TimeInForce.FOK)
    trades = ob.add(fok)
    assert len(trades) == 0
    assert ob.depth_at_price(Side.SELL, 10.0) == 50

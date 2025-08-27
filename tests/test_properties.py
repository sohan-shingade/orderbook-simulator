# tests/test_properties.py
from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given, settings

from orderbook.core import OrderBook
from orderbook.models import Order, OrderType, Side, TimeInForce


@st.composite
def orders(draw, start_id=1):
    oid = draw(st.integers(min_value=start_id, max_value=start_id + 10000))
    side = draw(st.sampled_from([Side.BUY, Side.SELL]))
    qty = draw(st.integers(min_value=10, max_value=500))
    price = draw(st.floats(min_value=1.0, max_value=200.0, allow_nan=False, allow_infinity=False))
    tif = draw(st.sampled_from([TimeInForce.GTC, TimeInForce.IOC, TimeInForce.FOK]))
    typ = draw(st.sampled_from([OrderType.LIMIT, OrderType.MARKET]))
    if typ is OrderType.MARKET:
        price = None
        tif = TimeInForce.IOC
    return Order(id=oid, side=side, qty=qty, price=price, order_type=typ, tif=tif)


@given(st.lists(orders(), min_size=20, max_size=200))
@settings(deadline=None, max_examples=25)
def test_no_cross_invariants_random_sequence(seq):
    ob = OrderBook(check_invariants=True)
    used_ids = set()
    for o in seq:
        if o.id in used_ids:
            continue
        used_ids.add(o.id)
        ob.add(o)
    ob.assert_invariants()

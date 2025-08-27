# orderbook/__init__.py
"""
Order Book Simulator — Price-Time Priority Matching Engine.

Export the primary types and entry points for convenience.
"""
from .models import Side, OrderType, TimeInForce, Order, Trade
from .core import OrderBook

__all__ = [
    "Side",
    "OrderType",
    "TimeInForce",
    "Order",
    "Trade",
    "OrderBook",
]

__version__ = "0.1.0"

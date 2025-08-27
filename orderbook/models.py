# orderbook/models.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class Side(Enum):
    BUY = 1
    SELL = -1

    def opposite(self) -> "Side":
        return Side.SELL if self is Side.BUY else Side.BUY


class OrderType(Enum):
    LIMIT = auto()
    MARKET = auto()


class TimeInForce(Enum):
    GTC = auto()   # Good-Til-Cancel (default)
    IOC = auto()   # Immediate-Or-Cancel (partial ok, remainder canceled)
    FOK = auto()   # Fill-Or-Kill (all-or-none immediately or cancel)


OrderId = int


@dataclass(slots=True)
class Order:
    """
    External order representation used by the engine.
    - qty: original quantity in shares (positive int)
    - remaining: current outstanding quantity
    - price: float price for LIMIT, None for MARKET
    - ts: deterministic sequence number (integer monotone)
    """
    id: OrderId
    side: Side
    qty: int
    price: Optional[float]
    order_type: OrderType
    tif: TimeInForce = TimeInForce.GTC
    ts: int = 0
    remaining: Optional[int] = None

    def __post_init__(self) -> None:
        if self.qty <= 0:
            raise ValueError("qty must be positive")
        if self.order_type is OrderType.LIMIT and self.price is None:
            raise ValueError("LIMIT order requires price")
        if self.order_type is OrderType.MARKET and self.price is not None:
            raise ValueError("MARKET order must have price=None")
        if self.remaining is None:
            self.remaining = self.qty

    @property
    def is_active(self) -> bool:
        return (self.remaining or 0) > 0


@dataclass(slots=True)
class Trade:
    """
    Trade record emitted by matching engine.
    maker_id: resting order id
    taker_id: incoming (or modifying) order id
    price: execution price (price of resting order for LIMIT/marketable)
    qty: executed quantity
    ts: engine sequence for determinism
    """
    maker_id: OrderId
    taker_id: OrderId
    price: float
    qty: int
    ts: int

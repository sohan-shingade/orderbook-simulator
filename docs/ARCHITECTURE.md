# Architecture & Design Decisions

- Bids/Asks: `dict[price] -> deque[Order]` (FIFO), best price via heaps with lazy deletion
- id_index: `order_id -> (side, price)` for O(1) level location; cancels scan within level
- Operations: limit/market add, partial fills, cancel, replace; IOC/FOK supported
- Complexity: best-price ~O(1), deque ops O(1), cancel/replace O(k) within level
- Single-threaded event loop; thread-safety and production evolution discussed in README

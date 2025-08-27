# Order Book Simulator — Price-Time Priority Matching Engine

**Author:** Sohan Shingade (UC San Diego — Data Science & Finance)

I built a production-style limit order book in Python that matches orders using strict **price-time priority**. It supports **limit/market orders**, **partial fills**, **cancels**, **replace/modify** (queue priority resets on price change), and **IOC/FOK**. I added a deterministic synthetic event generator, L1 metrics, microbenchmarks, visualizations, and a CLI so it’s easy to run end-to-end. Everything is self-contained: no external data or services.

## Quickstart

```bash
pip install -r requirements.txt
make test
python -m orderbook.cli sim --seed 30 --n-events 200000 --report results/
python -m orderbook.cli bench --n-events 300000 --report results/
python -m orderbook.cli report --report results/
```

Artifacts are saved under `results/`:
- `trades_*.csv`, `snapshots_*.csv`, `latencies_*.csv`
- figures in `results/figures/`: `spread.png`, `midprice.png`, `depths.png`, `imbalance.png`, `latency_hist.png`

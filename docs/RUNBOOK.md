# Runbook & Reproducibility

## Setup
```
pip install -r requirements.txt
```

## Simulation
```
python -m orderbook.cli sim --seed 30 --n-events 200000 --report results/
```

## Benchmark
```
python -m orderbook.cli bench --n-events 300000 --report results/
```

## Update Report
```
python -m orderbook.cli report --report results/
```

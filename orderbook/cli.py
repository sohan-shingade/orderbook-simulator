# orderbook/cli.py
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .metrics import summarize_latency_ns
from .sim import SimArtifacts, SimConfig, Simulator, save_artifacts
from .viz import plot_latency_hist, plot_timeseries_metrics


def run_sim(args: argparse.Namespace) -> None:
    cfg = SimConfig(
        seed=args.seed,
        n_events=args.n_events,
        tick_size=args.tick,
        p_limit=args.p_limit,
        p_market=args.p_market,
        p_cancel=args.p_cancel,
        p_replace=args.p_replace,
        mid0=args.mid,
        sigma_ticks=args.sigma_ticks,
        drift_per_1k=args.drift_per_1k,
        size_mean=args.size_mean,
        size_min=args.size_min,
        p_ioc=args.p_ioc,
        p_fok=args.p_fok,
        snapshot_every=args.snapshot_every,
    )
    sim = Simulator(cfg)
    art: SimArtifacts = sim.run()
    out_dir = args.report
    paths = save_artifacts(art, out_dir)
    fig_paths = plot_timeseries_metrics(art.snapshots, out_dir)
    lat_png = plot_latency_hist(art.latencies_ns, out_dir)
    summary = summarize_latency_ns(art.latencies_ns)

    print(json.dumps({"saved": {**paths, **fig_paths, "latency_hist": lat_png}, "latency_summary": summary}, indent=2))


def run_bench(args: argparse.Namespace) -> None:
    cfg = SimConfig(seed=args.seed, n_events=args.n_events, snapshot_every=max(args.n_events // 50, 1))
    sim = Simulator(cfg)
    art = sim.run()
    out_dir = args.report
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    lat_png = plot_latency_hist(art.latencies_ns, out_dir)
    summary = summarize_latency_ns(art.latencies_ns)
    df = pd.DataFrame([summary])
    csv = Path(out_dir) / "benchmark_summary.csv"
    df.to_csv(csv, index=False)
    print(json.dumps({"benchmark": summary, "latency_hist": lat_png, "csv": str(csv)}, indent=2))


def run_report(args: argparse.Namespace) -> None:
    results_dir = Path(args.report)
    figs = results_dir / "figures"
    def latest(pattern: str) -> str:
        candidates = sorted(figs.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        return str(candidates[0]) if candidates else ""

    mapping = {
        "SPREAD_PATH": latest("spread.png"),
        "MID_PATH": latest("midprice.png"),
        "DEPTHS_PATH": latest("depths.png"),
        "IMB_PATH": latest("imbalance.png"),
        "LAT_PATH": latest("latency_hist.png"),
    }
    doc = Path("docs/RESULTS.md")
    text = doc.read_text(encoding="utf-8")
    for key, val in mapping.items():
        placeholder = f"{{{{{key}}}}}"
        text = text.replace(placeholder, val)
    doc.write_text(text, encoding="utf-8")
    print(json.dumps({"updated": "docs/RESULTS.md", "figures": mapping}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="orderbook", description="Order Book Simulator CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sim = sub.add_parser("sim", help="Run simulation and save artifacts")
    p_sim.add_argument("--seed", type=int, default=30)
    p_sim.add_argument("--n-events", type=int, default=200_000)
    p_sim.add_argument("--tick", type=float, default=0.01)
    p_sim.add_argument("--p-limit", type=float, default=0.65)
    p_sim.add_argument("--p-market", type=float, default=0.20)
    p_sim.add_argument("--p-cancel", type=float, default=0.10)
    p_sim.add_argument("--p-replace", type=float, default=0.05)
    p_sim.add_argument("--mid", type=float, default=100.0)
    p_sim.add_argument("--sigma-ticks", type=float, default=1.5)
    p_sim.add_argument("--drift-per-1k", type=float, default=0.0)
    p_sim.add_argument("--size-mean", type=float, default=100.0)
    p_sim.add_argument("--size-min", type=int, default=10)
    p_sim.add_argument("--p-ioc", type=float, default=0.05)
    p_sim.add_argument("--p-fok", type=float, default=0.02)
    p_sim.add_argument("--snapshot-every", type=int, default=250)
    p_sim.add_argument("--report", type=str, default="results")
    p_sim.set_defaults(func=run_sim)

    p_bench = sub.add_parser("bench", help="Run microbenchmark")
    p_bench.add_argument("--seed", type=int, default=30)
    p_bench.add_argument("--n-events", type=int, default=300_000)
    p_bench.add_argument("--report", type=str, default="results")
    p_bench.set_defaults(func=run_bench)

    p_report = sub.add_parser("report", help="Update docs/RESULTS.md with latest figure paths")
    p_report.add_argument("--report", type=str, default="results")
    p_report.set_defaults(func=run_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

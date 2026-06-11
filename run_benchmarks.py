#!/usr/bin/env python3
"""
run_benchmarks.py - Automated load-test runner + chart/table generator.

Runs Locust load tests locally (against localhost) for the music catalog services
and produces a rich set of comparison charts and CSV tables.

Requirements (host machine):
  pip install locust matplotlib pandas requests grpcio grpcio-tools

Usage:
  # Run everything
  python run_benchmarks.py

  # Filter by technology (language)
  python run_benchmarks.py --tech go           # only the 4 Go services
  python run_benchmarks.py --tech python       # only the 4 Python services

  # Filter by API/protocol
  python run_benchmarks.py --api rest          # go-rest + python-rest
  python run_benchmarks.py --api grpc,graphql  # gRPC and GraphQL variants

  # Combine filters (single service)
  python run_benchmarks.py --tech go --api rest   # only go-rest

  # Filter by load level
  python run_benchmarks.py --load high
  python run_benchmarks.py --tech go --load low,medium

  # Only regenerate charts/tables from existing results (no Locust run)
  python run_benchmarks.py --charts-only
"""

import argparse
import csv
import math
import os
import socket
import subprocess
import sys
import time

import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd

# ── Service registry ───────────────────────────────────────────────────────

ALL_SERVICES = {
    "go-rest":        ("http://localhost:8001", "locust/locustfile_rest.py"),
    "go-graphql":     ("http://localhost:8002", "locust/locustfile_graphql.py"),
    "go-grpc":        ("http://localhost:8003", "locust/locustfile_grpc.py"),
    "go-soap":        ("http://localhost:8004", "locust/locustfile_soap.py"),
    "python-rest":    ("http://localhost:8011", "locust/locustfile_rest.py"),
    "python-graphql": ("http://localhost:8012", "locust/locustfile_graphql.py"),
    "python-grpc":    ("http://localhost:8013", "locust/locustfile_grpc.py"),
    "python-soap":    ("http://localhost:8014", "locust/locustfile_soap.py"),
}

# Load levels: (label, users, spawn_rate, duration_seconds)
# Durations increased so the test stabilises well past the ramp-up phase.
ALL_LOADS = [
    ("low",    50,  10, 30),   # 30 s  – ramp fully done in ~5 s
    ("medium", 200, 20, 45),   # 45 s  – ramp done in ~10 s
    ("high",   500, 50, 60),   # 60 s  – ramp done in ~10 s
]

TECH_MAP = {
    "go":     [s for s in ALL_SERVICES if s.startswith("go-")],
    "python": [s for s in ALL_SERVICES if s.startswith("python-")],
}

API_MAP = {
    "rest":    ["go-rest",    "python-rest"],
    "graphql": ["go-graphql", "python-graphql"],
    "grpc":    ["go-grpc",    "python-grpc"],
    "soap":    ["go-soap",    "python-soap"],
}

# gRPC services don't expose an HTTP /health endpoint – check TCP instead
GRPC_PORTS = {"8003", "8013"}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR  = os.path.join(BASE_DIR, "results")
os.makedirs(OUT_DIR, exist_ok=True)

# Per-service colour palette (used in line charts)
COLORS = {
    "go-rest":        "#2196F3",
    "go-graphql":     "#4CAF50",
    "go-grpc":        "#9C27B0",
    "go-soap":        "#FF9800",
    "python-rest":    "#F44336",
    "python-graphql": "#009688",
    "python-grpc":    "#E91E63",
    "python-soap":    "#795548",
}

# ── Argument parsing ───────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Music API benchmark runner")
    p.add_argument("--tech",        help="Filter by tech: go, python  (comma-separated)")
    p.add_argument("--api",         help="Filter by API: rest, graphql, grpc, soap  (comma-separated)")
    p.add_argument("--load",        help="Filter by load level: low, medium, high  (comma-separated)")
    p.add_argument("--charts-only", action="store_true",
                   help="Skip Locust; regenerate charts/tables from existing CSVs only")
    return p.parse_args()


def filter_services(tech_filter, api_filter):
    services = list(ALL_SERVICES.keys())
    if tech_filter:
        allowed = set()
        for t in tech_filter.split(","):
            allowed.update(TECH_MAP.get(t.strip(), []))
        services = [s for s in services if s in allowed]
    if api_filter:
        allowed = set()
        for a in api_filter.split(","):
            allowed.update(API_MAP.get(a.strip(), []))
        services = [s for s in services if s in allowed]
    return services


def filter_loads(load_filter):
    if not load_filter:
        return ALL_LOADS
    labels = {l.strip() for l in load_filter.split(",")}
    return [l for l in ALL_LOADS if l[0] in labels]

# ── Service health checks ──────────────────────────────────────────────────

def wait_for_service(url, retries=20):
    parts = url.replace("http://", "").replace("https://", "").split(":")
    host  = parts[0]
    port  = parts[1] if len(parts) > 1 else "80"

    if port in GRPC_PORTS:
        for _ in range(retries):
            try:
                s = socket.create_connection((host, int(port)), timeout=3)
                s.close()
                return True
            except OSError:
                pass
            time.sleep(2)
        return False

    for _ in range(retries):
        try:
            r = requests.get(f"{url}/health", timeout=3)
            if r.status_code < 400:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False

# ── Locust runner ──────────────────────────────────────────────────────────

def run_locust(name, host, locustfile, users, spawn_rate, duration):
    csv_prefix = os.path.join(OUT_DIR, f"{name}_u{users}")
    cmd = [
        sys.executable, "-m", "locust",
        "-f", os.path.join(BASE_DIR, locustfile),
        "--host", host,
        "--headless",
        "-u", str(users),
        "-r", str(spawn_rate),
        "--run-time", f"{duration}s",
        "--csv", csv_prefix,
        "--only-summary",
    ]
    print(f"  -> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=BASE_DIR, check=False)
    if result.returncode != 0:
        print(f"  WARNING: Locust exited with code {result.returncode}")
    return csv_prefix


def read_stats(csv_prefix):
    stats_file = csv_prefix + "_stats.csv"
    if not os.path.exists(stats_file):
        return None
    with open(stats_file, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        if row.get("Name", "").lower() in ("aggregated", "total", ""):
            return row
    return rows[-1] if rows else None

# ── Persistent result store ────────────────────────────────────────────────

def load_existing_results():
    path = os.path.join(OUT_DIR, "all_results.csv")
    return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()


def merge_results(existing_df, new_records):
    """Merge new records into existing DataFrame, overwriting same service+load rows."""
    new_df = pd.DataFrame(new_records)
    if existing_df.empty:
        return new_df
    mask = existing_df.apply(
        lambda r: not any(
            r["service"] == nr["service"] and r["load"] == nr["load"]
            for nr in new_records
        ),
        axis=1,
    )
    return pd.concat([existing_df[mask], new_df], ignore_index=True)

# ── Benchmark main loop ────────────────────────────────────────────────────

def run_benchmarks(services, loads):
    new_records = []
    for label, users, spawn, dur in loads:
        print(f"\n{'='*60}")
        print(f"LOAD LEVEL: {label.upper()}  ({users} users / {dur}s)")
        print(f"{'='*60}")
        for svc in services:
            host, lf = ALL_SERVICES[svc]
            print(f"\n[{svc}] @ {host}")
            if not wait_for_service(host):
                print("  WARNING: service not reachable – skipping")
                continue
            try:
                prefix = run_locust(f"{svc}_{label}", host, lf, users, spawn, dur)
                stats  = read_stats(prefix)
                if stats:
                    new_records.append({
                        "service":  svc,
                        "load":     label,
                        "users":    users,
                        "rps":      float(stats.get("Requests/s") or 0),
                        "p50":      float(stats.get("50%")        or 0),
                        "p95":      float(stats.get("95%")        or 0),
                        "p99":      float(stats.get("99%")        or 0),
                        "failures": int(  stats.get("Failure Count") or 0),
                    })
                    print(f"  RPS={stats.get('Requests/s')}  p95={stats.get('95%')}ms")
            except Exception as exc:
                print(f"  ERROR: {exc}")
    return new_records

# ── Chart helpers ──────────────────────────────────────────────────────────

_LOAD_COLORS = ["#5C9BD6", "#E8A838", "#E05C5C"]


def _bar_chart(df, services, load_labels, metric, ylabel, title, filename,
               log_scale=False):
    """
    Grouped bar chart.
    X-axis  = services
    Groups  = load levels (one bar per load per service)
    """
    if df.empty or not services:
        return

    n_loads = len(load_labels)
    width   = 0.75 / max(n_loads, 1)
    x       = list(range(len(services)))

    fig, ax = plt.subplots(figsize=(max(7, len(services) * 1.8 + 1), 5))

    for i, load in enumerate(load_labels):
        vals = []
        for svc in services:
            sub = df[(df["service"] == svc) & (df["load"] == load)]
            vals.append(float(sub[metric].values[0]) if not sub.empty else 0)

        offset = (i - n_loads / 2 + 0.5) * width
        bars = ax.bar(
            [xi + offset for xi in x], vals,
            width=width * 0.9,
            label=load,
            color=_LOAD_COLORS[i % len(_LOAD_COLORS)],
            edgecolor="white",
            linewidth=0.5,
        )
        for bar, v in zip(bars, vals):
            if v > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * (1.06 if log_scale else 1.02),
                    f"{v:.0f}",
                    ha="center", va="bottom", fontsize=7,
                )

    ax.set_xticks(x)
    ax.set_xticklabels(services, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.legend(title="Load level", fontsize=8)
    ax.grid(axis="y", alpha=0.3)

    if log_scale:
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(ticker.ScalarFormatter())
        ax.yaxis.set_minor_formatter(ticker.NullFormatter())

    plt.tight_layout()
    path = os.path.join(OUT_DIR, filename)
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved {path}")


def _line_chart(df, services, metric, ylabel, title, filename, log_scale=False):
    """
    Line chart.
    X-axis = concurrent users (50, 200, 500)
    One line per service
    """
    if df.empty or not services:
        return

    user_vals = sorted(df["users"].unique())
    fig, ax   = plt.subplots(figsize=(9, 5))

    for svc in services:
        sub  = df[df["service"] == svc].sort_values("users")
        vals = [
            float(sub[sub["users"] == u][metric].values[0])
            if not sub[sub["users"] == u].empty else 0
            for u in user_vals
        ]
        ax.plot(user_vals, vals, marker="o", label=svc,
                color=COLORS.get(svc, None), linewidth=2, markersize=6)

    ax.set_xlabel("Concurrent users")
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(True, alpha=0.3)
    ax.set_xticks(user_vals)

    if log_scale:
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(ticker.ScalarFormatter())
        ax.yaxis.set_minor_formatter(ticker.NullFormatter())

    plt.tight_layout()
    path = os.path.join(OUT_DIR, filename)
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved {path}")

# ── Table helpers ──────────────────────────────────────────────────────────

def _safe_log10(v):
    return round(math.log10(v), 3) if v > 0 else None


def generate_tables(df):
    """
    Produce three pivot CSV tables:
      table_RPS.csv       – throughput (req/s)
      table_p95_ms.csv    – 95th-percentile latency in ms
      table_log10_p95.csv – log10 of p95 (useful to compress the python-soap outlier)
    """
    if df.empty:
        return

    loads_order   = ["low", "medium", "high"]
    present_loads = [l for l in loads_order if l in df["load"].values]
    svc_order     = list(ALL_SERVICES.keys())
    present_svcs  = [s for s in svc_order if s in df["service"].values]

    for metric, label, transform in [
        ("rps", "RPS",        lambda v: round(v, 1)),
        ("p95", "p95_ms",     lambda v: round(v, 1)),
        ("p95", "log10_p95",  _safe_log10),
    ]:
        rows = []
        for svc in present_svcs:
            row = {"service": svc}
            for load in present_loads:
                sub = df[(df["service"] == svc) & (df["load"] == load)]
                row[load] = (
                    transform(float(sub[metric].values[0]))
                    if not sub.empty else None
                )
            rows.append(row)

        out_path = os.path.join(OUT_DIR, f"table_{label}.csv")
        pd.DataFrame(rows).to_csv(out_path, index=False)
        print(f"  Saved {out_path}")

# ── Chart generation orchestrator ─────────────────────────────────────────

def generate_charts(df):
    if df.empty:
        print("No data available to generate charts.")
        return

    svc_order     = list(ALL_SERVICES.keys())
    present_svcs  = [s for s in svc_order if s in df["service"].values]
    loads_order   = ["low", "medium", "high"]
    present_loads = [l for l in loads_order if l in df["load"].values]

    # ── 1. Line charts: all services vs concurrency ────────────────────────
    print("\n── Line charts (all services) ───────────────────────────────────")
    _line_chart(
        df, present_svcs, "rps",
        "Requests/s",
        "Throughput vs. Concurrency – all services",
        "chart_lines_rps.png",
    )
    _line_chart(
        df, present_svcs, "p95",
        "p95 latency (ms) – logarithmic scale",
        "p95 Latency vs. Concurrency – log scale, all services",
        "chart_lines_p95_log.png",
        log_scale=True,
    )

    # ── 2. Per-API charts: same API, Go vs Python ─────────────────────────
    print("\n── Bar charts per API (Go vs Python, same protocol) ─────────────")
    for api, api_svcs in API_MAP.items():
        svcs = [s for s in api_svcs if s in present_svcs]
        if not svcs:
            continue
        _bar_chart(
            df, svcs, present_loads, "rps",
            "Requests/s",
            f"{api.upper()} – Throughput: Go vs Python",
            f"chart_api_{api}_rps.png",
        )
        _bar_chart(
            df, svcs, present_loads, "p95",
            "p95 latency (ms) – log scale",
            f"{api.upper()} – p95 Latency: Go vs Python",
            f"chart_api_{api}_p95.png",
            log_scale=True,
        )

    # ── 3. Per-technology charts: same tech, all APIs ─────────────────────
    print("\n── Bar charts per technology (all protocols, same language) ──────")
    for tech, tech_svcs in TECH_MAP.items():
        svcs = [s for s in tech_svcs if s in present_svcs]
        if not svcs:
            continue
        _bar_chart(
            df, svcs, present_loads, "rps",
            "Requests/s",
            f"{tech.capitalize()} – Throughput across protocols",
            f"chart_tech_{tech}_rps.png",
        )
        _bar_chart(
            df, svcs, present_loads, "p95",
            "p95 latency (ms) – log scale",
            f"{tech.capitalize()} – p95 Latency across protocols",
            f"chart_tech_{tech}_p95.png",
            log_scale=True,
        )

    # ── 4. Summary tables ─────────────────────────────────────────────────
    print("\n── Summary tables ───────────────────────────────────────────────")
    generate_tables(df)

# ── Entry point ────────────────────────────────────────────────────────────

def main():
    args     = parse_args()
    services = filter_services(args.tech, args.api)
    loads    = filter_loads(args.load)

    if not services:
        print("ERROR: No services match the given filters.\n"
              "Available --tech: go, python\n"
              "Available --api:  rest, graphql, grpc, soap")
        sys.exit(1)
    if not loads:
        print("ERROR: No load levels match the given filter.\n"
              "Available --load: low, medium, high")
        sys.exit(1)

    print(f"Services to test : {services}")
    print(f"Load levels      : {[l[0] for l in loads]}")

    if args.charts_only:
        print("\n[--charts-only] Skipping Locust – loading existing results …")
        df = load_existing_results()
        if df.empty:
            print("ERROR: results/all_results.csv not found. Run benchmarks first.")
            sys.exit(1)
    else:
        new_records = run_benchmarks(services, loads)
        if not new_records:
            print("\nNo results collected. Exiting.")
            return

        existing_df = load_existing_results()
        df          = merge_results(existing_df, new_records)
        df.to_csv(os.path.join(OUT_DIR, "all_results.csv"), index=False)
        print(f"\nSaved all_results.csv  ({len(df)} rows total)")

    generate_charts(df)
    print("\nDONE – results saved to ./results/")


if __name__ == "__main__":
    main()

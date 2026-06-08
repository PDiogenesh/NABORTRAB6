#!/usr/bin/env python3
"""
run_benchmarks.py – Automated load-test runner + chart generator.

Runs three load levels against all 8 services and produces comparison charts.

Requirements (host machine):
  pip install locust matplotlib pandas requests

Usage:
  python run_benchmarks.py
"""

import subprocess, time, csv, os, sys, io
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# ── Config ────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SERVICES = {
    "go-rest":       ("http://localhost:8001", "locust/locustfile_rest.py"),
    "go-graphql":    ("http://localhost:8002", "locust/locustfile_graphql.py"),
    "go-soap":       ("http://localhost:8004", "locust/locustfile_soap.py"),
    "python-rest":   ("http://localhost:8011", "locust/locustfile_rest.py"),
    "python-graphql":("http://localhost:8012", "locust/locustfile_graphql.py"),
    "python-soap":   ("http://localhost:8014", "locust/locustfile_soap.py"),
}

# Three load levels: (users, spawn_rate, duration_seconds)
LOADS = [
    ("low",    50,  10, 60),
    ("medium", 200, 20, 60),
    ("high",   500, 50, 60),
]

OUT_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────

def wait_for_service(url, retries=30):
    for _ in range(retries):
        try:
            r = requests.get(f"{url}/health", timeout=3)
            if r.status_code < 400:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


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
    print(f"  → {' '.join(cmd)}")
    subprocess.run(cmd, cwd=BASE_DIR, check=True)
    return csv_prefix


def read_stats(csv_prefix):
    stats_file = csv_prefix + "_stats.csv"
    if not os.path.exists(stats_file):
        return None
    with open(stats_file, newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    # Aggregated row
    for row in reader:
        if row.get("Name", "").lower() in ("aggregated", "total", ""):
            return row
    return reader[-1] if reader else None


# ── Main ──────────────────────────────────────────────────────

def main():
    all_results = []  # [{service, load_label, users, rps, p50, p95, p99, failures}]

    for label, users, spawn, dur in LOADS:
        print(f"\n{'='*60}")
        print(f"LOAD LEVEL: {label.upper()} ({users} users)")
        print(f"{'='*60}")

        for svc, (host, lf) in SERVICES.items():
            print(f"\n[{svc}] @ {host}")
            ok = wait_for_service(host)
            if not ok:
                print(f"  ⚠ Service not reachable – skipping")
                continue

            try:
                prefix = run_locust(f"{svc}_{label}", host, lf, users, spawn, dur)
                stats = read_stats(prefix)
                if stats:
                    all_results.append({
                        "service": svc,
                        "load": label,
                        "users": users,
                        "rps": float(stats.get("Requests/s") or 0),
                        "p50": float(stats.get("50%") or 0),
                        "p95": float(stats.get("95%") or 0),
                        "p99": float(stats.get("99%") or 0),
                        "failures": int(stats.get("Failure Count") or 0),
                    })
                    print(f"  RPS={stats.get('Requests/s')}  p95={stats.get('95%')}ms")
            except Exception as e:
                print(f"  ✗ Error: {e}")

    if not all_results:
        print("\nNo results collected. Exiting.")
        return

    df = pd.DataFrame(all_results)
    df.to_csv(os.path.join(OUT_DIR, "all_results.csv"), index=False)

    # ── Charts ────────────────────────────────────────────────

    loads = [l for l, *_ in LOADS]
    services = list(SERVICES.keys())
    colors = plt.cm.tab10.colors

    for metric, ylabel, title in [
        ("rps",  "Requests/s",       "Throughput (higher = better)"),
        ("p95",  "p95 latency (ms)", "p95 Latency (lower = better)"),
    ]:
        fig, axes = plt.subplots(1, len(loads), figsize=(6*len(loads), 6), sharey=False)
        if len(loads) == 1:
            axes = [axes]

        for ax, load in zip(axes, loads):
            sub = df[df["load"] == load]
            vals = [sub[sub["service"] == s][metric].values[0]
                    if not sub[sub["service"] == s].empty else 0
                    for s in services]
            bars = ax.bar(services, vals, color=colors[:len(services)], edgecolor="white")
            ax.set_title(f"Load: {load}", fontsize=12)
            ax.set_xlabel("Service")
            ax.set_ylabel(ylabel)
            ax.tick_params(axis="x", rotation=30)
            for bar, val in zip(bars, vals):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(vals)*0.01,
                        f"{val:.0f}", ha="center", va="bottom", fontsize=8)

        fig.suptitle(title, fontsize=14, fontweight="bold")
        plt.tight_layout()
        out_path = os.path.join(OUT_DIR, f"chart_{metric}.png")
        plt.savefig(out_path, dpi=150)
        plt.close()
        print(f"\n✓ Saved {out_path}")

    # ── Multi-load line chart ─────────────────────────────────

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    for i, svc in enumerate(services):
        sub = df[df["service"] == svc]
        rps_vals = [sub[sub["load"] == l]["rps"].values[0]
                    if not sub[sub["load"] == l].empty else 0 for l in loads]
        p95_vals = [sub[sub["load"] == l]["p95"].values[0]
                    if not sub[sub["load"] == l].empty else 0 for l in loads]
        user_vals = [u for _, u, *_ in LOADS]

        ax1.plot(user_vals, rps_vals, marker="o", label=svc, color=colors[i])
        ax2.plot(user_vals, p95_vals, marker="o", label=svc, color=colors[i])

    ax1.set_title("Throughput vs. Concurrency", fontsize=13)
    ax1.set_xlabel("Concurrent users"); ax1.set_ylabel("Requests/s")
    ax1.legend(fontsize=8); ax1.grid(True, alpha=0.3)

    ax2.set_title("p95 Latency vs. Concurrency", fontsize=13)
    ax2.set_xlabel("Concurrent users"); ax2.set_ylabel("p95 latency (ms)")
    ax2.legend(fontsize=8); ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = os.path.join(OUT_DIR, "chart_comparison_lines.png")
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"✓ Saved {out_path}")

    print("\n✅ Benchmarking complete. Results in ./results/")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Portable 16-Stage Multi-Core Reproduction Campaign Runner.

Runs the entire experimental suite from raw .vrp instances to compiled LaTeX PDFs
using multi-core process pools (completes in ~6.7 minutes on Apple M4 10-core).
"""
import argparse
import csv
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXP = REPO_ROOT / "experiments"
RESULTS = EXP / "results"
INSTANCES = REPO_ROOT / "instances"
CHECKER = REPO_ROOT / "check" / "target" / "release" / "check_cvrp"
PY = sys.executable

INIT_X = REPO_ROOT / "cvrplib_x_initial"
HOLD_X = REPO_ROOT / "cvrplib_x_holdout"
INIT_X.mkdir(exist_ok=True)
HOLD_X.mkdir(exist_ok=True)

mpl_dir = Path(tempfile.gettempdir()) / "vrp_multicore_mpl"
mpl_dir.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(mpl_dir))

timings = []
campaign_t0 = time.perf_counter()


def run_step(step_num: int, title: str, fn):
    print(f"\n[{step_num:02d}/16] START: {title}", flush=True)
    t0 = time.perf_counter()
    fn()
    dt = time.perf_counter() - t0
    timings.append((step_num, title, dt))
    print(f"[{step_num:02d}/16] DONE in {dt:.2f} s ({dt/60:.2f} min): {title}", flush=True)


def cmd(args, cwd=None, stdout_file=None):
    if stdout_file:
        with open(stdout_file, "w", encoding="utf-8") as out:
            subprocess.run([str(a) for a in args], cwd=str(cwd or REPO_ROOT),
                           stdout=out, stderr=subprocess.PIPE, text=True, check=True)
    else:
        subprocess.run([str(a) for a in args], cwd=str(cwd or REPO_ROOT), check=True)


def step01():
    initial_parents = (
        "X-n101-k25", "X-n106-k14", "X-n110-k13", "X-n115-k10", "X-n120-k6",
        "X-n125-k30", "X-n129-k18", "X-n134-k13", "X-n139-k10", "X-n143-k7"
    )
    with (EXP / "holdout_parents.csv").open() as f:
        holdout_parents = [r["parent"] for r in csv.DictReader(f)]
    base_url = "https://raw.githubusercontent.com/VROOM-Project/vroom-scripts/0f5ee1eb625d287101686d11622d03e43ec0c969/benchmarks/CVRP/X"
    for p in initial_parents:
        dest = INIT_X / f"{p}.vrp"
        if not dest.exists():
            req = urllib.request.Request(f"{base_url}/{p}.vrp", headers={"User-Agent": "vrp-repro"})
            with urllib.request.urlopen(req) as resp:
                dest.write_bytes(resp.read())
    for p in holdout_parents:
        dest = HOLD_X / f"{p}.vrp"
        if not dest.exists():
            req = urllib.request.Request(f"{base_url}/{p}.vrp", headers={"User-Agent": "vrp-repro"})
            with urllib.request.urlopen(req) as resp:
                dest.write_bytes(resp.read())
    if not CHECKER.exists():
        cmd(["cargo", "build", "--release"], cwd=REPO_ROOT / "check")
    p1 = subprocess.Popen(["clang++", "-std=c++17", "-O3", str(EXP / "replay_tc_exact.cpp"), "-o", str(REPO_ROOT / "replay_bin")])
    p2 = subprocess.Popen(["clang++", "-std=c++17", "-O3", "-Wall", "-Wextra", "-pedantic", str(EXP / "exact.cpp"), "-o", str(REPO_ROOT / "exact_bin")])
    if p1.wait() != 0 or p2.wait() != 0:
        raise RuntimeError("C++ compilation failed")


def step16():
    cmd([PY, REPO_ROOT / "paper" / "figures.py", INSTANCES])
    p1 = subprocess.Popen(["pdflatex", "-interaction=nonstopmode", "main.tex"],
                          cwd=str(REPO_ROOT / "paper"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p2 = subprocess.Popen(["pdflatex", "-interaction=nonstopmode", "supplement.tex"],
                          cwd=str(REPO_ROOT / "paper"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if p1.wait() != 0 or p2.wait() != 0:
        raise RuntimeError("pdflatex compilation failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=None,
                        help="Number of parallel worker processes (default: auto-detect CPU cores; set 1 for strict single-core timing)")
    args = parser.parse_args()
    if args.workers is not None:
        os.environ["VRP_WORKERS"] = str(max(1, args.workers))
    workers_desc = os.environ.get("VRP_WORKERS", f"auto ({os.cpu_count() or 4} cores)")
    print(f"=== Running Full 16-Stage Campaign | Workers: {workers_desc} ===", flush=True)
    run_step(1, "Verify/download 30 CVRPLIB-X parents, check_cvrp & compile C++17 binaries", step01)
    run_step(2, "Replay TC-Exact across 55 XSH instances (tc_exact_replay.csv)",
             lambda: cmd([REPO_ROOT / "replay_bin", INSTANCES], stdout_file=RESULTS / "tc_exact_replay.csv"))
    run_step(3, "5-Level Capacity Sweep + HiGHS MILP + QOBLIB check_cvrp (benchmark.py)",
             lambda: cmd([PY, EXP / "benchmark.py", "--instances", INSTANCES, "--output", RESULTS,
                          "--binary", REPO_ROOT / "exact_bin", "--checker", CHECKER,
                          "--repeats", "5", "--stress-repeats", "2", "--time-limit", "10"]))
    run_step(4, "Audit 275 solutions with check_cvrp & generate capacity summary (report.py)",
             lambda: cmd([PY, EXP / "report.py", "--results", RESULTS, "--instances", INSTANCES, "--checker", CHECKER]))
    run_step(5, "4-Unit Capacity Allocation Profiles + Set-Partitioning MILP + LOOCV (allocation.py)",
             lambda: (cmd([PY, EXP / "allocation.py", INSTANCES, REPO_ROOT / "exact_bin"]),
                      cmd([PY, EXP / "summarize_allocation.py"])))
    run_step(6, "1 Overload Profile vs. 5 Fixed-Design HiGHS MILPs Benchmark (five_design_benchmark.py)",
             lambda: cmd([PY, EXP / "five_design_benchmark.py", INSTANCES]))
    run_step(7, "Partial Fleet Upgrades & 3-Mode DP Budget Curves (upgrades.py & budget_profiles.py)",
             lambda: (cmd([PY, EXP / "upgrades.py", INSTANCES, REPO_ROOT / "exact_bin"]),
                      cmd([PY, EXP / "budget_profiles.py", INSTANCES, REPO_ROOT / "exact_bin"])))
    run_step(8, "Paired Early vs. Late Load-Filtering Ablation across 3 Slack Levels (robustness.py ablation)",
             lambda: cmd([PY, EXP / "robustness.py", "ablation", "--instances", INSTANCES, "--binary", REPO_ROOT / "exact_bin"]))
    run_step(9, "Independent Two-Index Edge-Flow MILP with Rounded-Capacity Cuts at +5% (robustness.py arc)",
             lambda: cmd([PY, EXP / "robustness.py", "arc", "--instances", INSTANCES, "--seconds", "10"]))
    run_step(10, "51-Shuffle Demand Reassignment Control — 5,610 Exact Solves (geometry_control.py)",
             lambda: (cmd([PY, EXP / "geometry_control.py", INSTANCES, REPO_ROOT / "exact_bin"]),
                      cmd([PY, EXP / "summarize_geometry.py"])))
    run_step(11, "Exact Polynomial Generating-Function Load Profiles across 325 Configs (load_profile.py)",
             lambda: cmd([PY, EXP / "load_profile.py", INSTANCES, INIT_X]))
    run_step(12, "External CVRPLIB-X 20-Customer Subsamples Ablation & Placement Transfer (external_*.py)",
             lambda: (cmd([PY, EXP / "external_ablation.py", INIT_X, REPO_ROOT / "exact_bin"]),
                      cmd([PY, EXP / "external_geometry.py", INIT_X, REPO_ROOT / "exact_bin"])))
    run_step(13, "6-Vehicle MILP Transfer & Completion Bounds on 10 Initial Parents (allocation_transfer.py)",
             lambda: (cmd([PY, EXP / "allocation_transfer.py", INIT_X]),
                      cmd([PY, EXP / "allocation_transfer.py", INIT_X, "--complete-designs"]),
                      cmd([PY, EXP / "allocation_certificates.py"])))
    run_step(14, "6-Vehicle Exact Overload Profiles across 10 Initial + 20 Holdout Parents + MILP Checks",
             lambda: (cmd([PY, EXP / "six_vehicle_profiles.py", INIT_X]),
                      cmd([PY, EXP / "six_vehicle_profiles.py", HOLD_X, "--holdout"]),
                      cmd([PY, EXP / "holdout_summary.py", "--check-milp", HOLD_X]),
                      cmd([PY, EXP / "holdout_summary.py"])))
    run_step(15, "6-Vehicle Anchored Join Ablation (0/2/3-Anchor) & LP Subset-Row Cut Certificates",
             lambda: (cmd([PY, EXP / "anchor_ablation.py", INIT_X, HOLD_X]),
                      cmd([PY, EXP / "regret_bound.py", INIT_X, HOLD_X]),
                      cmd([PY, EXP / "summarize_anchors.py"])))
    run_step(16, "Regenerate All Paper Figures, Appendix Tables & Compile main.pdf + supplement.pdf in parallel",
             step16)

    total_dt = time.perf_counter() - campaign_t0
    print("\n" + "=" * 95)
    print("  COMPLETE 16-STAGE MULTI-CORE REPRODUCTION CAMPAIGN SUMMARY")
    print("=" * 95)
    for num, title, dt in timings:
        print(f"  Step {num:02d} | {dt:8.2f} s ({dt/60:5.2f} min) | {title}")
    print("-" * 95)
    print(f"  TOTAL MULTI-CORE CAMPAIGN WALL-CLOCK TIME: {total_dt:.2f} s ({total_dt/60:.2f} minutes)")
    print("=" * 95, flush=True)


if __name__ == "__main__":
    main()

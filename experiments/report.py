#!/usr/bin/env python3
"""Audit saved results, summarize paired effects, and render the benchmark figure."""

import argparse
import csv
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from benchmark import NAMES, SCENARIOS, check_official, read_instance, write_csv


LABELS = ("Original", "+1 unit", "+2%", "+5%", "+10%")


def records(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def verify_files(results, instance_directory, checker):
    expected = {(name, scenario) for name in NAMES for scenario, _ in SCENARIOS}
    metadata = json.loads((results / "metadata.json").read_text())
    instances = {name: read_instance(instance_directory / f"{name}.vrp") for name in NAMES}
    if metadata["input_sha256"] != {name: item.sha256 for name, item in instances.items()}:
        raise ValueError("Input hashes differ from the benchmark manifest")
    data = json.loads((results / "solutions.json").read_text())
    rows = {(r["instance"], r["scenario"]): r for r in records(results / "per_instance.csv")
            if r["mode"] == "bounded"}
    seen = set()
    for record in data:
        name, scenario = record["instance"], record["scenario"]
        key = (name, scenario)
        if key in seen or key not in expected:
            raise ValueError(f"Unexpected or duplicate solution {key}")
        seen.add(key)
        capacity, objective = record["capacity"], record["objective"]
        if (capacity, objective) != (int(rows[key]["capacity"]), int(rows[key]["objective"])):
            raise ValueError(f"Solution and result disagree for {key}")
        routes = record["routes"]
        if len(routes) != 4 or sorted(c for r in routes for c in r["customers"]) != list(range(1, 21)):
            raise ValueError(f"Invalid customer coverage for {key}")
        item = instances[name]
        total = 0
        for route in routes:
            customers = route["customers"]
            closed = (0, *customers, 0)
            cost = sum(item.distance[a][b] for a, b in zip(closed, closed[1:]))
            load = sum(item.demand[c - 1] for c in customers)
            if not 0 < load <= capacity or (cost, load) != (route["cost"], route["load"]):
                raise ValueError(f"Invalid saved tour cost or demand for {key}")
            total += cost
        if total != objective:
            raise ValueError(f"Invalid saved objective for {key}")
        if checker:
            check_official(checker, instance_directory / f"{name}.vrp", routes, capacity, objective)
    if seen != expected:
        raise ValueError(f"Missing {len(expected - seen)} solutions")
    output = {"verified_solutions": len(seen), "official_qoblib_checker": bool(checker),
              "qoblib_commit": metadata["qoblib_commit"]}
    (results / "solution_verification.json").write_text(json.dumps(output, indent=2) + "\n")


def summarize(results):
    rows = records(results / "per_instance.csv")
    by_key = {(r["instance"], r["scenario"], r["mode"]): r for r in rows}
    if len(rows) != len(by_key) or len(rows) != 6 * len(NAMES):
        raise ValueError("Expected five capacity levels and one pricing ablation per instance")
    original = {name: by_key[name, "original", "bounded"] for name in NAMES}
    replay = {r["instance"]: r for r in records(results / "tc_exact_replay.csv")}
    for name, row in original.items():
        for left, right in (("candidate_routes", "tight_subsets"), ("partitions", "partitions"),
                            ("objective", "optimum"), ("second_distinct_objective", "second_distinct_cost")):
            if row[left] != replay[name][right]:
                raise ValueError(f"TC-Exact replay differs for {name}, {left}")
    ablation = [by_key[name, "original", "capacity_only"] for name in NAMES]
    paired = {
        "instances": len(NAMES),
        "reference_and_tc_exact_replay_matches": len(NAMES),
        "capacity_only_candidates_median": statistics.median(int(r["candidate_routes"]) for r in ablation),
        "capacity_only_pricing_ms_median": statistics.median(float(r["pricing_ms"]) for r in ablation),
        "bounded_pricing_ms_median": statistics.median(float(r["pricing_ms"]) for r in original.values()),
        "candidate_reduction_factor_paired_median": statistics.median(
            int(r["candidate_routes"]) / int(original[r["instance"]]["candidate_routes"]) for r in ablation),
        "pricing_speedup_factor_paired_median": statistics.median(
            float(r["pricing_ms"]) / float(original[r["instance"]]["pricing_ms"]) for r in ablation),
    }
    (results / "pricing_ablation.json").write_text(json.dumps(paired, indent=2) + "\n")
    summary, groups = [], []
    for scenario, _ in SCENARIOS:
        block = [by_key[name, scenario, "bounded"] for name in NAMES]
        candidates = [int(r["candidate_routes"]) for r in block]
        partitions = [int(r["partitions"]) for r in block]
        solve = [float(r["exact_ms"]) for r in block]
        reduction = [100 * (int(original[r["instance"]]["objective"]) - int(r["objective"]))
                     / int(original[r["instance"]]["objective"]) for r in block]
        groups.append((candidates, partitions, solve, reduction))
        summary.append({
            "scenario": scenario, "instances": len(block),
            "fleet_slack_min": min(int(r["fleet_slack"]) for r in block),
            "fleet_slack_max": max(int(r["fleet_slack"]) for r in block),
            "candidate_routes_median": statistics.median(candidates),
            "partition_count_median": statistics.median(partitions),
            "paired_partition_factor_median": statistics.median(
                int(r["partitions"]) / int(original[r["instance"]]["partitions"]) for r in block),
            "exact_ms_median": round(statistics.median(solve), 4),
            "pricing_ms_median": round(statistics.median(float(r["pricing_ms"]) for r in block), 4),
            "cover_ms_median": round(statistics.median(float(r["cover_ms"]) for r in block), 4),
            "cost_improved_instances": sum(value > 0 for value in reduction),
            "paired_cost_reduction_pct_median": round(statistics.median(reduction), 4),
            "milp_optimal": sum(r["milp_status"] == "0" for r in block),
            "milp_limit": sum(r["milp_status"] == "1" for r in block),
            "milp_attempted": sum(bool(r["milp_status"]) for r in block),
        })
    write_csv(results / "scenario_summary.csv", summary)
    return groups


def draw(results, groups):
    figure, axes = plt.subplots(2, 2, figsize=(9, 5.8), layout="constrained")
    panels = (("Candidate routes", True), ("Feasible four-route partitions", True),
              ("Exact runtime (ms)", True), ("Cost reduction vs. original (%)", False))
    positions = np.arange(len(LABELS))
    for i, (axis, (label, logarithmic)) in enumerate(zip(axes.flat, panels)):
        low, median, high = np.percentile([group[i] for group in groups], [25, 50, 75], axis=1)
        axis.fill_between(positions, low, high, color="#286385", alpha=.2, linewidth=0)
        axis.plot(positions, median, "o-", color="#184D6A", linewidth=2, markersize=4)
        axis.set(xticks=positions, xticklabels=LABELS, ylabel=label)
        if logarithmic:
            axis.set_yscale("log")
        axis.grid(axis="y", color="#dadfe2", linewidth=.6)
        axis.spines[["right", "top"]].set_visible(False)
    figure.suptitle("Capacity sensitivity across 55 QOBLIB CVRP instances\nMedian and interquartile range")
    figure.savefig(results / "capacity_sensitivity.png", dpi=300)
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--instances", type=Path, required=True)
    parser.add_argument("--checker", type=Path)
    args = parser.parse_args()
    verify_files(args.results, args.instances, args.checker.resolve() if args.checker else None)
    draw(args.results, summarize(args.results))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run the CVRP exact-cover and set-partitioning experiments from raw .vrp files."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from math import floor, hypot
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from urllib.request import urlopen
import warnings

import numpy as np
import scipy
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

QOBLIB_COMMIT = "55384509a610f040bea517a6c16079ce5c4edf0d"
QOBLIB_RAW = f"https://raw.githubusercontent.com/ZIB-AOPT/QOBLIB/{QOBLIB_COMMIT}"
NAMES = [f"XSH-n20-k4-{i:02}" for i in range(1, 56)]
SCENARIOS = (("original", 0), ("plus_1_unit", None), ("plus_2pct", 2),
             ("plus_5pct", 5), ("plus_10pct", 10))


@dataclass(frozen=True)
class Instance:
    name: str
    capacity: int
    demand: tuple[int, ...]
    distance: tuple[tuple[int, ...], ...]
    reference: int
    sha256: str


def fetch_instances(directory):
    directory.mkdir(parents=True, exist_ok=True)

    def fetch(name):
        path = directory / f"{name}.vrp"
        with urlopen(f"{QOBLIB_RAW}/09-routing/instances/{path.name}", timeout=30) as response:
            path.write_bytes(response.read())

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(fetch, NAMES))


def read_instance(path):
    data = path.read_bytes()
    headers = {}
    sections = {"NODE_COORD_SECTION": [], "DEMAND_SECTION": [], "DEPOT_SECTION": []}
    section = None
    for line in data.decode("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "EOF":
            break
        if line in sections:
            section = line
        elif section is None:
            key, value = line.split(":", maxsplit=1)
            headers[key.strip()] = value.strip()
        else:
            sections[section].append(line.split())
    if headers["NAME"] != path.stem or headers["TYPE"] != "CVRP":
        raise ValueError(f"Unexpected name or type in {path}")
    if headers["DIMENSION"] != "21" or headers["EDGE_WEIGHT_TYPE"] != "EUC_2D":
        raise ValueError(f"Unexpected dimension or distance metric in {path}")
    coords = {int(i): (float(x), float(y)) for i, x, y in sections["NODE_COORD_SECTION"]}
    demand = {int(i): int(q) for i, q in sections["DEMAND_SECTION"]}
    if (set(coords) != set(range(1, 22)) or set(demand) != set(coords)
            or sections["DEPOT_SECTION"] != [["1"], ["-1"]] or demand[1] != 0
            or len(sections["DEMAND_SECTION"]) != 21 or len(sections["NODE_COORD_SECTION"]) != 21):
        raise ValueError(f"Unexpected node or depot data in {path}")
    customer_demand = tuple(demand[i] for i in range(2, 22))
    capacity = int(headers["CAPACITY"])
    if min(customer_demand) <= 0 or sum(customer_demand) != 4 * capacity:
        raise ValueError(f"Expected positive demands and a saturated fleet in {path}")
    distance = tuple(tuple(floor(hypot(coords[i][0] - coords[j][0],
                                       coords[i][1] - coords[j][1]) + 0.5)
                           for j in range(1, 22)) for i in range(1, 22))
    reference = re.search(r"Optimal cost:\s*(\d+)", headers["COMMENT"])
    if reference is None:
        raise ValueError(f"Missing reference cost in {path}")
    return Instance(path.stem, capacity, customer_demand, distance,
                    int(reference.group(1)), hashlib.sha256(data).hexdigest())


def customer_ids(mask):
    return tuple(i + 1 for i in range(20) if mask & (1 << i))


def exact_run(binary, instance, capacity, min_load, repeats, export_costs, timeout=None):
    data = [capacity, min_load, repeats, int(export_costs), *instance.demand]
    data.extend(d for row in instance.distance for d in row)
    output = subprocess.run([str(binary)], input=" ".join(map(str, data)), text=True,
                            capture_output=True, check=True, timeout=timeout).stdout.splitlines()
    candidates, partitions, ties, optimum, second = map(int, output[0].split())
    masks = tuple(map(int, output[1].split()))
    timings = [tuple(map(float, line.split())) for line in output[2:2 + repeats]]
    columns = [tuple(map(int, line.split())) for line in output[2 + repeats:]]
    if not partitions or not ties or (export_costs and len(columns) != candidates):
        raise ValueError(f"Exact solver output is incomplete for {instance.name}")
    result = {
        "candidate_routes": candidates,
        "partitions": partitions,
        "optimal_partitions": ties,
        "objective": optimum,
        "second_distinct_objective": None if second == -1 else second,
        "pricing_ms": statistics.median(t[0] for t in timings),
        "cover_ms": statistics.median(t[1] for t in timings),
        "exact_ms": statistics.median(sum(t) for t in timings),
    }
    return result, masks, columns, timings


def verify_and_reconstruct(instance, capacity, masks, objective):
    if len(masks) != 4 or sorted(x for mask in masks for x in customer_ids(mask)) != list(range(1, 21)):
        raise ValueError(f"Invalid customer coverage for {instance.name}")
    distance = instance.distance

    @lru_cache(maxsize=None)
    def best_tail(previous, remaining):
        if not remaining:
            return distance[previous][0], ()
        return min((distance[previous][node] + cost, (node, *tail))
                   for i, node in enumerate(remaining)
                   for cost, tail in [best_tail(node, remaining[:i] + remaining[i + 1:])])

    routes = []
    for mask in masks:
        nodes = customer_ids(mask)
        load = sum(instance.demand[node - 1] for node in nodes)
        if not 0 < load <= capacity:
            raise ValueError(f"Invalid route load for {instance.name}")
        _, route = best_tail(0, nodes)
        closed = (0, *route, 0)
        cost = sum(distance[a][b] for a, b in zip(closed, closed[1:]))
        routes.append({"customers": route, "load": load, "cost": cost})
    if sum(route["cost"] for route in routes) != objective:
        raise ValueError(f"Recomputed tour costs disagree for {instance.name}")
    return routes


def milp_run(columns, time_limit):
    start = perf_counter()
    rows, indices = [], []
    for j, (mask, _) in enumerate(columns):
        covered = customer_ids(mask)
        rows.extend([*(i - 1 for i in covered), 20])
        indices.extend([j] * (len(covered) + 1))
    matrix = coo_matrix((np.ones(len(rows)), (rows, indices)),
                        shape=(21, len(columns))).tocsc()
    rhs = np.array([1] * 20 + [4])
    costs = np.array([cost for _, cost in columns], dtype=float)
    with warnings.catch_warnings():
        # SciPy passes HiGHS-specific options through after this warning.
        warnings.filterwarnings("ignore", message="Unrecognized options detected",
                                category=RuntimeWarning)
        result = milp(costs, integrality=np.ones(len(columns)),
                      bounds=Bounds(0, 1), constraints=LinearConstraint(matrix, rhs, rhs),
                      options={"time_limit": time_limit, "mip_rel_gap": 0.0, "threads": 1})
    masks = tuple(mask for (mask, _), x in zip(columns, result.x) if x > 0.5) if result.x is not None else ()
    return {
        "milp_status": int(result.status),
        "milp_objective": round(result.fun) if result.fun is not None else None,
        "milp_bound": getattr(result, "mip_dual_bound", None),
        "milp_gap": getattr(result, "mip_gap", None),
        "milp_ms": (perf_counter() - start) * 1000,
    }, masks


def check_official(checker, instance_path, routes, capacity, objective):
    with TemporaryDirectory(prefix="cita-check-") as directory:
        file = Path(directory) / instance_path.name
        contents = instance_path.read_text()
        file.write_text(re.sub(r"(?m)^CAPACITY\s*:\s*\d+", f"CAPACITY : {capacity}", contents))
        solution = file.with_suffix(".sol")
        lines = [f"Route #{i}: " + " ".join(map(str, route["customers"]))
                 for i, route in enumerate(routes, 1)]
        solution.write_text("\n".join([*lines, f"Cost {objective}"]) + "\n")
        output = subprocess.run([str(checker), str(file), str(solution)], text=True,
                                capture_output=True, check=True).stdout
        if f"Total cost: {objective}" not in output.splitlines() or "WARNING" in output:
            raise ValueError(f"QOBLIB checker cost mismatch for {file.name}")


def run_campaign(args):
    if args.download:
        fetch_instances(args.instances)
    args.output.mkdir(parents=True, exist_ok=True)
    names = args.names or NAMES
    rows, solution_records, timings_records, input_hashes = [], [], [], {}
    for name in names:
        instance_path = args.instances / f"{name}.vrp"
        instance = read_instance(instance_path)
        input_hashes[name] = instance.sha256
        previous = None
        for scenario, percent in SCENARIOS:
            increase = 1 if percent is None else (instance.capacity * percent + 99) // 100
            capacity = instance.capacity + increase
            slack = 4 * increase
            for mode in (("bounded", "capacity_only") if increase == 0 else ("bounded",)):
                min_load = max(1, capacity - slack) if mode == "bounded" else 1
                supplied_to_milp = mode == "bounded" and increase == 0
                repeats = args.stress_repeats if increase else args.repeats
                result, masks, columns, timings = exact_run(args.binary, instance, capacity,
                                                            min_load, repeats, supplied_to_milp)
                row = dict(instance=name, scenario=scenario, mode=mode,
                           original_capacity=instance.capacity, capacity=capacity,
                           fleet_slack=slack, minimum_load=min_load,
                           qoblib_reference=instance.reference if increase == 0 else None, **result)
                routes = verify_and_reconstruct(instance, capacity, masks, row["objective"])
                if args.checker:
                    check_official(args.checker, instance_path, routes, capacity, row["objective"])
                if supplied_to_milp:
                    comparison, milp_masks = milp_run(columns, args.time_limit)
                    row.update(comparison)
                    if milp_masks:
                        verify_and_reconstruct(instance, capacity, milp_masks, row["milp_objective"])
                    if (row["milp_status"] == 0 and
                            (row["milp_objective"] != row["objective"]
                             or abs(row["milp_bound"] - row["objective"]) > 1e-6)):
                        raise ValueError(f"HiGHS disagrees with exact cover for {name}: {row}")
                if increase == 0 and instance.reference != row["objective"]:
                    raise ValueError(f"QOBLIB reference cost differs for {name}: {row}")
                if mode == "capacity_only":
                    metrics = ("partitions", "optimal_partitions", "objective", "second_distinct_objective")
                    if any(previous[key] != row[key] for key in metrics):
                        raise ValueError(f"Unpruned pricing disagrees for {name}")
                else:
                    if previous and (row["objective"] > previous["objective"]
                                     or row["partitions"] < previous["partitions"]):
                        raise ValueError(f"Capacity expansion violated monotonicity for {name}")
                    previous = row
                    solution_records.append({"instance": name, "scenario": scenario, "capacity": capacity,
                                             "objective": row["objective"], "routes": routes})
                timings_records.extend(dict(instance=name, scenario=scenario, mode=mode, repeat=i,
                                            pricing_ms=t[0], cover_ms=t[1])
                                       for i, t in enumerate(timings, 1))
                rows.append(row)
        print(f"{name} verified", flush=True)

    write_csv(args.output / "per_instance.csv", rows)
    write_csv(args.output / "repetitions.csv", timings_records)
    (args.output / "solutions.json").write_text(json.dumps(solution_records, indent=2) + "\n")
    metadata = {
        "qoblib_commit": QOBLIB_COMMIT, "input_sha256": input_hashes,
        "system": platform.platform(), "python": platform.python_version(),
        "numpy": np.__version__, "scipy": scipy.__version__,
        "compiler": subprocess.check_output(["clang++", "--version"], text=True).splitlines()[0],
        "hardware": subprocess.run(["/usr/sbin/system_profiler", "SPHardwareDataType"],
                                   capture_output=True, text=True).stdout.split("Chip: ")[-1].splitlines()[0]
        if sys.platform == "darwin" else platform.processor(),
        "compile_flags": "-std=c++17 -O3 -Wall -Wextra -pedantic",
        "original_repetitions": args.repeats, "perturbed_repetitions": args.stress_repeats,
        "milp_scope": "original", "milp_time_limit_seconds": args.time_limit,
        "official_checker": bool(args.checker),
    }
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True,
                        help="Compiled exact.cpp executable")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--stress-repeats", type=int, default=2)
    parser.add_argument("--time-limit", type=float, default=5.0)
    parser.add_argument("--checker", type=Path, help="Optional official QOBLIB check_cvrp executable")
    parser.add_argument("--names", nargs="+", choices=NAMES, help="Optional subset for smoke testing")
    args = parser.parse_args()
    if min(args.repeats, args.stress_repeats) < 1 or args.time_limit <= 0:
        parser.error("repetition counts and --time-limit must be positive")
    args.binary = args.binary.resolve()
    if args.checker:
        args.checker = args.checker.resolve()
    run_campaign(args)


if __name__ == "__main__":
    main()

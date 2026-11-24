"""Paired pricing ablation and independent undirected arc MILP with capacity cuts."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from math import ceil
from pathlib import Path
from statistics import median
from time import perf_counter
import warnings

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix
from benchmark import pool_workers, NAMES, exact_run, read_instance, write_csv

ROOT = Path(__file__).resolve().parent


def _solve_ablation_instance(job):
    index, name, instances_dir, binary, ref_inst = job
    inst = read_instance(instances_dir / f"{name}.vrp")
    inst_rows = []
    for j, scenario in enumerate(("plus_1_unit", "plus_2pct", "plus_5pct")):
        base = ref_inst[scenario]
        capacity = int(base["capacity"])
        modes = [("bounded", max(1, sum(inst.demand) - 3 * capacity)), ("capacity_only", 1)]
        if (index + j) % 2:
            modes.reverse()
        for mode, low in modes:
            result, _, _, times = exact_run(binary, inst, capacity, low, 3, False)
            for key in ("objective", "partitions", "optimal_partitions", "second_distinct_objective"):
                if result[key] != int(base[key]):
                    raise ValueError((name, scenario, mode, key))
            for repetition, (pricing, cover) in enumerate(times, 1):
                inst_rows.append(dict(instance=name, scenario=scenario, mode=mode, repeat=repetition,
                                      candidates=result["candidate_routes"], partitions=result["partitions"],
                                      objective=result["objective"], pricing_ms=pricing, cover_ms=cover))
    return inst_rows


def ablation(args, reference):
    rows = []
    binary = args.binary.resolve()
    jobs = [(index, name, args.instances, binary,
             {sc: reference[name, sc] for sc in ("plus_1_unit", "plus_2pct", "plus_5pct")})
            for index, name in enumerate(NAMES)]
    with ProcessPoolExecutor(max_workers=pool_workers(8)) as pool:
        for block in pool.map(_solve_ablation_instance, jobs):
            rows.extend(block)
    write_csv(ROOT / "results/slack_ablation.csv", rows)
    summary = []
    for scenario in ("plus_1_unit", "plus_2pct", "plus_5pct"):
        factors = []
        for name in NAMES:
            pair = [[r for r in rows if (r["instance"], r["mode"], r["scenario"]) ==
                     (name, mode, scenario)] for mode in ("capacity_only", "bounded")]
            a, b = pair
            factors.append((a[0]["candidates"] / b[0]["candidates"],
                            median(r["pricing_ms"] for r in a) / median(r["pricing_ms"] for r in b),
                            median(r["pricing_ms"] + r["cover_ms"] for r in a) /
                            median(r["pricing_ms"] + r["cover_ms"] for r in b)))
        summary.append(dict(scenario=scenario, cases=len(factors), candidate_factor=median(x[0] for x in factors),
                            pricing_factor=median(x[1] for x in factors), total_factor=median(x[2] for x in factors),
                            pricing_faster=sum(x[1] > 1 for x in factors)))
    write_csv(ROOT / "results/slack_ablation_summary.csv", summary)


def arc_solve(inst, capacity, seconds):
    n = len(inst.demand)
    edges = [(i, j) for i in range(n + 1) for j in range(i + 1, n + 1)]
    costs = [inst.distance[i][j] for i, j in edges]
    matrix = [[int(node in edge) for edge in edges] for node in range(n + 1)]
    lower = [8] + [2] * n
    upper = list(lower)
    bounds = Bounds(0, [2 if i == 0 else 1 for i, _ in edges])
    cuts = set()
    start = perf_counter()
    bound, optimum, iterations = 0, None, 0
    while (remaining := seconds - (perf_counter() - start)) > .01:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Unrecognized options detected")
            result = milp(costs, integrality=np.ones(len(edges)), bounds=bounds,
                          constraints=LinearConstraint(csr_matrix(matrix), lower, upper),
                          options={"time_limit": remaining, "mip_rel_gap": 0, "threads": 1})
        iterations += 1
        dual = getattr(result, "mip_dual_bound", None)
        if dual is not None and np.isfinite(dual):
            bound = max(bound, ceil(dual - 1e-6))
        if result.x is None:
            break
        neighbors = {i: set() for i in range(1, n + 1)}
        for (i, j), value in zip(edges, result.x):
            if i and value > .5:
                neighbors[i].add(j)
                neighbors[j].add(i)
        unseen = set(neighbors)
        violated = []
        while unseen:
            group = {unseen.pop()}
            todo = list(group)
            while todo:
                for other in neighbors[todo.pop()] & unseen:
                    group.add(other)
                    unseen.remove(other)
                    todo.append(other)
            crossings = [int((i in group) != (j in group)) for i, j in edges]
            rhs = 2 * ceil(sum(inst.demand[i - 1] for i in group) / capacity)
            if np.dot(crossings, result.x) < rhs - .5:
                violated.append((frozenset(group), crossings, rhs))
        if not violated:
            optimum = round(result.fun)
            break
        for key, coefficients, rhs in violated:
            if key in cuts:
                raise ValueError("Repeated violated cut")
            cuts.add(key)
            matrix.append(coefficients)
            lower.append(rhs)
            upper.append(np.inf)
    return dict(arc_incumbent=optimum, arc_lower_bound=bound, cuts=len(cuts), iterations=iterations,
                elapsed_s=round(perf_counter() - start, 3))


def _solve_arc_job(job):
    rank, name, instances_dir, seconds, target = job
    inst = read_instance(instances_dir / f"{name}.vrp")
    scenario = "plus_5pct"
    capacity = inst.capacity + ceil(inst.capacity * .05)
    result = arc_solve(inst, capacity, seconds)
    incumbent = result["arc_incumbent"]
    if result["arc_lower_bound"] > target or (incumbent is not None and incumbent < target):
        raise ValueError((name, result, target))
    return dict(instance=name, growth_rank=int(rank)+1, scenario=scenario, capacity=capacity,
                exact_objective=target, **result, certified=result["arc_lower_bound"] == target,
                bound_gap_pct=100*(target-result["arc_lower_bound"])/target)


def arc(args, reference):
    ranking = sorted(NAMES, key=lambda name: (int(reference[name, "plus_1_unit"]["partitions"]) /
                                                int(reference[name, "original"]["partitions"]), name))
    ranks = np.linspace(0, len(ranking)-1, 9).round().astype(int)
    jobs = [(int(rank), ranking[rank], args.instances, args.seconds,
             int(reference[ranking[rank], "plus_5pct"]["objective"])) for rank in ranks]
    with ProcessPoolExecutor(max_workers=pool_workers(9)) as pool:
        rows = list(pool.map(_solve_arc_job, jobs))
    write_csv(ROOT / "results/arc_baseline.csv", rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", choices=["ablation", "arc"])
    parser.add_argument("--instances", type=Path, required=True)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--seconds", type=float, default=10)
    args = parser.parse_args()
    if args.experiment == "ablation" and not args.binary:
        parser.error("ablation requires --binary")
    with (ROOT / "results/per_instance.csv").open() as f:
        reference = {(r["instance"], r["scenario"]): r for r in csv.DictReader(f) if r["mode"] == "bounded"}
    (ablation if args.experiment == "ablation" else arc)(args, reference)

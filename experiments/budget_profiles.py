"""Matched ablation of the budget-aware two-route recurrence for upgrades by 1 or 2."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import subprocess
from fractions import Fraction
from itertools import permutations
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmark import pool_workers, NAMES, customer_ids, exact_run, read_instance, verify_and_reconstruct, write_csv

HERE = Path(__file__).resolve().parent
MODES = ("direct", "split", "cache")
ORDERS = list(permutations(MODES))


def fee_supported(curve, budget):
    lower = max([Fraction(0)] + [Fraction(curve[budget]-curve[a], a-budget)
                                 for a in range(budget+1, len(curve))])
    upper = [Fraction(curve[a]-curve[budget], budget-a) for a in range(budget)]
    return all(lower <= bound for bound in upper)


def _solve_budget_instance(job):
    i, name, instances_dir, binary, cover, prev_inst = job
    inst = read_instance(instances_dir / (name + ".vrp"))
    q = inst.capacity
    inst_timings, inst_budgets = [], []
    for increment in (1, 2):
        cap = q + increment
        objective, _, columns, _ = exact_run(binary, inst, cap, 4*q - 3*cap, 1, True)
        lines = [f"20 {len(columns)}"]
        for mask, cost in columns:
            load = sum(inst.demand[j-1] for j in customer_ids(mask))
            lines.append(f"{mask} {cost} {int(load > q)}")
        payload = "\n".join(lines)
        reference = None
        for repeat in range(3):
            order = ORDERS[(i + increment + repeat) % len(ORDERS)]
            for mode in order:
                run = subprocess.run([str(cover), mode], input=payload, text=True, capture_output=True, check=True)
                bins = [list(map(int, line.split())) for line in run.stdout.splitlines()]
                profile = [(count, value) for count, value, *_ in bins]
                if reference is None:
                    reference = profile
                assert reference == profile and sum(n for n, _ in profile) == objective["partitions"]
                if repeat == 0:
                    for b, (count, value, *masks) in enumerate(bins):
                        if count:
                            routes = verify_and_reconstruct(inst, cap, masks, value)
                            assert sum(r["load"] > q for r in routes) == b
                inst_timings.append(dict(instance=name, increment=increment, repeat=repeat+1, mode=mode,
                                         position=order.index(mode)+1, cover_ms=float(run.stderr.strip())))
        curve = [min(value for count, value in profile[:b+1] if count) for b in range(5)]
        assert curve[-1] == objective["objective"]
        for b, (count, value) in enumerate(profile):
            if increment == 1:
                ref = prev_inst[b]
                assert (count, curve[b]) == (int(ref["exactly_b_partitions"]), int(ref["budget_optimum"]))
            inst_budgets.append(dict(instance=name, increment=increment, budget=b, partitions_exact=count,
                                     exact_cost=value if count else "", budget_cost=curve[b],
                                     nondominated=b == 0 or curve[b] < curve[b-1], fee_supported=fee_supported(curve, b)))
    return inst_timings, inst_budgets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instances", type=Path)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    results = HERE / "results"
    previous = {}
    with (results / "upgrade_budget.csv").open() as source:
        for r in csv.DictReader(source):
            previous.setdefault(r["instance"], {})[int(r["upgrades"])] = r
    timings, budgets = [], []
    binary = args.binary.resolve()
    with TemporaryDirectory() as tmp:
        cover = Path(tmp) / "cover"
        subprocess.run(["c++", "-std=c++17", "-O3", str(HERE/"upgrade_cover.cpp"), "-o", str(cover)], check=True)
        jobs = [(i, name, args.instances, binary, cover, previous[name]) for i, name in enumerate(NAMES)]
        with ProcessPoolExecutor(max_workers=pool_workers(8)) as pool:
            for t_block, b_block in pool.map(_solve_budget_instance, jobs):
                timings.extend(t_block)
                budgets.extend(b_block)
    write_csv(results/"budget_profile_timings.csv", timings)
    write_csv(results/"budget_profile_frontier.csv", budgets)


if __name__ == "__main__":
    main()

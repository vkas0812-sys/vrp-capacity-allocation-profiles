"""Matched ablation of the budget-aware two-route recurrence for upgrades by 1 or 2."""
import argparse
import csv
import subprocess
from fractions import Fraction
from itertools import permutations
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory

from benchmark import NAMES, customer_ids, exact_run, read_instance, verify_and_reconstruct, write_csv

HERE = Path(__file__).resolve().parent
MODES = ("direct", "split", "cache")


def fee_supported(curve, budget):
    # z_b + fee*b <= z_a + fee*a for every alternative a, fee >= 0.
    lower = max([Fraction(0)] + [Fraction(curve[budget]-curve[a], a-budget)
                                 for a in range(budget+1, len(curve))])
    upper = [Fraction(curve[a]-curve[budget], budget-a) for a in range(budget)]
    return all(lower <= bound for bound in upper)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instances", type=Path)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    results = HERE / "results"
    with (results / "upgrade_budget.csv").open() as source:
        previous = {(r["instance"],int(r["upgrades"])):r for r in csv.DictReader(source)}
    timings, budgets = [], []
    orders = list(permutations(MODES))
    with TemporaryDirectory() as tmp:
        cover = Path(tmp) / "cover"
        subprocess.run(["c++","-std=c++17","-O3",str(HERE/"upgrade_cover.cpp"),"-o",str(cover)],check=True)
        for i,name in enumerate(NAMES):
            inst = read_instance(args.instances / (name + ".vrp"))
            q = inst.capacity
            for increment in (1,2):
                cap = q + increment
                objective, _, columns, _ = exact_run(args.binary.resolve(),inst,cap,4*q-3*cap,1,True)
                lines = [f"20 {len(columns)}"]
                for mask,cost in columns:
                    load = sum(inst.demand[j-1] for j in customer_ids(mask))
                    lines.append(f"{mask} {cost} {int(load > q)}")
                payload = "\n".join(lines)
                reference = None
                for repeat in range(3):
                    order = orders[(i+increment+repeat)%len(orders)]
                    for mode in order:
                        run = subprocess.run([cover,mode],input=payload,text=True,capture_output=True,check=True)
                        bins = [list(map(int,line.split())) for line in run.stdout.splitlines()]
                        profile = [(count,value) for count,value,*_ in bins]
                        if reference is None:
                            reference = profile
                        assert reference == profile and sum(n for n,_ in profile) == objective["partitions"]
                        if repeat == 0:
                            for b,(count,value,*masks) in enumerate(bins):
                                if count:
                                    routes = verify_and_reconstruct(inst,cap,masks,value)
                                    assert sum(r["load"] > q for r in routes) == b
                        timings.append(dict(instance=name,increment=increment,repeat=repeat+1,mode=mode,
                                            position=order.index(mode)+1,cover_ms=float(run.stderr.strip())))
                curve = [min(value for count,value in profile[:b+1] if count) for b in range(5)]
                assert curve[-1] == objective["objective"]
                for b,(count,value) in enumerate(profile):
                    if increment == 1:
                        ref = previous[name,b]
                        assert (count,curve[b]) == (int(ref["exactly_b_partitions"]),int(ref["budget_optimum"]))
                    budgets.append(dict(instance=name,increment=increment,budget=b,partitions_exact=count,
                                        exact_cost=value if count else "",budget_cost=curve[b],
                                        nondominated=b==0 or curve[b]<curve[b-1],fee_supported=fee_supported(curve,b)))
    write_csv(results/"budget_profile_timings.csv",timings)
    write_csv(results/"budget_profile_frontier.csv",budgets)


if __name__ == "__main__":
    main()

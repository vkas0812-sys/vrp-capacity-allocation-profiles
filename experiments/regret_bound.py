"""Certify how much adaptive allocation could improve an available 3+1 plan.

Use an exact fixed-point dual repair on the finite priced route set. Add at most
12 violated customer-triple subset-row cuts per round, for two rounds.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from itertools import combinations
from pathlib import Path
import warnings

import numpy as np
from scipy.optimize import linprog, OptimizeWarning
from scipy.sparse import vstack, csr_matrix, coo_matrix

from allocation_transfer import HERE, PARENTS, members, priced_instance
from benchmark import pool_workers, write_csv

SCALE = 10**6


def certified_dual(eq, ub, c, y, u):
    y = np.rint(y*SCALE).astype(np.int64)
    u = np.minimum(0, np.rint(u*SCALE).astype(np.int64))
    violation = max(0, int(np.max(eq.T@y + ub.T@u - SCALE*c)))
    y[-1] -= violation
    assert np.all(eq.T@y + ub.T@u <= SCALE*c)
    numerator = int(sum(y[:-1]) + 6*y[-1] + 4*u[0] + sum(u[1:]))
    return -(-numerator // SCALE)


def solve(job):
    name, index, directory, ref, plan = job
    _, _, _, _, columns = priced_instance(directory, index, name)
    mask = np.array([m for m, _, _ in columns], dtype=np.int64)
    costs = np.array([c for _, _, c in columns], dtype=np.int64)
    excess = np.array([e for _, e, _ in columns], dtype=np.int64)
    positions = {m: j for j, (m, _, _) in enumerate(columns)}
    chosen = [positions[int(m)] for m in plan["masks"].split()]
    customers = [i for j in chosen for i in members(int(mask[j]))]
    assert len(chosen) == 6 and sorted(customers) == list(range(24))
    assert all(x <= y for x, y in zip(sorted(excess[chosen]), (0, 0, 0, 0, 1, 3)))
    incumbent = int(sum(costs[chosen]))
    assert incumbent == int(ref["three_plus_one"])
    optimal = int(ref["adaptive"])
    indices = [(i, j) for j, m in enumerate(mask) for i in [*members(int(m)), 24]]
    rr, cc = zip(*indices)
    eq = coo_matrix((np.ones(len(rr), dtype=np.int64), (rr, cc)), shape=(25, len(mask))).tocsr()
    ub = csr_matrix(excess.reshape(1, -1))
    triples = np.array([(1 << a) | (1 << b) | (1 << c) for a, b, c in combinations(range(24), 3)], dtype=np.int64)
    used = set()
    row = dict(parent=name, incumbent=incumbent, adaptive_cost=optimal)
    best = 0
    for rnd in range(3):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=OptimizeWarning, message="Unrecognized options")
            sol = linprog(costs, A_ub=ub, b_ub=[4] + [1]*(ub.shape[0] - 1), A_eq=eq, b_eq=[1]*24 + [6],
                          bounds=(0, None), method="highs", options={"threads": 1})
        if not sol.success:
            raise ValueError(sol.message)
        best = max(best, certified_dual(eq, ub, costs, sol.eqlin.marginals, sol.ineqlin.marginals))
        assert best <= optimal <= incumbent
        row["lp_bound" if rnd == 0 else "cut_bound"] = best
        if rnd == 2 or best == incumbent:
            break
        positive = sol.x > 1e-9
        overlap = triples[:, None] & mask[positive]
        multiple = (overlap & (overlap - 1)) != 0
        violation = multiple @ sol.x[positive] - 1
        selected = [int(i) for i in np.argsort(-violation, kind="stable")
                    if violation[i] > 1e-7 and i not in used][:12]
        if not selected:
            break
        used.update(selected)
        overlap = triples[selected, None] & mask
        ub = vstack([ub, csr_matrix(((overlap & (overlap - 1)) != 0).astype(np.int64))], format="csr")
    row.update(cut_bound=best, cuts=ub.shape[0] - 1, exact_gain_pct=100*(incumbent - optimal)/incumbent,
               max_gain_pct=100*(incumbent - best)/incumbent)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("initial", type=Path)
    parser.add_argument("holdout", type=Path)
    args = parser.parse_args()
    results = HERE / "results"

    def read(path):
        with path.open() as src:
            return list(csv.DictReader(src))

    names = list(PARENTS) + [r["parent"] for r in read(HERE / "holdout_parents.csv")]
    refs = {r["parent"]: r for r in read(results / "six_vehicle_cohort_summary.csv")}
    plans = {r["parent"]: r for f in ("six_vehicle_profiles.csv", "six_vehicle_holdout.csv")
             for r in read(results / f) if r["design"] == "0 0 0 0 1 3"}
    jobs = [(name, i, args.initial if i < 10 else args.holdout, refs[name], plans[name])
            for i, name in enumerate(names)]
    with ProcessPoolExecutor(max_workers=pool_workers()) as pool:
        rows = list(pool.map(solve, jobs))
    write_csv(results / "regret_bound.csv", rows)


if __name__ == "__main__":
    main()

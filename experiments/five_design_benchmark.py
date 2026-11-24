"""Compare one profile with five fixed-design masters on shared XSH route prices."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import subprocess
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix

from benchmark import pool_workers, NAMES, customer_ids, exact_run, read_instance

HERE = Path(__file__).resolve().parent
DESIGNS = [(0, 0, 0, 4), (0, 0, 1, 3), (0, 0, 2, 2), (0, 1, 1, 2), (1, 1, 1, 1)]
LIMIT = 2.0


def profile(routes, binary):
    payload = [f"20 4 {len(routes)}"]
    payload.extend(f"{mask} {cost} {excess}" for mask, cost, excess in routes)
    run = subprocess.run([binary], input="\n".join(payload), text=True,
                         capture_output=True, check=True)
    classes = [list(map(int, line.split())) for line in run.stdout.splitlines()]
    answers = {}
    for design in DESIGNS:
        fits = [row for row in classes if all(e <= a for e, a in zip(row[:4], design))]
        answers[design] = min(row[5] for row in fits), sum(row[4] for row in fits)
    return answers


def five_masters(routes):
    rows, cols = [], []
    for j, (mask, cost, excess) in enumerate(routes):
        indices = [i - 1 for i in customer_ids(mask)] + [20] + list(range(21, 21 + excess))
        rows.extend(indices)
        cols.extend([j] * len(indices))
    matrix = csc_matrix((np.ones(len(rows)), (rows, cols)), shape=(25, len(routes)))
    cost = np.array([cost for _, cost, _ in routes])
    excess = np.array([e for _, _, e in routes])
    answers = {}
    for design in DESIGNS:
        eligible = excess <= max(design)
        limits = [sum(a >= t for a in design) for t in range(1, 5)]
        con = LinearConstraint(matrix[:, eligible], [1]*20 + [4] + [0]*4,
                               [1]*20 + [4] + limits)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Unrecognized options detected")
            result = milp(cost[eligible], integrality=np.ones(eligible.sum()),
                          bounds=Bounds(0, 1), constraints=con,
                          options={"time_limit": LIMIT, "mip_rel_gap": 0., "threads": 1})
        if result.status not in (0, 1):
            raise RuntimeError(result.message)
        answers[design] = result
    return answers


def _solve_five_design_instance(job):
    index, name, instances_dir, pricer, join, ref_inst = job
    inst = read_instance(instances_dir / (name + ".vrp"))
    q = inst.capacity
    _, _, columns, _ = exact_run(pricer, inst, q + 4, q - 4, 1, True)
    routes = [(m, c, max(0, sum(inst.demand[j-1] for j in customer_ids(m)) - q))
              for m, c in columns]

    def timed(method):
        start = perf_counter()
        answer = method()
        return answer, perf_counter() - start

    methods = [lambda: profile(routes, join), lambda: five_masters(routes)]
    order = (0, 1) if index % 2 == 0 else (1, 0)
    outputs = {i: timed(methods[i]) for i in order}
    (profiles, tp), (masters, tm) = outputs[0], outputs[1]
    out_rows = []
    for d in DESIGNS:
        label = " ".join(map(str, d))
        optimum, count = profiles[d]
        assert (optimum, count) == ref_inst[label]
        res = masters[d]
        if res.fun is not None:
            assert res.fun >= optimum - 1e-5
        if res.status == 0:
            assert abs(res.fun - optimum) < 1e-5
        out_rows.append([name, label, tp, tm, optimum, count, res.status,
                         res.fun, res.mip_dual_bound])
    return out_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instances", type=Path)
    args = parser.parse_args()
    with (HERE/"results/allocation_designs.csv").open() as stream:
        reference = {}
        for r in csv.DictReader(stream):
            reference.setdefault(r["instance"], {})[r["design"]] = (int(r["cost"]), int(r["partitions"]))
    with TemporaryDirectory() as tmp:
        pricer, join = Path(tmp)/"exact", Path(tmp)/"join"
        for source, target in [("exact.cpp", pricer), ("allocation_cover.cpp", join)]:
            subprocess.run(["c++", "-O3", "-std=c++17", HERE/source, "-o", target], check=True)
        jobs = [(index, name, args.instances, pricer, join, reference[name])
                for index, name in enumerate(NAMES)]
        with (HERE/"results/five_design_benchmark.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["instance", "design", "profile_seconds_all", "milp_seconds_all",
                             "profile_cost", "partitions", "milp_status", "incumbent", "dual_bound"])
            with ProcessPoolExecutor(max_workers=pool_workers(8)) as pool:
                for out_rows in pool.map(_solve_five_design_instance, jobs):
                    writer.writerows(out_rows)
                    stream.flush()


if __name__ == "__main__":
    main()

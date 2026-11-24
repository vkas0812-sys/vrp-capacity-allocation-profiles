"""Fixed total of four additional capacity units on the full XSH suite."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import subprocess
import warnings
from itertools import combinations_with_replacement
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from benchmark import pool_workers, NAMES, customer_ids, exact_run, read_instance, verify_and_reconstruct, write_csv

HERE = Path(__file__).resolve().parent
BUDGET = 4


def check_master(columns, excesses, inst, expected):
    row, col, data = [], [], []
    for j, ((mask, _), excess) in enumerate(zip(columns,excesses)):
        for node in customer_ids(mask):
            row.append(node-1); col.append(j); data.append(1)
        row.extend([20,21]); col.extend([j,j]); data.extend([1,excess])
    mat = coo_matrix((data,(row,col)),shape=(22,len(columns))).tocsc()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Unrecognized options detected")
        result = milp([cost for _,cost in columns],integrality=np.ones(len(columns)),bounds=Bounds(0,1),
                      constraints=LinearConstraint(mat,[1]*20+[4,0],[1]*20+[4,BUDGET]),
                      options={"time_limit":10., "mip_rel_gap":0., "threads":1})
    if result.x is not None:
        masks = [mask for (mask,_),v in zip(columns,result.x) if v>.5]
        tours = verify_and_reconstruct(inst,inst.capacity+BUDGET,masks,round(result.fun))
        assert sum(max(0,r["load"]-inst.capacity) for r in tours)<=BUDGET and round(result.fun)>=expected
    if result.status == 0:
        assert round(result.fun)==expected
    return dict(instance=inst.name, expected=expected,status=result.status, incumbent=result.fun,
                dual_bound=result.mip_dual_bound, gap=result.mip_gap)


def _solve_allocation_instance(job):
    name, instances_dir, binary, join_bin, designs, ref_plus1, ref_orig = job
    inst = read_instance(instances_dir / (name + ".vrp"))
    q = inst.capacity
    assert sum(inst.demand) == 4 * q
    _, _, columns, _ = exact_run(binary, inst, q + BUDGET, q - BUDGET, 1, True)
    excesses = [max(0, sum(inst.demand[j-1] for j in customer_ids(mask)) - q) for mask, _ in columns]
    payload = [f"20 4 {len(columns)}"]
    payload.extend(f"{mask} {cost} {e}" for (mask, cost), e in zip(columns, excesses))
    out = subprocess.run([str(join_bin)], input="\n".join(payload), text=True, capture_output=True, check=True)
    profiles = []
    inst_signatures = []
    inst_rows = []
    for line in out.stdout.splitlines():
        *key, count, value, m1, m2, m3, m4 = map(int, line.split())
        masks = [m1, m2, m3, m4]
        tours = verify_and_reconstruct(inst, q + 4, masks, value)
        assert sorted(max(0, r["load"] - q) for r in tours) == key
        profiles.append((key, count, value))
        inst_signatures.append(dict(instance=name, excess=" ".join(map(str, key)), count=count,
                                    cost=value, masks=" ".join(map(str, masks))))
    for design in designs:
        fits = [(count, value) for key, count, value in profiles if all(a <= b for a, b in zip(key, design))]
        count = sum(n for n, _ in fits)
        cost = min(v for _, v in fits)
        if design == (1, 1, 1, 1):
            assert (cost, count) == (int(ref_plus1["objective"]), int(ref_plus1["partitions"]))
        inst_rows.append(dict(instance=name, design=" ".join(map(str, design)), cost=cost, partitions=count))
    base = [(n, v) for k, n, v in profiles if sum(k) == 0]
    assert base == [(int(ref_orig["partitions"]), int(ref_orig["objective"]))]
    chk = check_master(columns, excesses, inst, min(v for _, _, v in profiles))
    return inst_rows, inst_signatures, chk


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instances",type=Path)
    parser.add_argument("binary",type=Path)
    args=parser.parse_args()
    results=HERE/"results"
    with (results/"per_instance.csv").open() as src:
        refs={(r["instance"],r["scenario"]):r for r in csv.DictReader(src) if r["mode"]=="bounded"}
    designs=list(a for a in combinations_with_replacement(range(5),4) if sum(a)==4)
    rows,checks,signatures=[],[],[]
    binary = args.binary.resolve()
    with TemporaryDirectory() as tmp:
        join=Path(tmp)/"join"
        subprocess.run(["c++","-O3","-std=c++17",str(HERE/"allocation_cover.cpp"),"-o",str(join)],check=True)
        jobs=[(name, args.instances, binary, join, designs, refs[name,"plus_1_unit"], refs[name,"original"])
              for name in NAMES]
        with ProcessPoolExecutor(max_workers=pool_workers()) as pool:
            for inst_rows, inst_sigs, chk in pool.map(_solve_allocation_instance, jobs):
                rows.extend(inst_rows)
                signatures.extend(inst_sigs)
                checks.append(chk)
    for filename, records in (("allocation_designs.csv",rows),("allocation_signatures.csv",signatures),
                              ("allocation_milp.csv",checks)):
        write_csv(results/filename,records)


if __name__=="__main__":
    main()

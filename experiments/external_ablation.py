"""Recheck early pricing filters on reproducible, disjoint CVRPLIB-X subsamples."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from subprocess import TimeoutExpired
import hashlib
from math import ceil, hypot
from pathlib import Path
from random import Random
from statistics import median

from benchmark import pool_workers, Instance, exact_run, verify_and_reconstruct, write_csv

HERE = Path(__file__).resolve().parent
PARENTS = ("X-n101-k25", "X-n106-k14", "X-n110-k13", "X-n115-k10", "X-n120-k6",
           "X-n125-k30", "X-n129-k18", "X-n134-k13", "X-n139-k10", "X-n143-k7")


def subsamples(path):
    data = path.read_bytes()
    lines = [s.strip() for s in data.decode().splitlines()]
    coordinates = {int(i): (int(x), int(y)) for i, x, y in
                   (s.split() for s in lines[lines.index("NODE_COORD_SECTION")+1:lines.index("DEMAND_SECTION")])}
    demands = dict(tuple(map(int, s.split())) for s in
                   lines[lines.index("DEMAND_SECTION")+1:lines.index("DEPOT_SECTION")])
    ids = sorted(i for i in demands if i != 1)
    Random(20261121).shuffle(ids)
    for offset in (0, 20):
        selected = ids[offset:offset+20]
        demand = tuple(demands[i] for i in selected)
        loads = [0]*4
        for quantity in sorted(demand, reverse=True):
            loads[loads.index(min(loads))] += quantity
        nodes = [coordinates[i] for i in [1, *selected]]
        distance = tuple(tuple(int(hypot(x-a, y-b)+0.5) for a,b in nodes) for x,y in nodes)
        yield Instance(path.stem, max(loads), demand, distance, -1, hashlib.sha256(data).hexdigest()), selected


def _solve_external_task(job):
    idx, i, name, j, inst, selected, k, label, extra, binary = job
    capacity = inst.capacity + extra
    modes = [("early", max(1, sum(inst.demand) - 3*capacity)), ("late", 1)]
    if (i + j + k) % 2:
        modes.reverse()
    pair = {}
    row = dict(parent=name, sample=j+1, ids=" ".join(map(str, selected)), sha256=inst.sha256,
               base_capacity=inst.capacity, scenario=label, capacity=capacity,
               fleet_slack=4*capacity - sum(inst.demand))
    for mode, lower in modes:
        try:
            result, masks, _, timings = exact_run(binary, inst, capacity, lower, 3, False, timeout=12)
        except TimeoutExpired:
            row[mode + "_status"] = "timeout"
            continue
        row[mode + "_status"] = "complete"
        verify_and_reconstruct(inst, capacity, masks, result["objective"])
        pair[mode] = result
        row[mode + "_repeats_ms"] = " ".join(str(sum(t)) for t in timings)
    if len(pair) != 2:
        return idx, row
    for key in ("objective", "partitions", "optimal_partitions", "second_distinct_objective"):
        if pair["early"][key] != pair["late"][key]:
            raise ValueError((name, j, label, key))
        row[key] = pair["early"][key]
    for key in ("candidate_routes", "pricing_ms", "exact_ms"):
        row[key + "_factor"] = pair["late"][key] / pair["early"][key]
    return idx, row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    jobs = []
    idx = 0
    for i, name in enumerate(PARENTS):
        for j, (inst, selected) in enumerate(subsamples(args.directory / (name + ".vrp"))):
            for k, (label, extra) in enumerate((("+1", 1), ("+2%", ceil(.02*inst.capacity)),
                                                ("+5%", ceil(.05*inst.capacity)))):
                jobs.append((idx, i, name, j, inst, selected, k, label, extra, binary))
                idx += 1
    # Schedule heaviest (+5%, +2%) tasks first so 12s timeouts never straggle at the tail.
    scheduled = sorted(jobs, key=lambda item: -item[7].count("%") - item[8])
    results_by_idx = {}
    with ProcessPoolExecutor(max_workers=pool_workers()) as pool:
        for out_idx, row in pool.map(_solve_external_task, scheduled):
            results_by_idx[out_idx] = row
    rows = [results_by_idx[m] for m in range(len(jobs))]
    write_csv(HERE / "results/external_ablation.csv", rows)
    for label in ("+1", "+2%", "+5%"):
        block = [r for r in rows if r["scenario"] == label and "exact_ms_factor" in r]
        print(label, median(r["exact_ms_factor"] for r in block),
              sum(r["exact_ms_factor"] > 1 for r in block), len(block))


if __name__ == "__main__":
    main()

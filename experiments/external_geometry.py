"""Fixed transfer experiment on the two archived samples of each of ten X parents.

Compare unchanged placement with seven seeded placements per sample at C and C+1.
Keep every scheduled row, allow five seconds per exact solve, use complete blocks
for effect estimates, and aggregate both samples within parent before pooling.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
from random import Random
from statistics import median
from subprocess import TimeoutExpired

from benchmark import exact_run, verify_and_reconstruct, write_csv
from external_ablation import PARENTS, subsamples

RESULTS = Path(__file__).resolve().parent / "results"


def run_block(job):
    binary, parent_index, sample, inst = job
    rows = []
    counts = {}
    for draw in range(8):
        demand = list(inst.demand)
        seed = 20261122 + 1000 * parent_index + 100 * sample + draw
        if draw:
            Random(seed).shuffle(demand)
        instance = replace(inst, demand=tuple(demand))
        row = dict(parent=inst.name, sample=sample, draw=draw, seed=seed if draw else "",
                   capacity=inst.capacity, source_sha256=inst.sha256)
        for extra, label in enumerate(("base", "plus_one")):
            cap = inst.capacity + extra
            try:
                result, masks, _, _ = exact_run(binary, instance, cap,
                    max(1, sum(demand)-3*cap), 1, False, timeout=5)
            except TimeoutExpired:
                row[label + "_status"] = "timeout"
                continue
            verify_and_reconstruct(instance, cap, masks, result["objective"])
            row[label + "_status"] = "complete"
            row[label] = result["objective"]
            observed = (result["candidate_routes"], result["partitions"])
            if counts.setdefault(label, observed) != observed:
                raise ValueError((inst.name, sample, draw, label))
            row[label + "_partitions"] = result["partitions"]
        if "base" in row and "plus_one" in row:
            row["saving_pct"] = 100 * (1 - row["plus_one"] / row["base"])
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parents", type=Path)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    jobs = [(args.binary.resolve(), i, sample, inst) for i, name in enumerate(PARENTS)
            for sample, (inst, _) in enumerate(subsamples(args.parents / (name + ".vrp")), 1)]
    with ProcessPoolExecutor(max_workers=3) as pool:
        blocks = list(pool.map(run_block, jobs))
    write_csv(RESULTS / "external_geometry.csv", [r for block in blocks for r in block])
    parents = {}
    for rows in blocks:
        if all("saving_pct" in r for r in rows):
            natural = rows[0]["saving_pct"]
            shuffled = median(r["saving_pct"] for r in rows[1:])
            parents.setdefault(rows[0]["parent"], []).append((natural, shuffled, shuffled-natural))
    parent_rows = []
    for name, samples in parents.items():
        if len(samples) == 2:
            parent_rows.append(dict(parent=name, **dict(zip(("original_pct","shuffled_pct","shift_pp"),
                                                  map(median,zip(*samples))))))
    write_csv(RESULTS / "external_geometry_parents.csv", parent_rows)
    print("complete parents",len(parent_rows),flush=True)
    for key in ("original_pct","shuffled_pct","shift_pp"):
        print(key, median(r[key] for r in parent_rows))


if __name__ == "__main__":
    main()

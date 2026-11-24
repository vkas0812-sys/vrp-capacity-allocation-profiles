"""Reassign demands to customer locations and repeat the paired one-unit intervention."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from dataclasses import replace
from pathlib import Path
from random import Random

from benchmark import pool_workers, NAMES, exact_run, read_instance, verify_and_reconstruct, write_csv

RESULTS = Path(__file__).resolve().parent / "results"


def _solve_geometry_instance(job):
    i, name, instances_dir, binary, ref_orig, ref_plus1 = job
    original = read_instance(instances_dir / (name + ".vrp"))
    inst_rows = []
    ref_map = {"original": ref_orig, "plus_1_unit": ref_plus1}
    for j in range(51):
        seed = 20261121 + 100 * i + j
        shuffled = list(original.demand)
        Random(seed).shuffle(shuffled)
        instance = replace(original, demand=tuple(shuffled))
        row = dict(instance=name, seed=seed)
        for extra, level in enumerate(("original", "plus_1_unit")):
            cap = original.capacity + extra
            result, masks, _, _ = exact_run(binary, instance, cap, sum(shuffled)-3*cap, 1, False)
            verify_and_reconstruct(instance, cap, masks, result["objective"])
            for field in ("candidate_routes", "partitions"):
                if result[field] != int(ref_map[level][field]):
                    raise ValueError((name, seed, level, field))
            row[level] = result["objective"]
        row["reduction_pct"] = 100 * (1 - row["plus_1_unit"] / row["original"])
        inst_rows.append(row)
    return inst_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instances", type=Path)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    with (RESULTS / "per_instance.csv").open() as source:
        ref = {(r["instance"], r["scenario"]): r for r in csv.DictReader(source) if r["mode"] == "bounded"}
    binary = args.binary.resolve()
    jobs = [(i, name, args.instances, binary, ref[name, "original"], ref[name, "plus_1_unit"])
            for i, name in enumerate(NAMES)]
    rows = []
    with ProcessPoolExecutor(max_workers=pool_workers()) as pool:
        for block in pool.map(_solve_geometry_instance, jobs):
            rows.extend(block)
    write_csv(RESULTS / "geometry_control.csv", rows)
    print(f"{len(rows)} matched pairs, {2 * len(rows)} reconstructed solutions")


if __name__ == "__main__":
    main()

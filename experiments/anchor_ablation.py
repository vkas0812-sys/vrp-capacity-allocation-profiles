"""Matched 0/2/3-anchor experiment on the archived 10+20 six-vehicle hybrids."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from itertools import pairwise, permutations
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter

from allocation_transfer import HERE, PARENTS, priced_instance, members
from six_vehicle_profiles import check_counts
from benchmark import pool_workers, write_csv

MODES = ("baseline", "two", "three")
PERM_MODES = list(permutations(MODES))


def _prep_parent(job):
    index, name, directory = job
    start = perf_counter()
    _, _, demand, dist, columns = priced_instance(directory, index, name)
    data = [f"24 100 {len(columns)}"]
    for mask, _, cost in columns:
        load = sum(demand[i] for i in members(mask))
        data.append(f"{mask} {cost} {load}")
    payload = "\n".join(data)
    prep = perf_counter() - start
    return index, name, demand, dist, payload, prep


def _run_anchor_repeat(job):
    task_id, index, name, repeat, payload, demand, dist, adaptive_ref, binary = job
    order = PERM_MODES[(index + repeat) % 6]
    task_rows = []
    values_first = None
    for mode in order:
        t = perf_counter()
        proc = subprocess.run([str(binary), mode], input=payload, text=True, capture_output=True, check=True, timeout=90)
        elapsed = perf_counter() - t
        values = {}
        for line in proc.stdout.splitlines():
            key, count, value, *masks = map(int, line.split())
            assert count > 0 and len(masks) == 6 and sorted(i for m in masks for i in members(m)) == list(range(24))
            excess = [max(0, sum(demand[i] for i in members(m)) - 100) for m in masks]
            assert sum(excess) <= 4 and sum(1 << (3 * (e - 1)) for e in excess if e) == key
            assert sum(min(sum(dist[a][b] for a, b in pairwise((0, *tour, 0)))
                           for tour in permutations(i + 1 for i in members(m))) for m in masks) == value
            assert key not in values
            values[key] = (count, value)
        assert min(v for _, v in values.values()) == adaptive_ref
        if values_first is None:
            values_first = values
        assert values_first == values
        unions, bins, join_s = proc.stderr.split()
        task_rows.append((mode, order.index(mode) + 1, int(unions), int(bins), float(join_s), elapsed))
    return task_id, index, name, repeat, values_first, task_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("initial", type=Path)
    parser.add_argument("holdout", type=Path)
    args = parser.parse_args()
    with (HERE / "holdout_parents.csv").open() as src:
        names = list(PARENTS) + [r["parent"] for r in csv.DictReader(src)]
    with (HERE / "results/six_vehicle_cohort_summary.csv").open() as src:
        refs = {r["parent"]: r for r in csv.DictReader(src)}
    rows = []
    with TemporaryDirectory() as tmp:
        binary = Path(tmp) / "solver"
        subprocess.run(["c++", "-std=c++17", "-O3", str(HERE / "six_vehicle_join.cpp"), "-o", str(binary)], check=True)
        for mode in MODES:
            check_counts(binary, mode)
            check_counts(binary, mode, spread=True)

        prep_jobs = [(index, name, args.initial if index < len(PARENTS) else args.holdout)
                     for index, name in enumerate(names)]
        with ProcessPoolExecutor(max_workers=pool_workers()) as pool:
            prepped = {idx: (name, demand, dist, payload, prep)
                       for idx, name, demand, dist, payload, prep in pool.map(_prep_parent, prep_jobs)}

        repeat_jobs = []
        task_id = 0
        for index, name in enumerate(names):
            _, demand, dist, payload, _ = prepped[index]
            for repeat in range(3 if index % 5 == 0 else 1):
                repeat_jobs.append((task_id, index, name, repeat, payload, demand, dist,
                                    int(refs[name]["adaptive"]), binary))
                task_id += 1

        results_by_task = {}
        with ProcessPoolExecutor(max_workers=pool_workers(8)) as pool:
            for res in pool.map(_run_anchor_repeat, repeat_jobs):
                results_by_task[res[0]] = res

        parent_ref = {}
        for tid in range(len(repeat_jobs)):
            _, index, name, repeat, values_first, task_rows = results_by_task[tid]
            if index not in parent_ref:
                parent_ref[index] = values_first
            assert parent_ref[index] == values_first
            prep = prepped[index][4]
            for mode, pos, unions, bins, join_s, elapsed in task_rows:
                rows.append(dict(parent=name, cohort="initial" if index < 10 else "holdout",
                                 repeat=repeat + 1, mode=mode, order=pos, unions=unions, bins=bins,
                                 join_s=join_s, prepared_s=prep, elapsed_s=elapsed))
    write_csv(HERE / "results/anchor_ablation.csv", rows)


if __name__ == "__main__":
    main()

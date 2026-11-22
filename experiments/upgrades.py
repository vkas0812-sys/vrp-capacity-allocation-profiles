"""Resolve distance savings by the number of vehicles given one extra load unit."""
import argparse
import csv
import subprocess
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory

from benchmark import NAMES, customer_ids, exact_run, read_instance, verify_and_reconstruct, write_csv

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instances", type=Path)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    results = HERE / "results"
    with (results / "per_instance.csv").open() as source:
        refs = {(r["instance"], r["scenario"]): r for r in csv.DictReader(source) if r["mode"] == "bounded"}
    rows = []
    with TemporaryDirectory() as tmp:
        cover = Path(tmp) / "cover"
        subprocess.run(["c++", "-std=c++17", "-O3", str(HERE / "upgrade_cover.cpp"), "-o", str(cover)], check=True)
        for name in NAMES:
            inst = read_instance(args.instances / (name + ".vrp"))
            q = inst.capacity
            assert sum(inst.demand) == 4*q
            _, _, columns, _ = exact_run(args.binary.resolve(), inst, q+1, q-3, 1, True)
            lines = [f"20 {len(columns)}"]
            for mask, cost in columns:
                load = sum(inst.demand[i-1] for i in customer_ids(mask))
                lines.append(f"{mask} {cost} {int(load > q)}")
            output = subprocess.run([str(cover)], input="\n".join(lines), text=True, capture_output=True, check=True)
            classes = [list(map(int, line.split())) for line in output.stdout.splitlines()]
            z0 = int(refs[name,"original"]["objective"])
            z1 = int(refs[name,"plus_1_unit"]["objective"])
            assert len(classes) == 5 and classes[4][0] == 0 and z0 > z1
            assert classes[0][1] == z0
            best = z0
            feasible = 0
            for b,(count,value,*masks) in enumerate(classes):
                if count:
                    routes = verify_and_reconstruct(inst,q+1,masks,value)
                    assert sum(r["load"] > q for r in routes) == b
                    best = min(best,value)
                feasible += count
                rows.append(dict(instance=name, upgrades=b, exactly_b_partitions=count,
                    exactly_b_optimum=value if count else "", witness_masks=" ".join(map(str,masks)) if count else "",
                    budget_optimum=best, budget_partitions=feasible, recovered_pct=100*(z0-best)/(z0-z1)))
                if b in (0,4):
                    ref = refs[name,"original" if b == 0 else "plus_1_unit"]
                    assert (best,feasible)==(int(ref["objective"]),int(ref["partitions"]))
    write_csv(results / "upgrade_budget.csv",rows)
    for b in range(5):
        block = [r for r in rows if r["upgrades"] == b]
        print(b, median(r["recovered_pct"] for r in block),sum(r["recovered_pct"]==100 for r in block))


if __name__ == "__main__":
    main()

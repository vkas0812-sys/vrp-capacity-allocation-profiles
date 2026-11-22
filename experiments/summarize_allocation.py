"""Compare adaptive allocation against uniform and a leave-one-instance-out fixed design."""
import csv
from pathlib import Path
from statistics import mean, median
from collections import Counter

from benchmark import write_csv

RESULTS = Path(__file__).resolve().parent / "results"


def main():
    costs={}
    with (RESULTS/"allocation_designs.csv").open() as src:
        for r in csv.DictReader(src):
            costs.setdefault(r["instance"],{})[r["design"]]=int(r["cost"])
    uniform="1 1 1 1"
    rows=[]
    for name, design_cost in costs.items():
        base=design_cost[uniform]
        best=min(design_cost.values())
        chosen=min(sorted(design_cost),key=lambda d: mean(v[d]/v[uniform] for other,v in costs.items()
                                                            if other!=name))
        rows.append(dict(instance=name,uniform=base,adaptive=best,fixed_design=chosen,fixed_cost=design_cost[chosen],
                         best_designs=";".join(d for d,v in design_cost.items() if v==best),
                         gain_vs_uniform=100*(base-best)/base,
                         gain_vs_fixed=100*(design_cost[chosen]-best)/design_cost[chosen]))
    write_csv(RESULTS/"allocation_comparison.csv",rows)
    for key in ("gain_vs_uniform","gain_vs_fixed"):
        print(key,median(r[key] for r in rows),sum(r[key]>0 for r in rows),max(r[key] for r in rows))
    print("fixed choices",Counter(r["fixed_design"] for r in rows))
    for d in sorted(next(iter(costs.values()))):
        print(d,sum(v[d]==min(v.values()) for v in costs.values()),
              median(100*(v[d]-min(v.values()))/min(v.values()) for v in costs.values()))
    print(max(rows,key=lambda r:r["gain_vs_uniform"]))


if __name__=="__main__":
    main()

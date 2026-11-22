"""Combine valid bounds for the pooled master and its five-design decomposition."""
import csv
from collections import defaultdict
from math import ceil
from pathlib import Path
from statistics import median

from benchmark import write_csv
from allocation_transfer import PARENTS, POLICIES

RESULTS=Path(__file__).resolve().parent/"results"


def main():
    runs=defaultdict(dict)
    for filename in ("allocation_transfer.csv","allocation_transfer_completion.csv"):
        with (RESULTS/filename).open() as source:
            for r in csv.DictReader(source):
                runs[r["parent"]][r["policy"]]=r
    rows=[]
    for parent in PARENTS:
        block=runs[parent]
        assert all(key in block for key in POLICIES)
        lbs={key:ceil(float(r["lower_bound"])-1e-6) if r["lower_bound"] else 0 for key,r in block.items()}
        lower=lbs["adaptive"]
        designs=["balanced","three_plus_one","four","two_two","two_one_one"]
        if all(k in block for k in designs):
            lower=max(lower,min(lbs[k] for k in designs))
        upper=min(round(float(r["incumbent"])) for r in block.values() if r["incumbent"])
        assert lower<=upper
        assert all(block[k]["status"]=="0" for k in ("balanced","three_plus_one"))
        balanced,concentrated=[round(float(block[k]["incumbent"])) for k in ("balanced","three_plus_one")]
        rows.append(dict(parent=parent,balanced=balanced,three_plus_one=concentrated,lower=lower,upper=upper,
                         certified=lower==upper,direct_status=block["adaptive"]["status"]))
    write_csv(RESULTS/"allocation_transfer_bounds.csv",rows)
    print("certified",sum(r["certified"] for r in rows))
    for key in ("balanced","three_plus_one"):
        for bound in ("upper","lower"):
            v=[100*(r[key]-r[bound])/r[key] for r in rows]
            print(key,bound,"median",median(v),"strict",sum(x>0 for x in v))
    print(rows)


if __name__=="__main__":
    main()

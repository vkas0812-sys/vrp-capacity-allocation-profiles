"""Matched 0/2/3-anchor experiment on the archived 10+20 six-vehicle hybrids."""
import argparse
import csv
from itertools import pairwise, permutations
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter

from allocation_transfer import HERE, PARENTS, priced_instance, members
from six_vehicle_profiles import check_counts
from benchmark import write_csv

MODES=("baseline","two","three")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("initial",type=Path)
    parser.add_argument("holdout",type=Path)
    args=parser.parse_args()
    with (HERE/"holdout_parents.csv").open() as src:
        names=list(PARENTS)+[r["parent"] for r in csv.DictReader(src)]
    with (HERE/"results/six_vehicle_cohort_summary.csv").open() as src:
        refs={r["parent"]:r for r in csv.DictReader(src)}
    rows=[]
    with TemporaryDirectory() as tmp:
        binary=Path(tmp)/"solver"
        subprocess.run(["c++","-std=c++17","-O3",str(HERE/"six_vehicle_join.cpp"),"-o",str(binary)],check=True)
        for mode in MODES:
            check_counts(binary,mode)
            check_counts(binary,mode,spread=True)
        for index,name in enumerate(names):
            directory=args.initial if index<len(PARENTS) else args.holdout
            start=perf_counter()
            _,_,demand,dist,columns=priced_instance(directory,index,name)
            data=[f"24 100 {len(columns)}"]
            for mask,_,cost in columns:
                load=sum(demand[i] for i in members(mask))
                data.append(f"{mask} {cost} {load}")
            payload="\n".join(data)
            prep=perf_counter()-start
            reference=None
            # One run for every mode/parent; repeat on six evenly spaced parents.
            for repeat in range(3 if index%5==0 else 1):
                order=list(permutations(MODES))[(index+repeat)%6]
                for mode in order:
                    t=perf_counter()
                    proc=subprocess.run([binary,mode],input=payload,text=True,capture_output=True,check=True,timeout=90)
                    elapsed=perf_counter()-t
                    values={}
                    for line in proc.stdout.splitlines():
                        key,count,value,*masks=map(int,line.split())
                        assert count>0 and len(masks)==6 and sorted(i for m in masks for i in members(m))==list(range(24))
                        excess=[max(0,sum(demand[i] for i in members(m))-100) for m in masks]
                        assert sum(excess)<=4 and sum(1<<(3*(e-1)) for e in excess if e)==key
                        assert sum(min(sum(dist[a][b] for a,b in pairwise((0,*tour,0)))
                                       for tour in permutations(i+1 for i in members(m))) for m in masks)==value
                        assert key not in values
                        values[key]=(count,value)
                    assert min(v for _,v in values.values())==int(refs[name]["adaptive"])
                    if reference is None: reference=values
                    assert reference==values
                    unions,bins,join_s=proc.stderr.split()
                    rows.append(dict(parent=name,cohort="initial" if index<10 else "holdout",repeat=repeat+1,
                                     mode=mode,order=order.index(mode)+1,unions=int(unions),bins=int(bins),
                                     join_s=float(join_s),prepared_s=prep,elapsed_s=elapsed))
            print(name,flush=True)
    write_csv(HERE/"results/anchor_ablation.csv",rows)


if __name__=="__main__":
    main()

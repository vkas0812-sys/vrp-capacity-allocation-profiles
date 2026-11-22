"""Check the six-route join against archived MILP certificates on every hybrid."""
import argparse
import csv
import hashlib
import subprocess
from itertools import combinations, combinations_with_replacement, pairwise, permutations, product
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from allocation_transfer import HERE, PARENTS, members, priced_instance
from benchmark import write_csv


def check_counts(binary, mode=None, spread=False):
    """Brute-force oracle: six tours, two per disjoint eight-customer component."""
    demand=[26,26,25,25,25,25,24,24]*3
    columns=[]
    choices=[]
    for start in (0,8,16):
        group=((1<<8)-1)<<start
        pairs=[]
        costs={}
        for ids in combinations(range(start,start+8),4):
            mask=sum(1<<j for j in ids)
            load=sum(demand[j] for j in ids)
            cost=1+mask%97
            costs[mask]=(max(0,load-100),cost)
            columns.append(f"{mask} {cost} {load}")
        for mask,(e,c) in costs.items():
            if mask & (1<<start):
                other_e,other_c=costs[group^mask]
                pairs.append(([e,other_e],c+other_c))
        choices.append(pairs)
    oracle={}
    for splits in product(*choices):
        excess=[e for pair,_ in splits for e in pair]
        if sum(excess)>4:
            continue
        code=sum(1<<(3*(e-1)) for e in excess if e)
        value=sum(c for _,c in splits)
        count,best=oracle.get(code,(0,value))
        oracle[code]=(count+1,min(best,value))
    if spread:
        # Place the first three customer IDs in distinct components; all three
        # must now lie on different routes. Preserve every route load and price.
        relabeled=[]
        for line in columns:
            mask,cost,load=map(int,line.split())
            new_mask=sum(1<<((j%8)*3+j//8) for j in members(mask))
            relabeled.append(f"{new_mask} {cost} {load}")
        columns=relabeled
    data=[f"24 100 {len(columns)}",*columns]
    run=subprocess.run([binary,mode] if mode else [binary],input="\n".join(data),text=True,capture_output=True,check=True)
    observed={}
    for line in run.stdout.splitlines():
        code,count,cost,*_=map(int,line.split())
        observed[code]=(count,cost)
    assert observed==oracle


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parents",type=Path)
    parser.add_argument("--holdout",action="store_true",help="Run the frozen 20-parent extension.")
    args=parser.parse_args()
    results=HERE/"results"
    with (results/"allocation_transfer_bounds.csv").open() as src:
        bounds={r["parent"]:r for r in csv.DictReader(src)}
    names=list(PARENTS)
    offset=0
    filename="six_vehicle_profiles.csv"
    if args.holdout:
        with (HERE/"holdout_parents.csv").open() as source:
            manifest=list(csv.DictReader(source))
        names=[r["parent"] for r in manifest]
        assert len(set(names))==20 and not set(names).intersection(PARENTS)
        for r in manifest:
            data=(args.parents/(r["parent"]+".vrp")).read_bytes()
            git_blob=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
            if git_blob!=r["git_blob"]:
                raise ValueError("Unexpected input version for "+r["parent"])
        offset=len(PARENTS)
        filename="six_vehicle_holdout.csv"
    designs=[a for a in combinations_with_replacement(range(5),6) if sum(a)==4]
    rows=[]
    with TemporaryDirectory() as tmp:
        binary=Path(tmp)/"join"
        subprocess.run(["c++","-O3","-std=c++17",str(HERE/"six_vehicle_join.cpp"),"-o",str(binary)],check=True)
        check_counts(binary)
        for index,name in enumerate(names,offset):
            start=perf_counter()
            seed,ids,demands,dist,sets=priced_instance(args.parents,index,name)
            lines=[f"24 100 {len(sets)}"]
            for mask,e,c in sets:
                load=sum(demands[j] for j in members(mask))
                lines.append(f"{mask} {c} {load}")
            try:
                run=subprocess.run([binary],input="\n".join(lines),text=True,capture_output=True,check=True,timeout=60)
            except subprocess.TimeoutExpired:
                rows.append(dict(parent=name,status="timeout",elapsed_s=perf_counter()-start))
                continue
            elapsed=perf_counter()-start
            profiles=[]
            for line in run.stdout.splitlines():
                code,count,cost,*masks=map(int,line.split())
                loads=[sum(demands[j] for j in members(m)) for m in masks]
                key=sorted(max(0,d-100) for d in loads)
                assert len(masks)==6 and sorted(j for m in masks for j in members(m))==list(range(24))
                assert code==sum(1<<(3*(k-1)) for k in key if k) and sum(key)<=4
                reconstructed=sum(min(sum(dist[a][b] for a,b in pairwise((0,*tour,0)))
                                      for tour in permutations(j+1 for j in members(m))) for m in masks)
                assert reconstructed==cost
                profiles.append((key,count,cost,masks))
            ref=bounds.get(name)
            if ref is not None:
                assert min(r[2] for r in profiles)==int(ref["lower"])==int(ref["upper"])
            for design in designs:
                fits=[r for r in profiles if all(a<=b for a,b in zip(r[0],design))]
                _,_,cost,masks=min(fits,key=lambda r:r[2])
                if ref is not None and design==(0,0,0,0,1,3): assert cost==int(ref["three_plus_one"])
                if ref is not None and design==(0,0,1,1,1,1): assert cost==int(ref["balanced"])
                rows.append(dict(parent=name,seed=seed,ids=" ".join(map(str,ids)),status="complete",design=" ".join(map(str,design)),
                                 cost=cost,count=sum(r[1] for r in fits),masks=" ".join(map(str,masks)),
                                 elapsed_s=elapsed,join_s=float(run.stderr)))
            print(name,round(elapsed,2),flush=True)
    write_csv(results/filename,rows)


if __name__=="__main__":
    main()

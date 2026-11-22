"""Prospective test of three fixed policies on ten six-vehicle, 24-customer hybrids."""
import argparse
import csv
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from itertools import pairwise, permutations
from math import hypot
from pathlib import Path
from random import Random
import warnings

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_matrix

from benchmark import write_csv
from external_ablation import PARENTS

HERE=Path(__file__).resolve().parent
POLICIES={"balanced":(0,0,1,1,1,1), "three_plus_one":(0,0,0,0,1,3), "adaptive":None}


def members(mask):
    while mask:
        bit=mask & -mask
        yield bit.bit_length()-1
        mask ^= bit


def priced_instance(directory,index,name):
    path=directory/(name+".vrp")
    data=path.read_text().split("NODE_COORD_SECTION")[1].split("DEMAND_SECTION")[0].strip()
    locations={int(i):(int(x),int(y)) for i,x,y in (row.split() for row in data.splitlines())}
    seed=20261123+index
    rng=Random(seed)
    ids=rng.sample(sorted(set(locations)-{1}),24)
    nodes=[locations[i] for i in [1,*ids]]
    distance=[[int(hypot(x-a,y-b)+.5) for a,b in nodes] for x,y in nodes]
    demands=[]
    while len(demands)<24:
        group=[rng.randint(16,34) for _ in range(3)]
        last=100-sum(group)
        if 16<=last<=34:
            demands.extend([*group,last])
    rng.shuffle(demands)
    @lru_cache(None)
    def path_cost(mask,end):
        rest=mask ^ (1<<end)
        if not rest:
            return distance[0][end+1]
        return min(path_cost(rest,j)+distance[j+1][end+1] for j in members(rest))
    sets=[]
    def enumerate_sets(start,mask,load):
        if load>=96:
            cost=min(path_cost(mask,j)+distance[j+1][0] for j in members(mask))
            sets.append((mask,max(0,load-100),cost))
        for j in range(start,24):
            if load+demands[j]<=104:
                enumerate_sets(j+1,mask|(1<<j),load+demands[j])
    enumerate_sets(0,0,0)
    return seed,ids,demands,distance,sets


def solve_parent(job):
    directory,index,name,policies=job
    seed,ids,demands,distance,sets=priced_instance(directory,index,name)
    row=[]; col=[]; values=[]
    for j,(mask,e,cost) in enumerate(sets):
        for i in members(mask):
            row.append(i); col.append(j); values.append(1)
        for i,v in enumerate([1,e,*[int(e>=h) for h in range(1,5)]],24):
            if v:
                row.append(i); col.append(j); values.append(v)
    matrix=csc_matrix((values,(row,col)),shape=(30,len(sets)))
    objectives=[c for _,_,c in sets]
    records=[]
    for policy,design in policies.items():
        limits=[sum(x>=t for x in design) for t in range(1,5)] if design else [6]*4
        constraint=LinearConstraint(matrix,[1]*24+[6,0,0,0,0,0],[1]*24+[6,4,*limits])
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore",message="Unrecognized options detected")
            res=milp(objectives,integrality=np.ones(len(sets)),bounds=Bounds(0,1),constraints=constraint,
                     options={"time_limit":10., "threads":1,"mip_rel_gap":0.})
        masks=[]
        if res.x is not None:
            masks=[m for (m,_,_),x in zip(sets,res.x) if x>.5]
            assert len(masks)==6 and sorted(i for m in masks for i in members(m))==list(range(24))
            overloads=sorted(max(0,sum(demands[i] for i in members(m))-100) for m in masks)
            assert sum(overloads)<=4 and (design is None or all(a<=b for a,b in zip(overloads,design)))
            def check_tour(mask):
                return min(sum(distance[a][b] for a,b in pairwise((0,*p,0)))
                           for p in permutations(i+1 for i in members(mask)))
            assert sum(check_tour(m) for m in masks)==round(res.fun)
        records.append(dict(parent=name,seed=seed,ids=" ".join(map(str,ids)),demands=" ".join(map(str,demands)),
                            policy=policy,columns=len(sets),status=res.status,incumbent=res.fun,
                            lower_bound=res.mip_dual_bound,masks=" ".join(map(str,masks))))
    return records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parents",type=Path)
    parser.add_argument("--complete-designs",action="store_true",
                        help="Bound unresolved pooled runs by solving the other three allocations.")
    args=parser.parse_args()
    selected=set(PARENTS)
    policies=POLICIES
    filename="allocation_transfer.csv"
    if args.complete_designs:
        with (HERE/"results"/filename).open() as source:
            selected={r["parent"] for r in csv.DictReader(source) if r["policy"]=="adaptive" and r["status"]!="0"}
        policies={"four":(0,0,0,0,0,4),"two_two":(0,0,0,0,2,2),"two_one_one":(0,0,0,1,1,2)}
        filename="allocation_transfer_completion.csv"
    with ProcessPoolExecutor(max_workers=2) as pool:
        blocks=list(pool.map(solve_parent,[(args.parents,i,n,policies) for i,n in enumerate(PARENTS) if n in selected]))
    write_csv(HERE/"results"/filename,[r for b in blocks for r in b])


if __name__=="__main__":
    main()

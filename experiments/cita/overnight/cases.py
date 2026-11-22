"""One isolated scientific task. The supervisor enforces wall-time and RSS limits."""
import csv
from functools import lru_cache
from itertools import combinations, combinations_with_replacement
import hashlib
import json
from math import hypot
from pathlib import Path
from random import Random
import subprocess
import sys
from time import perf_counter
import warnings

import numpy as np
from scipy.optimize import linprog, OptimizeWarning
from scipy.sparse import coo_matrix,csr_matrix,vstack
from regret_bound import certified_dual
from allocation_transfer import members


def make_case(run,j):
    n,k,B=j["n"],j["k"],j["B"]
    raw=(run/"inputs"/(j["parent"]+".vrp")).read_text()
    section=raw.split("NODE_COORD_SECTION")[1].split("DEMAND_SECTION")[0]
    coords={int(a):(int(x),int(y)) for a,x,y in (s.split() for s in section.strip().splitlines())}
    # Geometry and demand streams are independent. Policy scenarios retain the same sites.
    ids=Random(43001+j["site"]).sample(sorted(set(coords)-{1}),n)
    nodes=[coords[i] for i in [1,*ids]]
    rng=Random(82921+j["seed"])
    assigned=list(range(n));rng.shuffle(assigned)
    demands=[0]*n
    groups=[];offset=0
    for vehicle in range(k):
        size=n//k+int(vehicle<n%k)
        group=assigned[offset:offset+size];offset+=size
        values=[100//size+int(i<100%size) for i in range(size)]
        for _ in range(3*size):
            a,b=rng.sample(range(size),2)
            if values[a]>max(3,100//size-8) and values[b]<100//size+9:
                values[a]-=1;values[b]+=1
        for i,d in zip(group,values):demands[i]=d
        groups.append(sum(1<<i for i in group))
    routes=[]
    def generate(start,mask,load):
        if load>=100-B: routes.append((mask,load))
        for node in range(start,n):
            if load+demands[node]<=100+B:
                generate(node+1,mask|(1<<node),load+demands[node])
    generate(0,0,0)
    if len(routes)>125000: raise MemoryError("priced_column_limit")
    prices=[]
    for scenario in range(j.get("batch",1)):
        locations=nodes[:]
        if scenario:
            order=list(range(1,n+1));Random(730001+scenario*173+j["site"]).shuffle(order)
            locations=[nodes[0]]+[nodes[i] for i in order]
        dist=[[int(hypot(a-x,b-y)+.5) for x,y in locations] for a,b in locations]
        @lru_cache(None)
        def tail(mask,last):
            rest=mask^(1<<last)
            return min((tail(rest,i)+dist[i+1][last+1] for i in members(rest)),default=dist[0][last+1])
        prices.append([min(tail(m,i)+dist[i+1][0] for i in members(m)) for m,_ in routes])
        tail.cache_clear()
    return demands,routes,prices,groups


def run_dag(run,j,d,routes,prices):
    header=f'{j["n"]} {j["k"]} 100 {j["B"]} {len(routes)} {len(prices)}'
    lines=[header," ".join(map(str,d))]
    for i,(mask,load) in enumerate(routes):
        lines.append(f"{mask} {load} "+" ".join(str(p[i]) for p in prices))
    proc=subprocess.run([run/"bin/profile_dag",j["mode"]],input="\n".join(lines),
                        text=True,capture_output=True)
    if proc.returncode==3: raise MemoryError(proc.stderr)
    if proc.returncode: raise RuntimeError(proc.stderr or str(proc.returncode))
    profiles=[{} for _ in prices]; timing=[]
    for row in proc.stdout.splitlines():
        kind,s,*v=row.split();i=int(s)
        if kind=="T":
            timing.append(dict(build_s=float(v[0]),evaluate_s=float(v[1]),states=int(v[2]),
                               edges=int(v[3]),labels=int(v[4])))
        else:
            code,count,cost=map(int,v);profiles[i][code]=[count,cost]
    assert all(p and 0 in p for p in profiles)
    return profiles,timing


def design_costs(profile,k,B):
    designs=[d for d in combinations_with_replacement(range(B+1),k) if sum(d)==B]
    decoded=[]
    for code,(_,cost) in profile.items():
        e=[t for t in range(1,B+1) for _ in range((code>>(4*(t-1)))&15)]
        decoded.append(([0]*(k-len(e))+e,cost))
    return {"-".join(map(str,d)):min(c for e,c in decoded if all(a<=b for a,b in zip(e,d))) for d in designs}


def oracle(j,columns,prices):
    # Deliberately enumerate entire partitions for the smallest cases.
    lookup={m:(q,c) for (m,q),c in zip(columns,prices)}
    out={}
    def visit(left,t,spent,code,cost):
        if not t:
            if left==0:
                n,b=out.get(code,(0,cost));out[code]=[n+1,min(b,cost)]
            return
        if not left:return
        anchor=left & -left
        for mask,(load,value) in lookup.items():
            e=max(load-100,0)
            if mask&anchor and mask&left==mask and spent+e<=j["B"]:
                visit(left^mask,t-1,spent+e,code+((1<<(4*(e-1))) if e else 0),cost+value)
    visit((1<<j["n"])-1,j["k"],0,0,0)
    return out


def certificate(j,routes,c,groups):
    # Feasible start from the generator, followed by strictly improving two-route exchanges.
    t=perf_counter();assert j["k"]==6 and j["B"]==4
    options={m:(load,c[i]) for i,(m,load) in enumerate(routes)}
    groups=groups[:];initial=sum(options[m][1] for m in groups)
    for _ in range(30):
        move=None;best=0
        for a,b in combinations(range(6),2):
            union=groups[a]|groups[b];anchor=union&-union; rest=union^anchor;sub=rest
            others=[max(0,options[m][0]-100) for i,m in enumerate(groups) if i not in (a,b)]
            while True:
                one=sub|anchor;two=union^one
                if one in options and two in options:
                    lo,x=options[one];lt,y=options[two]
                    delta=options[groups[a]][1]+options[groups[b]][1]-x-y
                    excess=sorted(others+[max(0,lo-100),max(0,lt-100)])
                    if delta>best and all(i<=z for i,z in zip(excess,(0,0,0,0,1,3))):
                        best=delta;move=(a,b,one,two)
                if not sub:break
                sub=(sub-1)&rest
        if move is None:break
        groups[move[0]],groups[move[1]]=move[2:]
    incumbent=sum(options[m][1] for m in groups)
    assert sorted(i for m in groups for i in members(m))==list(range(j["n"]))
    assert all(i<=z for i,z in zip(sorted(max(0,options[m][0]-100) for m in groups),(0,0,0,0,1,3)))
    heu_s=perf_counter()-t
    n=j["n"];masks=np.array([m for m,_ in routes],dtype=np.int64)
    rr=[];cc=[]
    for idx,mask in enumerate(masks):
        for i in [*members(int(mask)),n]:rr.append(i);cc.append(idx)
    eq=coo_matrix((np.ones(len(rr),dtype=np.int64),(rr,cc)),shape=(n+1,len(routes))).tocsr()
    ub=csr_matrix(np.array([max(0,ld-100) for _,ld in routes],dtype=np.int64)[None,:])
    costs=np.array(c,dtype=np.int64)
    triples=np.array([sum(1<<i for i in nodes) for nodes in combinations(range(n),3)])
    used=set();lb=0;raw=None;t=perf_counter()
    for rnd in range(3):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore",category=OptimizeWarning)
            res=linprog(costs,A_eq=eq,b_eq=[1]*n+[6],A_ub=ub,b_ub=[4]+[1]*(ub.shape[0]-1),
                        bounds=(0,None),method="highs",options={"threads":1})
        if not res.success: raise RuntimeError(res.message)
        lb=max(lb,certified_dual(eq,ub,costs,res.eqlin.marginals,res.ineqlin.marginals))
        if raw is None:raw=lb
        if rnd==2 or lb==incumbent:break
        positive=res.x>1e-9
        ol=triples[:,None]&masks[positive]
        violations=((ol&(ol-1))!=0)@res.x[positive]-1
        selected=[int(i) for i in np.argsort(-violations,kind="stable") if violations[i]>1e-7 and i not in used][:12]
        if not selected:break
        used.update(selected);ol=triples[selected,None]&masks
        ub=vstack([ub,csr_matrix(((ol&(ol-1))!=0).astype(np.int64))],format="csr")
    assert lb<=incumbent
    return dict(initial=initial,incumbent=incumbent,lp_bound=raw,cut_bound=lb,
                certified_gain_pct=100*(incumbent-lb)/incumbent,heuristic_s=heu_s,lp_s=perf_counter()-t)


def run_task(run,j):
    t=perf_counter();d,r,p,g=make_case(run,j);prep=perf_counter()-t
    base=dict(columns=len(r),prep_s=prep)
    if j["kind"]=="certificate":
        return dict(**base,**certificate(j,r,p[0],g))
    if j["kind"]=="anchor":
        lines=[f"24 100 {len(r)}"]+[f"{m} {p[0][i]} {load}" for i,(m,load) in enumerate(r)]
        proc=subprocess.run([run/"bin/six_join",j["mode"]],input="\n".join(lines),text=True,capture_output=True,check=True)
        prof={}
        for line in proc.stdout.splitlines():
            code,count,cost,*witness=map(int,line.split())
            # Decode the three-bit legacy labels into four-bit digits.
            digits=[(code>>(3*i))&7 for i in range(4)]
            conv=sum(x<<(4*i) for i,x in enumerate(digits))
            prof[conv]=[count,cost]
        u,b,s=proc.stderr.split()
        return dict(**base,profile=prof,join_s=float(s),unions=int(u),bins=int(b))
    if j["kind"]=="batch" and j["mode"]=="cold":
        j=dict(j,mode="hash"); pp=[];times=[]
        for price in p:
            prof,ts=run_dag(run,j,d,r,[price]); pp+=prof;times+=ts
    else:
        pp,times=run_dag(run,j,d,r,p)
    if j["n"]<=12: assert pp[0]==oracle(j,r,p[0])
    ds=design_costs(pp[0],j["k"],j["B"]) if j["kind"]=="policy" else {}
    return dict(**base,profile=pp[0],hashes=[hashlib.sha256(json.dumps(sorted(x.items())).encode()).hexdigest() for x in pp],
                design_costs=ds,timings=times)


if __name__=="__main__":
    try:
        result=run_task(Path(sys.argv[1]),json.loads(sys.argv[2]))
        print(json.dumps(dict(status="ok",result=result)))
    except MemoryError as error:
        print(json.dumps(dict(status="resource_limit",detail=str(error))))

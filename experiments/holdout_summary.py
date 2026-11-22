"""Summarize every planned six-vehicle instance; check a fixed subset by MILP."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import median

from allocation_transfer import HERE, POLICIES, solve_parent
from benchmark import write_csv

RESULTS=HERE/"results"


def read(path):
    with path.open() as src:
        return list(csv.DictReader(src))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-milp",type=Path,metavar="PARENT_DIR")
    args=parser.parse_args()
    manifest=read(HERE/"holdout_parents.csv")
    if args.check_milp:
        checks=[]
        for i in (0,6,13,19):
            checks.extend(solve_parent((args.check_milp,10+i,manifest[i]["parent"],POLICIES)))
        write_csv(RESULTS/"six_vehicle_holdout_milp.csv",checks)
        return
    rows=[]
    costs={}
    for cohort,filename in (("initial","six_vehicle_profiles.csv"),("holdout","six_vehicle_holdout.csv")):
        groups=defaultdict(list)
        for row in read(RESULTS/filename):
            groups[row["parent"]].append(row)
        assert len(groups)==(10 if cohort=="initial" else 20)
        for name,entries in groups.items():
            if any(x["status"]!="complete" for x in entries):
                rows.append(dict(parent=name,cohort=cohort,status="timeout"))
                continue
            by_design={x["design"]:int(x["cost"]) for x in entries}
            assert len(by_design)==5
            balanced=by_design["0 0 1 1 1 1"]
            fixed=by_design["0 0 0 0 1 3"]
            best=min(by_design.values())
            costs[name]=dict(balanced=balanced,three_plus_one=fixed,adaptive=best)
            rows.append(dict(parent=name,cohort=cohort,status="complete",balanced=balanced,three_plus_one=fixed,
                             adaptive=best,balanced_gain_pct=100*(balanced-best)/balanced,
                             fixed_gain_pct=100*(fixed-best)/fixed))
    for x in read(RESULTS/"six_vehicle_holdout_milp.csv"):
        value=costs[x["parent"]][x["policy"]]
        if x["incumbent"]:
            assert round(float(x["incumbent"]))>=value
        if x["lower_bound"]:
            assert float(x["lower_bound"])<=value+1e-5
        if x["status"]=="0":
            assert round(float(x["incumbent"]))==value
    write_csv(RESULTS/"six_vehicle_cohort_summary.csv",rows)
    for cohort in ("initial","holdout","all"):
        group=[r for r in rows if r["status"]=="complete" and (cohort=="all" or r["cohort"]==cohort)]
        for key in ("balanced_gain_pct","fixed_gain_pct"):
            v=[r[key] for r in group]
            print(cohort,key,len(v),sum(p>0 for p in v),median(v),max(v))


if __name__=="__main__":
    main()

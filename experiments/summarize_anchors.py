"""Report ratios within parent after taking the median over available repeats."""
import csv
from collections import defaultdict
from statistics import median, quantiles
from pathlib import Path

RESULTS=Path(__file__).resolve().parent/"results"


def main():
    groups=defaultdict(lambda:defaultdict(list))
    with (RESULTS/"anchor_ablation.csv").open() as src:
        for r in csv.DictReader(src):
            groups[r["parent"]][r["mode"]].append(r)
    assert len(groups)==30
    for mode in ("two","three"):
        for field in ("join_s","end_to_end","unions","bins"):
            ratios=[]
            for methods in groups.values():
                def center(rows):
                    if field=="end_to_end":
                        return median(float(r["prepared_s"])+float(r["elapsed_s"]) for r in rows)
                    return median(float(r[field]) for r in rows)
                ratios.append(center(methods["baseline"])/center(methods[mode]))
            print(mode,field,quantiles(ratios,method="inclusive"),min(ratios),max(ratios),
                  sum(v>1 for v in ratios))
    for cohort in ("initial","holdout"):
        v=[median(float(r["join_s"]) for r in modes["baseline"])/median(float(r["join_s"]) for r in modes["three"])
           for modes in groups.values() if modes["baseline"][0]["cohort"]==cohort]
        print(cohort,median(v))
    with (RESULTS/"regret_bound.csv").open() as src:
        rows=list(csv.DictReader(src))
    for threshold in (0,.5,1,2):
        vals=[]
        for key in ("lp_bound","cut_bound","adaptive_cost"):
            vals.append(sum(100*(int(r["incumbent"])-int(r[key]))<=threshold*int(r["incumbent"]) for r in rows))
        print("threshold",threshold,vals)


if __name__=="__main__":
    main()

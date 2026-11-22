"""Paired descriptive summaries, giving every XSH instance equal weight."""
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median, quantiles

RESULTS = Path(__file__).resolve().parent / "results"


def read(name):
    with (RESULTS / name).open() as source:
        return list(csv.DictReader(source))


def summary(values):
    q1, center, q3 = quantiles(values, method="inclusive")
    return [round(x, 4) for x in (q1, center, q3)]


def main():
    reference = {(r["instance"], r["scenario"]): int(r["objective"])
                 for r in read("per_instance.csv") if r["mode"] == "bounded"}
    groups = defaultdict(list)
    for r in read("geometry_control.csv"):
        groups[r["instance"]].append(r)
    if len(groups) != 55 or any(len(g) != 51 for g in groups.values()):
        raise ValueError("Expected 55 complete blocks with 51 draws each")
    effects, shifts, pilot, followup, all_draws = [], [], [], [], []
    original_above_all = 0
    for name, rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda r: int(r["seed"]))
        values = [float(r["reduction_pct"]) for r in rows]
        base, plus = [reference[name, level] for level in ("original", "plus_1_unit")]
        original = 100 * (1 - plus / base)
        effects.append(median(values))
        shifts.append(median(values) - original)
        pilot.append(median(values[:5]))
        followup.append(median(values[5:]))
        original_above_all += original > max(values)
        all_draws.extend(values)
    result = dict(instances=len(groups), pairs=len(all_draws), strict=sum(x>0 for x in all_draws),
                  unchanged=all_draws.count(0.), max_reduction=max(all_draws),
                  shuffled_quartiles=summary(effects), shift_quartiles=summary(shifts),
                  shuffle_median_larger=sum(s>0 for s in shifts),
                  original_above_all=original_above_all,
                  first_five=median(pilot), fresh_46=median(followup))
    print(json.dumps(result, indent=2))
    (RESULTS / "geometry_summary.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()

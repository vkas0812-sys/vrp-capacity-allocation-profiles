"""Count early/late pricing candidates without constructing tours (positive demands)."""
import argparse
import csv
import hashlib
import re
from math import ceil
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
LEVELS = ("original", "plus_1_unit", "plus_2pct", "plus_5pct", "plus_10pct")


def coefficients(demands, capacity):
    counts = [1] + [0] * capacity
    for quantity in demands:
        if quantity <= 0:
            raise ValueError("Customer demands must be positive")
        for load in range(capacity, quantity - 1, -1):
            counts[load] += counts[load - quantity]
    return counts


def read_csv(name):
    with (RESULTS / name).open() as source:
        return list(csv.DictReader(source))


def profile(name, family, demands, base, fleet, digest):
    capacities = [base, base + 1, *(base + ceil(base * p / 100) for p in (2, 5, 10))]
    counts = coefficients(demands, max(capacities))
    for level, cap in zip(LEVELS, capacities):
        slack = fleet * cap - sum(demands)
        lower = max(1, cap - slack)
        late = sum(counts[1:cap + 1])
        early = sum(counts[lower:cap + 1])
        yield dict(family=family, instance=name, customers=len(demands), fleet=fleet,
                   scenario=level, capacity=cap, slack=slack, lower=lower, early=early,
                   late=late, retained=early / late, sha256=digest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xsh", type=Path)
    parser.add_argument("external", type=Path)
    args = parser.parse_args()
    records = []
    parent_names = sorted({r["parent"] for r in read_csv("external_ablation.csv")})
    for family, paths in (("XSH", sorted(args.xsh.glob("XSH-n20-k4-*.vrp"))),
                          ("X", [args.external / (n + ".vrp") for n in parent_names])):
        for path in paths:
            raw = path.read_bytes()
            data = raw.decode().split("DEMAND_SECTION")[1].split("DEPOT_SECTION")[0]
            demands = [int(q) for node, q in (line.split() for line in data.strip().splitlines()) if int(node) != 1]
            base = int(re.search(r"(?m)^CAPACITY\s*:\s*(\d+)", raw.decode())[1])
            fleet = int(re.search(r"-k(\d+)", path.stem)[1])
            records.extend(profile(path.stem, family, demands, base, fleet, hashlib.sha256(raw).hexdigest()))
    index = {(r["instance"], r["scenario"]): r for r in records}
    checked = 0
    for row in read_csv("per_instance.csv") + read_csv("slack_ablation.csv"):
        expected = index[row["instance"], row["scenario"]]["early" if row["mode"] == "bounded" else "late"]
        observed = int(row.get("candidate_routes") or row["candidates"])
        if observed != expected:
            raise ValueError((row["instance"], row["scenario"], observed, expected))
        checked += 1
    if len(index) != 325:
        raise ValueError("Expected five scenarios for 55 XSH and ten full X parents")
    with (RESULTS / "load_profile.csv").open("w") as out:
        writer = csv.DictWriter(out, fieldnames=records[0])
        writer.writeheader()
        writer.writerows(records)
    print(f"{len(index)} profiles; {checked} enumeration rows matched")


if __name__ == "__main__":
    main()

"""Generate paper figures and per-instance appendix from the recorded experiments."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median, quantiles

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "experiments/results"


def read(name):
    with (RESULTS / (name + ".csv")).open() as source:
        return list(csv.DictReader(source))


def anchor_speedup():
    times = defaultdict(lambda: defaultdict(list))
    for row in read("anchor_ablation"):
        elapsed = float(row["prepared_s"]) + float(row["elapsed_s"])
        times[row["parent"]][row["mode"]].append(elapsed)

    fig, ax = plt.subplots(figsize=(4.75, 1.85), layout="constrained")
    for y, mode in enumerate(("three", "two")):
        ratios = [median(t["baseline"]) / median(t[mode]) for t in times.values()]
        q1, mid, q3 = quantiles(ratios, method="inclusive")
        ax.hlines(y, min(ratios), max(ratios), color="#66747a", lw=1.4)
        ax.plot([min(ratios), max(ratios)], [y, y], "|", color="#66747a", ms=7)
        ax.hlines(y, q1, q3, color="#146672", lw=9)
        ax.plot(mid, y, "D", color="#172b33", markeredgecolor="white", ms=7)
        ax.text(mid, y+.18, f"{mid:.2f}×", ha="center", weight="bold", fontsize=11)
    ax.axvline(1, color="#666666", linestyle="--", lw=1, zorder=0)
    ax.set(yticks=[0, 1], yticklabels=["Three anchors", "Two anchors"],
           xticks=range(1, 9), xlim=(.75, 8), ylim=(-.42, 1.53),
           xlabel="Speedup over unrestricted join (×)")
    ax.tick_params(axis="y", length=0)
    for side in ("left", "right", "top"):
        ax.spines[side].set_visible(False)
    fig.savefig(HERE / "anchor-speedup.pdf")
    plt.close(fig)


def policy_gain():
    cohorts = [
        ("Four vehicles · 55 instances", read("allocation_comparison"), "gain_vs_uniform", "gain_vs_fixed"),
        ("Six vehicles · 30 instances", read("six_vehicle_cohort_summary"), "balanced_gain_pct", "fixed_gain_pct"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(4.9, 2.75), sharey=True)
    for ax, (title, rows, even, fixed) in zip(axes, cohorts):
        for key, label, color, style in [(even, "Even split", "#166c74", "-"),
                                         (fixed, "Three-plus-one", "#713f24", "--")]:
            gains = [float(row[key]) for row in rows]
            thresholds = sorted({0, *gains})
            ax.step(thresholds, [100 * sum(g > t for g in gains) / len(gains)
                                 for t in thresholds], where="post", color=color,
                    ls=style, lw=1.8, label=label)
        ax.set(title=title, xlim=(-.2, 15), xticks=[0, 5, 10, 15],
               ylim=(-2, 102), yticks=[0, 25, 50, 75, 100])
        ax.grid(axis="y", lw=.45, color="#cccccc")
        ax.spines[["top", "right"]].set_visible(False)
        ax.title.set_fontsize(10)
    axes[0].set_ylabel("Instances above threshold (%)", fontsize=9)
    fig.supxlabel("Distance saving threshold (%)", y=.145, fontsize=10)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center",
               ncol=2, frameon=False, bbox_to_anchor=(.5, -.015), fontsize=9)
    fig.subplots_adjust(left=.14, right=.98, bottom=.33, top=.86, wspace=.2)
    fig.savefig(HERE / "policy-gain.pdf")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xsh", type=Path)
    args = parser.parse_args()
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    anchor_speedup()
    policy_gain()
    solutions = json.loads((RESULTS / "solutions.json").read_text())
    first = [s for s in solutions if s["instance"].endswith("-01")][:2]
    lines = (args.xsh / (first[0]["instance"] + ".vrp")).read_text()
    xy = [list(map(float, r.split()[1:])) for r in lines.split("NODE_COORD_SECTION")[1].split("DEMAND_SECTION")[0].strip().splitlines()]
    fig, axes = plt.subplots(1, 2, figsize=(5.4, 2.5), layout="constrained")
    for ax, s in zip(axes, first):
        for route, style, color in zip(s["routes"], ["-", "--", "-.", ":"], ["#146d73", "#b24e27", "#325998", "#684780"]):
            points = [xy[i] for i in [0, *route["customers"], 0]]
            ax.plot(*zip(*points), linestyle=style, marker=".", color=color, linewidth=1.1)
        ax.scatter(*xy[0], marker="s", color="black", zorder=4)
        ax.set(aspect="equal", title=f"Capacity {s['capacity']}  |  cost {s['objective']}", xlabel="x")
    axes[0].set_ylabel("y")
    fig.savefig(HERE / "route-example.pdf")
    plt.close(fig)
    orig = {(r["instance"], r["scenario"]):r for r in read("per_instance") if r["mode"] == "bounded"}
    shuffles = defaultdict(list)
    for r in read("geometry_control"):
        shuffles[r["instance"]].append(float(r["reduction_pct"]))
    fig, ax = plt.subplots(figsize=(5.1, 3.8), layout="constrained")
    rows = []
    for name, draws in sorted(shuffles.items()):
        base,plus = [orig[name,level] for level in ("original","plus_1_unit")]
        drop = 100 * (1-int(plus["objective"])/int(base["objective"]))
        ax.plot([drop]*2, [min(draws), max(draws)], lw=.65, color="#adbbc4")
        ax.scatter(drop, median(draws), c="#146d73", s=13, zorder=3)
        rows.append([name[-2:],base["capacity"],base["objective"],plus["objective"],base["partitions"],plus["partitions"],f"{drop:.1f}",f"{median(draws):.1f}"])
    lim = max(ax.get_xlim()[1], ax.get_ylim()[1])
    ax.plot([0,lim],[0,lim], "--", c="#333333", lw=.8)
    ax.set(xlabel="Original assignment: optimal distance reduction (%)", ylabel="Shuffled assignments: reduction (%)", xlim=(0,lim),ylim=(0,lim))
    fig.savefig(HERE / "assignment-control.pdf")
    for i, block in enumerate((rows[:28],rows[28:])):
        (HERE / f"pairs-{i+1}.tex").write_text("".join(" & ".join(row)+r" \\"+"\n" for row in block))


if __name__ == "__main__":
    main()

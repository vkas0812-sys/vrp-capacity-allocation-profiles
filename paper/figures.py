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


def anchor_example():
    from matplotlib.patches import FancyBboxPatch
    fig, ax = plt.subplots(figsize=(5.3, 1.52), layout="constrained")
    ax.set(xlim=(-1.6, 6.4), ylim=(-.74, 2.45))
    ax.axis("off")
    ax.text(-1.55, 2.18, "Route A carries anchors 1, 2; route B carries anchor 3.", fontsize=9.2)
    ax.text(1.38, 1.55, "Left triple", ha="center", weight="bold", fontsize=9)
    ax.text(4.8, 1.55, "Complement", ha="center", weight="bold", fontsize=9)
    for y, label, routes in [(1, "Keep", "ABCDEF"), (.15, "Discard", "ACDBEF")]:
        ax.text(-1.48, y, label, va="center", weight="bold", fontsize=9)
        for i, route in enumerate(routes):
            x=i+.38+(.44 if i>=3 else 0)
            anchored=route in "AB"
            ax.add_patch(FancyBboxPatch((x-.39,y-.28),.78,.56,
                         boxstyle="round,pad=.02,rounding_size=.08",
                         facecolor="#dcf0ef" if anchored else "white",
                         edgecolor="#156966" if anchored else "#9aa8ae", lw=1.1))
            ax.text(x,y,route,ha="center",va="center",fontsize=9.5,weight="bold" if anchored else "normal")
    ax.plot([3.07,3.07],[-.20,1.33],color="#88959a",lw=.8)
    ax.text(-1.55,-.54,"Valid left triples:  ABC, ABD, ABE, ABF",fontsize=9.1,color="#144a4a")
    fig.savefig(HERE / "anchor-example.pdf")
    plt.close(fig)


def supplementary_distributions():
    rows = read("allocation_comparison")
    gains = [float(r["gain_vs_uniform"]) for r in rows]
    edges = [0, 2, 4, 6, 8, 10, 12, 14, 16]
    counts = [sum(g==0 for g in gains)] + [sum(lo<g<=hi for g in gains) for lo,hi in zip(edges,edges[1:])]
    assert len(rows)==sum(counts)==55
    fig, ax = plt.subplots(figsize=(4.9, 2.15), layout="constrained")
    bars = ax.bar(range(len(counts)), counts, color=["#849298"]+["#216b70"]*8, width=.82)
    ax.bar_label(bars, fontsize=8, padding=2)
    ax.set(xticks=range(len(counts)), xticklabels=["0"]+[f"{a}–{b}" for a,b in zip(edges,edges[1:])],
           ylabel="Instances", xlabel="Distance saved relative to equal allocation (%)", ylim=(0,max(counts)*1.22))
    ax.tick_params(axis="x",labelsize=8)
    ax.spines[["top","right"]].set_visible(False)
    fig.savefig(HERE / "allocation-histogram.pdf")
    plt.close(fig)

    profiles = {(r["instance"],r["scenario"]):r for r in read("per_instance") if r["mode"]=="bounded"}
    ratios, savings = [], []
    for row in rows:
        base, plus = (profiles[row["instance"],level] for level in ("original","plus_1_unit"))
        ratios.append(int(plus["partitions"])/int(base["partitions"]))
        savings.append(100*(1-int(plus["objective"])/int(base["objective"])))
    fig, ax = plt.subplots(figsize=(4.9,2.55),layout="constrained")
    ax.scatter(ratios,savings,s=23,color="#216b70",alpha=.82,edgecolor="white",linewidth=.45)
    ax.set(xlabel="Feasible partitions at Q+1 / feasible partitions at Q",
           ylabel="Distance saved (%)")
    ax.spines[["top","right"]].set_visible(False)
    fig.savefig(HERE / "partition-growth.pdf")
    plt.close(fig)


def anchor_speedup():
    masks = defaultdict(dict)
    times = defaultdict(lambda: defaultdict(list))
    for row in read("anchor_ablation"):
        masks[row["parent"]][row["mode"]] = int(row["unions"])
        elapsed = float(row["prepared_s"]) + float(row["elapsed_s"])
        times[row["parent"]][row["mode"]].append(elapsed)

    fig, (ax, states) = plt.subplots(1, 2, figsize=(5.3, 1.88), layout="constrained", gridspec_kw={"width_ratios": [1.25, 1]})
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
           xlabel="End-to-end speedup (×)")
    ax.tick_params(axis="y", length=0)
    for side in ("left", "right", "top"):
        ax.spines[side].set_visible(False)
    modes = ("baseline", "two", "three")
    medians = [median(m[mode] for m in masks.values()) / 1000 for mode in modes]
    bars = states.barh(["Baseline","Two","Three"], medians, color=["#819096","#6aa3a2","#156966"])
    states.bar_label(bars, fmt="%.0f", fontsize=8, padding=2)
    states.invert_yaxis()
    states.set(xlabel="Triple masks (thousands)", xlim=(0, 1.30*max(medians)))
    for pane in (ax, states):
        pane.spines[["right","top"]].set_visible(False)
        pane.tick_params(labelsize=8)
        pane.xaxis.label.set_fontsize(8.5)
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


def allocation_pipeline():
    from matplotlib.patches import FancyBboxPatch

    fig, ax = plt.subplots(figsize=(5.05, 2.12))
    fig.subplots_adjust(0, 0, 1, 1)
    ax.set(xlim=(0, 10), ylim=(0, 4))
    ax.axis("off")

    def box(x, y, w, h, title, detail, color, fill):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=.09",
                                    facecolor=fill, edgecolor=color, linewidth=1))
        ax.text(x+w/2, y+h*.70, title, ha="center", va="center", fontsize=9,
                weight="bold", color=color)
        ax.text(x+w/2, y+h*.31, detail, ha="center", va="center", fontsize=8, linespacing=1.12)

    def arrow(start, end):
        ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="-|>",
                    color="#344c57", lw=1.05, shrinkA=1, shrinkB=1))

    ax.text(.05, 3.64, "Demands, distances, fleet size and upgrade budget", fontsize=9.2)
    arrow((1.45, 3.45), (1.45, 2.82))
    box(.05, 1.44, 2.81, 1.35, "Price routes", "Filter by load\nHeld–Karp tour cost", "#225a72", "#edf5f8")
    box(3.55, 2.17, 2.92, 1.15, "Four vehicles", "Join complementary\nroute pairs", "#136659", "#ebf5f1")
    box(3.55, .60, 2.92, 1.15, "Six vehicles", "Join anchored triples\nCorrect multiplicities", "#136659", "#ebf5f1")
    box(7.13, 1.44, 2.78, 1.35, "Overload profile", "Minimum distance\nand count per class", "#75431e", "#fcf1e6")
    for y in (2.72, 1.18):
        arrow((2.87, 2.12), (3.53, y))
        arrow((6.48, y), (7.11, 2.12))
    arrow((8.52, 1.40), (8.52, .83))
    ax.text(8.52, .63, "Query fixed designs\nor the adaptive optimum", ha="center", va="top", fontsize=8.4)
    fig.savefig(HERE / "allocation-pipeline.pdf")
    plt.close(fig)


def five_design_benchmark():
    groups = defaultdict(list)
    for row in read("five_design_benchmark"):
        groups[row["instance"]].append(row)
    assert len(groups) == 55 and all(len(rows) == 5 for rows in groups.values())
    misses = defaultdict(int)
    for rows in groups.values():
        for row in rows:
            misses[row["design"]] += int(row["milp_status"]) != 0

    fig, (ax, bar) = plt.subplots(1, 2, figsize=(5.25, 2.12),
                                 gridspec_kw={"width_ratios": [1.65, 1]}, layout="constrained")
    for field, title, color, marker in [
        ("milp_seconds_all", "Five MILPs", "#aa512e", "o"),
        ("profile_seconds_all", "One profile", "#11667a", "."),
    ]:
        # Each instance's five rows repeat the time for the whole design set.
        series = [(int(name.rsplit("-", 1)[1]), float(rows[0][field]))
                  for name, rows in sorted(groups.items())]
        ax.plot(*zip(*series), marker=marker, ms=2.7, lw=.83, color=color, label=title)
    ax.set(yscale="log", xlabel="XSH instance", ylabel="Wall time (s, log scale)",
           xticks=[1, 15, 30, 45, 55])
    ax.legend(frameon=False, fontsize=7, loc="lower left", ncol=2, handlelength=1.2,
              columnspacing=.6, bbox_to_anchor=(0, 1.01), borderaxespad=0)
    ax.grid(axis="y", lw=.5, color="#d7dedf")
    designs = sorted(misses)
    labels = ["+".join(v for v in reversed(d.split()) if v != "0") for d in designs]
    bars = bar.barh(labels, [misses[d] for d in designs], color="#aa512e", height=.53)
    bar.bar_label(bars, fontsize=8, padding=3)
    bar.invert_yaxis()
    bar.set(xlabel="Unproved MILP optima", xlim=(0, max(misses.values())+.8),
            xticks=range(max(misses.values())+1))
    for a in (ax, bar):
        a.spines[["right","top"]].set_visible(False)
        a.tick_params(labelsize=8)
    fig.savefig(HERE / "five-design-benchmark.pdf")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xsh", type=Path)
    args = parser.parse_args()
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    anchor_speedup()
    anchor_example()
    supplementary_distributions()
    policy_gain()
    allocation_pipeline()
    five_design_benchmark()
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

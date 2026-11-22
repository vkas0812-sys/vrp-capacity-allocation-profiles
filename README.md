# Exact Capacity Allocation Profiles for Vehicle Routing with Tight Fleets

[![QOBLIB Benchmark](https://img.shields.io/badge/QOBLIB-09--routing%20(CVRP)-blue)](https://github.com/ZIB-AOPT/QOBLIB/tree/main/09-routing)
[![C++17](https://img.shields.io/badge/C%2B%2B-17%20(-O3)-00599C?logo=cplusplus)](src/)
[![QOBLIB Checker](https://img.shields.io/badge/Verified-check__cvrp%20(275%2F275%20VALID)-198038)](https://github.com/ZIB-AOPT/QOBLIB/tree/main/09-routing/check)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](CITATION.cff)

**Authors (Equal Contribution / Shared First Authorship):**
- **Kha Anh Son Vuong** ([`vkas0812-sys`](https://github.com/vkas0812-sys)) — *School of Industrial Engineering and Management, Ho Chi Minh City International University (VNU-HCM), Ho Chi Minh City, Vietnam* · **ORCID:** [0009-0006-3435-7990](https://orcid.org/0009-0006-3435-7990) · **Email:** [sonvka31@mp.hcmiu.edu.vn](mailto:sonvka31@mp.hcmiu.edu.vn)
- **Luong Thanh Tra Ngo** ([`ngotra2710`](https://github.com/ngotra2710), *Corresponding Author*) — *FPT University, Greenwich Vietnam, Ho Chi Minh Campus, Vietnam* · **ORCID:** [0009-0003-2268-3498](https://orcid.org/0009-0003-2268-3498) · **Email:** [TraNLT2@fe.edu.vn](mailto:TraNLT2@fe.edu.vn)

**Related QOBLIB Submissions & Baseline Repository:**
- [ZIB-AOPT/QOBLIB PR #93 (`TC-Exact` — 55/55 Proven Optimal)](https://github.com/ZIB-AOPT/QOBLIB/pull/93)
- [ZIB-AOPT/QOBLIB PR #94 (`SQA-Subspace` — 55/55 Optimal)](https://github.com/ZIB-AOPT/QOBLIB/pull/94)
- [Baseline $\Delta=0$ Reference Repository (`qoblib-routing-exact-sqa`)](https://github.com/vkas0812-sys/qoblib-routing-exact-sqa)

---

## Abstract

When total fleet capacity equals customer demand ($\sum_{i=1}^n d_i = KQ$, fleet slack $\Delta = 0$), a dispatcher acquiring extra carrying capacity must decide how to distribute those units across vehicles. Building on our exact zero-slack set-partitioning baseline (**`TC-Exact`**, which certifies all 55 QOBLIB `09-routing` `XSH-n20-k4` instances in `3.33 ms/instance`), this repository develops **Exact Capacity Allocation Profiles** and **Anchored Multi-Route Joins** for tight-fleet vehicle routing under positive capacity budgets ($\Delta > 0$) and larger fleets ($K = 6, n = 24$):

1. **Exact 4-Vehicle Overload Profiles ([`experiments/allocation_cover.cpp`](experiments/allocation_cover.cpp)):** Groups customer partitions by sorted route overloads $(e_1 \le e_2 \le e_3 \le e_4)$ via a symmetry-broken $2+2$ route-pair join. After Held-Karp route pricing, a single profile returns the exact minimum distance and feasible partition count for all five 4-unit allocation designs (`(4,0,0,0)`, `(3,1,0,0)`, `(2,2,0,0)`, `(2,1,1,0)`, `(1,1,1,1)`) in a median of **`0.058 s`**, compared with **`1.452 s`** (`26.07x` speedup) for five time-limited Set-Partitioning MILP solves.
2. **The Asymmetric `3+1` Allocation Rule ([`experiments/allocation.py`](experiments/allocation.py)):** On the 55 four-vehicle QOBLIB `XSH-n20-k4` instances, choosing the allocation after observing demand shortens the optimal tour distance relative to equal allocation `(1,1,1,1)` in **41 of 55 cases** (median reduction `1.48%`, maximum **`14.26%`** on `XSH-n20-k4-09`, dropping from `680` to `583`). In leave-one-out cross-validation, **all 55 training folds select the asymmetric `3+1` split `(3,1,0,0)`**, which attains the global adaptive optimum on **45 of 55 held-out instances** (vs. only `14/55` for uniform `(1,1,1,1)`).
3. **Partial Fleet Upgrades & Demand-Placement Controls ([`experiments/upgrade_cover.cpp`](experiments/upgrade_cover.cpp), [`experiments/geometry_control.py`](experiments/geometry_control.py)):** Proves that under $D = 4Q$, upgrading 3 vehicles to $Q+1$ always achieves the exact same optimum as upgrading all 4 vehicles ($z_3 = z_4$), while upgrading just 1 or 2 vehicles recovers a median of **`94.29%`** and **`100%`** (`50/55` instances) of the full distance saving. Evaluates `2,805` demand-reassignment shuffles (`5,610` exact solves) to isolate geometric vs. load-packing effects.
4. **6-Vehicle Transfer & Anchored 3-Customer Routing Join ([`experiments/six_vehicle_join.cpp`](experiments/six_vehicle_join.cpp)):** Evaluates the frozen `3+1` rule on 30 six-vehicle instances ($n = 24$ customers, base capacity $Q = 100$, coordinates from CVRPLIB-X), where adaptive allocation improves on the even split `(1,1,1,1,0,0)` in **29 of 30 cases** and on `3+1` in only 14. Introduces an exact $3+3$ route join that anchors $a = 3$ distinguished customers on one side with combinatorial multiplicity correction $20 / \binom{6-s}{3-s}$, reducing stored triple masks by **`4.53x`** and accelerating end-to-end computation by a median factor of **`3.59x`** while preserving 100% of class counts and optimal costs.

---

## Repository Architecture

This repository integrates the baseline zero-slack solvers (`src/`, `docs/`, `scripts/`), the bundled official QOBLIB Rust verifier (`check/`) and benchmark dataset (`instances/`), the capacity-allocation experimental suite (`experiments/`), and the Springer LNCS manuscript (`paper/`):

```text
vrp-capacity-allocation-profiles/
├── README.md                          # Master overview, results summary, and reproducibility guide
├── CITATION.cff                       # Citation metadata (Kha Anh Son Vuong & Luong Thanh Tra Ngo)
├── campaign_summary.csv               # Baseline Δ = 0 exact metrics across all 55 XSH-n20-k4 instances
│
├── check/                             # Official QOBLIB Rust solution verifier (check_cvrp)
│   ├── Cargo.toml & Cargo.lock
│   ├── README.md
│   └── src/bin/check_cvrp.rs          # Verifies route coverage, capacity, and EUC_2D rounded costs
│
├── instances/                         # All 55 QOBLIB 09-routing CVRP instances (XSH-n20-k4-01..55.vrp)
│
├── src/                               # Part I: Zero-Slack Baseline Solvers (Δ = 0, C++17)
│   ├── generate_submission_data.cpp   # TC-Exact + 5-seed SQA-Subspace campaign generator
│   └── qoblib_routing_experiments.cpp # 3-way baseline benchmark (SQA-Direct vs SQA-Subspace vs TC-Exact)
│
├── docs/                              # Technical documentation for the Δ = 0 foundation
│   ├── references.md                  # Full bibliography & QOBLIB XSH-n20-k4 provenance
│   ├── background.md                  # CVRP, QUBO penalty barriers, and PIMC-SQA theory
│   ├── methods.md                     # TC-Exact & SQA-Subspace algorithmic specification
│   ├── reproducibility.md             # Build instructions & deterministic seed formulas
│   └── results.md                     # Guide to campaign_summary.csv and baseline metrics
│
├── scripts/                           # Packaging & baseline verification utilities
│   ├── build_submission.py            # QOBLIB submission directory builder
│   ├── plot_figure1.py                # Baseline convergence & manifold collapse plotter
│   └── test_reproducibility.sh        # End-to-end automated verification script
│
├── experiments/                       # Part II: Capacity Allocation Profiles & 6-Vehicle Anchored Join
│   ├── README.md                      # Detailed experimental protocol & Vietnamese reproduction notes
│   ├── exact.cpp                      # Bounded/unpruned Held-Karp route pricer & 4-route exact cover
│   ├── replay_tc_exact.cpp            # Cross-check wrapper replaying src/qoblib_routing_experiments.cpp
│   ├── allocation_cover.cpp           # C++17 2+2 pair join computing all 4-vehicle overload profiles
│   ├── upgrade_cover.cpp              # C++17 partial fleet upgrade curve solver (direct/split/cached)
│   ├── six_vehicle_join.cpp           # C++17 3+3 six-route join (baseline, 2-anchor, 3-anchor modes)
│   ├── benchmark.py                   # 5-level capacity sweep + HiGHS MILP + official check_cvrp runner
│   ├── allocation.py                  # 4-unit allocation profile runner & Set-Partitioning MILP check
│   ├── five_design_benchmark.py       # Head-to-head timing: 1 Overload Profile vs 5 Fixed-Design MILPs
│   ├── six_vehicle_profiles.py        # 6-vehicle CVRPLIB-X runner & brute-force combinatorial oracle
│   ├── anchor_ablation.py             # Paired timing & memory benchmark for 2-anchor and 3-anchor joins
│   ├── regret_bound.py                # LP relaxation + 3-customer Subset-Row cut regret certificates
│   ├── geometry_control.py            # 51-seed demand-reassignment control experiment (5,610 solves)
│   ├── robustness.py                  # Early vs late load-filtering ablation & edge-flow MILP checks
│   ├── summarize_allocation.py        # Leave-one-out cross-validation & policy gain summary
│   ├── summarize_anchors.py           # Paired speedup quantiles & LP/cut certificate thresholds
│   ├── holdout_summary.py             # 30-instance (10 initial + 20 holdout) 6-vehicle summary
│   └── results/                       # 26 verified CSV/JSON experimental outputs (275/275 check_cvrp OK)
│
└── paper/                             # Springer LNCS (ICCSA) Manuscript & Vector Figures
    ├── main.tex & main.pdf            # Main manuscript ("Exact Capacity Allocation Profiles...")
    ├── supplement.tex & supplement.pdf# 10-page supplementary tables & edge-model formulations
    ├── figures.py                     # Reproducible publication figure generator
    └── *.pdf, *.png                   # Vector figures included in main.tex and supplement.tex
```

---

## Key Experimental Results

### 1. Capacity Sweep Across All 55 QOBLIB `XSH-n20-k4` Instances
Every solution across all 5 capacity levels ($55 \times 5 = 275$ solutions in [`experiments/results/solutions.json`](experiments/results/solutions.json)) is verified valid by the official QOBLIB Rust checker [`check_cvrp`](https://github.com/ZIB-AOPT/QOBLIB/tree/main/09-routing/check) ([`experiments/results/solution_verification.json`](experiments/results/solution_verification.json)):

| Per-Vehicle Capacity | Median Priced Sets | Median Feasible Partitions | Paired Partition Growth | Median Distance Saving (%) | Median Exact Time (ms) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| **Base ($Q$, $\Delta=0$)** | 536 | 2,334 | $1.00\times$ | $0.00\%$ | `1.74 ms` |
| **$+1$ unit ($Q+1$, $\Delta=4$)** | 2,624 | 88,338 | $39.90\times$ | **`10.79%`** | `9.40 ms` |
| **$+2\%$ ($Q+\lceil 0.02Q\rceil$)** | 10,783 | 5,237,545 | $2,147\times$ | **`15.64%`** | `66.43 ms` |
| **$+5\%$ ($Q+\lceil 0.05Q\rceil$)** | 22,557 | 63,376,232 | $25,045\times$ | **`16.96%`** | `175.62 ms` |
| **$+10\%$ ($Q+\lceil 0.10Q\rceil$)** | 38,279 | 427,619,367 | $173,404\times$ | **`18.92%`** | `417.97 ms` |

### 2. Allocating Four Extra Capacity Units Across Four Vehicles ($\Delta = +4$)

| Allocation Design | Attains Instance Optimum | Median Distance Excess vs. Adaptive Best | Leave-One-Out Selection Frequency |
| :--- | :---: | :---: | :---: |
| **`(3, 1, 0, 0)` (`3+1` Rule)** | **45 / 55 (81.8%)** | **`0.00%`** | **55 / 55 folds (100%)** |
| `(2, 2, 0, 0)` | 29 / 55 (52.7%) | `0.00%` | 0 / 55 |
| `(2, 1, 1, 0)` | 29 / 55 (52.7%) | `0.00%` | 0 / 55 |
| `(4, 0, 0, 0)` | 20 / 55 (36.4%) | `0.63%` | 0 / 55 |
| `(1, 1, 1, 1)` (Equal Split) | 14 / 55 (25.5%) | `1.50%` | 0 / 55 |

### 3. Six-Vehicle Anchored Join Speedup ($K = 6, n = 24$, 30 CVRPLIB-X Geometries)

| Join Mode | Stored Triple Unions Reduction | Stored Triple Bins Reduction | Median Join Speedup | Median End-to-End Speedup | Exact Count & Cost Agreement |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Baseline (Unanchored)** | $1.00\times$ | $1.00\times$ | $1.00\times$ | $1.00\times$ | Reference |
| **Two Anchors ($a=2$)** | $2.08\times$ | $1.40\times$ | $1.95\times$ | **`1.93x`** (30/30 faster) | **100% Exact Match** |
| **Three Anchors ($a=3$)** | **`4.53x`** | **`2.46x`** | **`3.69x`** | **`3.59x`** (30/30 faster) | **100% Exact Match** |

---

## Reproducing the Experiments

### 1. Build Official QOBLIB Rust Checker (`check_cvrp`)
```bash
cd check && cargo build --release && cd ..
# Binary is built at: check/target/release/check_cvrp
```

### 2. Verify Zero-Slack Baseline (`TC-Exact` on All 55 Instances)
```bash
clang++ -O3 -std=c++17 src/generate_submission_data.cpp -o build_campaign
./build_campaign instances campaign_results.json
```

### 3. Verify 4-Vehicle Capacity Allocation Profiles & 6-Vehicle Anchored Join
```bash
# Compile C++17 profile and join solvers
clang++ -O3 -std=c++17 experiments/exact.cpp -o /tmp/exact
clang++ -O3 -std=c++17 experiments/allocation_cover.cpp -o /tmp/allocation_cover
clang++ -O3 -std=c++17 experiments/six_vehicle_join.cpp -o /tmp/six_vehicle_join

# Run summary & verification scripts
python3 experiments/summarize_allocation.py
python3 experiments/summarize_anchors.py
python3 experiments/holdout_summary.py
```

See [`experiments/README.md`](experiments/README.md) and [`docs/reproducibility.md`](docs/reproducibility.md) for the complete campaign reproduction commands.

---

## Citation & Contact

If you use these algorithms, capacity allocation profiles, or benchmark results in your research, please cite:

```bibtex
@inproceedings{vuong_ngo2026capacity_allocation_profiles,
  author    = {Vuong, Kha Anh Son and Ngo, Luong Thanh Tra},
  title     = {Exact Capacity Allocation Profiles for Vehicle Routing with Tight Fleets},
  booktitle = {Computational Science and Its Applications -- ICCSA},
  series    = {Lecture Notes in Computer Science (LNCS)},
  year      = {2026},
  note      = {Equal contribution / shared first authorship. Code: \url{https://github.com/vkas0812-sys/vrp-capacity-allocation-profiles}}
}
```

```yaml
authors:
  - family-names: "Vuong"
    given-names: "Kha Anh Son"
    email: "sonvka31@mp.hcmiu.edu.vn"
    affiliation: "School of Industrial Engineering and Management, Ho Chi Minh City International University, Vietnam National University Ho Chi Minh City, Vietnam"
    orcid: "https://orcid.org/0009-0006-3435-7990"
  - family-names: "Ngo"
    given-names: "Luong Thanh Tra"
    email: "TraNLT2@fe.edu.vn"
    affiliation: "FPT University, Greenwich Vietnam, Ho Chi Minh Campus, Vietnam"
    orcid: "https://orcid.org/0009-0003-2268-3498"
```

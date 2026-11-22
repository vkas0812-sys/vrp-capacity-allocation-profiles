# Lean 4 Formal Mathematical Verification (`lean/`)

This directory provides machine-checked formal proofs in **Lean 4** (`leanprover/lean4:v4.36.0`) for all core mathematical propositions, filtering bounds, overload-underload identities, partial-upgrade saturation theorems, anchor-join counting corrections, and dual-repair validity bounds stated in:

> **"Exact Capacity Allocation Profiles for Vehicle Routing with Tight Fleets"**  
> *Kha Anh Son Vuong & Luong Thanh Tra Ngo*

Every theorem in [`VrpCapacityAllocationProofs.lean`](./VrpCapacityAllocationProofs.lean) compiles cleanly using only Lean 4's built-in core kernel (`omega` linear integer arithmetic and `decide` kernel computation) with **zero `sorry` axioms** and **zero external dependencies** (no download of `Mathlib` required — verification finishes in `< 2 seconds`).

---

## 1. Quick Start (For Co-Author & Reviewers)

### Step 1: Install Lean 4 (via `elan`)

On macOS or Linux, run:

```bash
curl https://elan.lean-lang.org/elan-init.sh -sSf | sh -s -- -y --default-toolchain leanprover/lean4:v4.36.0
source "$HOME/.elan/env"
```

Verify your installation:

```bash
lean --version
# Expected: Lean (version 4.36.0, ...)
```

### Step 2: Run the Formal Verification

From the repository root:

```bash
lean lean/VrpCapacityAllocationProofs.lean
```

When all 15 theorems are verified by the Lean 4 kernel, it prints the type signatures of all 15 proven theorems and exits with return code `0` (`0 errors, 0 warnings`).

You can also open [`lean/VrpCapacityAllocationProofs.lean`](./VrpCapacityAllocationProofs.lean) in **VS Code** with the official **Lean 4 extension** (`leanprover.lean4`) to inspect the interactive proof state (`Lean Infoview`) line by line.

---

## 2. Summary of Formally Verified Theorems

| # | Lean 4 Theorem Identifier | Paper Reference ([`paper/main.tex`](../paper/main.tex)) | Formal Mathematical Statement Verified |
| :---: | :--- | :--- | :--- |
| **1** | `admissible_load_lower_bound` | Section 3, Eq. (2) | If $d(S) + d_{\text{rest}} = D$ and $d_{\text{rest}} \le (k-1)C$, then $D - (k-1)C \le d(S)$. |
| **2** | `lower_bound_slack_identity` | Section 3, Eq. (2) | Under fleet slack $\Delta = kC - D$, the lower bound $D - (k-1)C$ equals $C - \Delta$. |
| **3** | `admissible_load_interval` | Section 3, Eq. (2) | Every nonempty route in a feasible $k$-route partition satisfies $L(C) = \max\{1, D - (k-1)C\} \le d(S) \le C$. |
| **4** | `zero_slack_exact_saturation` | Section 3, p. 3 | *"At $\Delta = 0$ every vehicle carries exactly $C$"*: When $D = kC$, $d(S) \le C$ and $d_{\text{rest}} \le (k-1)C$ force $d(S) = C$. |
| **5** | `four_vehicle_plus_one_window` | Section 3, p. 3 | *"Raising the capacity of a tight four-vehicle fleet from $Q$ to $Q+1$ allows loads from $\max\{1, Q-3\}$ to $Q+1$."* |
| **6** | `overload_underload_pointwise` | Section 4, p. 4 | Pointwise decomposition into overload $e(S) = (d(S)-Q)_+$ and underload $u(S) = (Q-d(S))_+$: $d-Q = e-u$ and $|d-Q| = e+u$. |
| **7** | `tight_fleet_half_l1_identity` | Section 4, p. 4 | When $D = 4Q$, total overload equals total underload ($E(P) = U(P)$) and $E(P) = \frac{1}{2}\sum_{S\in P} |d(S) - Q|$. |
| **8** | `budget_load_interval_four_vehicles` | Section 4, p. 4 | *"Any partition achievable with $B$ units has every load in $[Q-B, Q+B]$."* |
| **9** | `sorted_matching_implies_threshold_count` | Section 4 & 5.2, pp. 4–5 | If sorted overloads satisfy $e_i \le a_i$ for all $i \in \{1..4\}$, then for every threshold $t \in \mathbb{Z}$, $\|\{i : e_i \ge t\}\| \le \|\{i : a_i \ge t\}\|$. |
| **10** | `threshold_count_implies_sorted_matching` | Section 4 & 5.2, pp. 4–5 | Converse of Theorem 9: threshold counting inequalities at $t \in \{e_1, e_2, e_3, e_4\}$ imply componentwise dominance $e_i \le a_i$. |
| **11** | `at_most_three_upgraded_routes` | Section 5.3, p. 8 | *"Because $D = 4Q$, four routes simultaneously above $Q$ would exceed total demand. Consequently $z_3 = z_4$ in every case."* |
| **12** | `anchor_multiplicities_exact` | Section 4, p. 4 | For a 6-route partition where anchors occupy $s \in \{1, 2, 3\}$ routes, $m_s = \binom{6-s}{3-s}$ takes exact values $m_1 = 10, m_2 = 4, m_3 = 1$, and $\binom{6}{3} = 20$. |
| **13** | `anchor_count_correction_exact` | Section 4, p. 5 | *"Multiply each oriented join count by $20/m_s$, accumulate by overload tuple, and divide the result by 20. Each partition now contributes exactly one."* |
| **14** | `subset_row_triple_inequality` | Section 5.2, p. 7 | 3-customer subset-row inequality (Jepsen et al.): *"For a triple of customers, at most one selected route can serve at least two members"* ($\sum_{r=1}^6 \lfloor c_r / 2 \rfloor \le 1$ whenever $\sum_{r=1}^6 c_r \le 3$). |
| **15** | `dual_repair_column_feasibility` | Section 5.2, p. 7 | Integer dual repair soundness: subtracting the maximum positive column violation $v_{\max}$ from the fleet-size dual multiplier guarantees valid dual feasibility ($\text{lhs} - v_{\max} \le \text{cost}$). |

---

## 3. Extending the Proofs

To add new theorems or verify additional properties (e.g., general $2h$-vehicle anchor-join formulas or uniform upgrade fee Pareto conditions):
1. Edit [`lean/VrpCapacityAllocationProofs.lean`](./VrpCapacityAllocationProofs.lean).
2. Run `lean lean/VrpCapacityAllocationProofs.lean` to confirm all proofs type-check with zero warnings.

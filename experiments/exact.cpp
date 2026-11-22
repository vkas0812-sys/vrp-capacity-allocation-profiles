#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <limits>
#include <numeric>
#include <stdexcept>
#include <utility>
#include <vector>

namespace {
using Mask = std::uint32_t;
using Clock = std::chrono::steady_clock;
constexpr int Customers = 20;
constexpr int Vehicles = 4;
constexpr Mask Full = (1U << Customers) - 1;
constexpr int Inf = std::numeric_limits<int>::max() / 4;
using Distances = std::array<std::array<int, Customers + 1>, Customers + 1>;

int first(Mask mask) { return __builtin_ctz(mask); }

double elapsed_ms(Clock::time_point start) {
    return std::chrono::duration<double, std::milli>(Clock::now() - start).count();
}

int tour_cost(Mask customers, const Distances& distance) {
    std::vector<int> nodes;
    for (Mask remaining = customers; remaining; remaining &= remaining - 1) {
        nodes.push_back(first(remaining) + 1);
    }
    const int count = static_cast<int>(nodes.size());
    const Mask all = (1U << count) - 1;
    std::vector<int> dp((all + 1) * count, Inf);
    for (int node = 0; node < count; ++node) {
        dp[(1U << node) * count + node] = distance[0][nodes[node]];
    }
    for (Mask visited = 1; visited <= all; ++visited) {
        for (Mask ends = visited; ends; ends &= ends - 1) {
            const int end = first(ends);
            const int current = dp[visited * count + end];
            for (Mask unvisited = all ^ visited; unvisited; unvisited &= unvisited - 1) {
                const int next = first(unvisited);
                const Mask extended = visited | (1U << next);
                int& entry = dp[extended * count + next];
                entry = std::min(entry, current + distance[nodes[end]][nodes[next]]);
            }
        }
    }
    int best = Inf;
    for (int end = 0; end < count; ++end) {
        best = std::min(best, dp[all * count + end] + distance[nodes[end]][0]);
    }
    return best;
}

struct Result {
    std::vector<int> costs = std::vector<int>(Full + 1, Inf);
    std::array<Mask, Vehicles> best_masks{};
    std::uint64_t partitions = 0;
    std::uint64_t best_count = 0;
    int best = Inf;
    int second = Inf;
    int candidates = 0;
    double pricing_ms = 0;
    double cover_ms = 0;
};

struct Split {
    Mask route = 0;
    std::uint64_t count = 0;
    std::uint64_t best_count = 0;
    int best = Inf;
    int second = Inf;
};

Result solve(int capacity, int min_load, const std::array<int, Customers>& demand,
             const Distances& distances) {
    const auto pricing_start = Clock::now();
    Result result;
    const int total_demand = std::accumulate(demand.begin(), demand.end(), 0);
    const int cover_min_load = std::max(1, total_demand - (Vehicles - 1) * capacity);
    std::array<int, Customers + 1> suffix{};
    for (int i = Customers - 1; i >= 0; --i) {
        suffix[i] = suffix[i + 1] + demand[i];
    }
    std::vector<std::pair<Mask, int>> priced_routes;
    auto enumerate = [&](auto&& self, int index, Mask mask, int load) -> void {
        if (load + suffix[index] < min_load) return;
        if (index == Customers || load == capacity) {
            if (mask) {
                result.costs[mask] = tour_cost(mask, distances);
                priced_routes.emplace_back(mask, load);
                ++result.candidates;
            }
            return;
        }
        if (load + demand[index] <= capacity) {
            self(self, index + 1, mask | (1U << index), load + demand[index]);
        }
        self(self, index + 1, mask, load);
    };
    enumerate(enumerate, 0, 0, 0);
    result.pricing_ms = elapsed_ms(pricing_start);

    const auto cover_start = Clock::now();
    std::array<std::vector<Mask>, Customers> by_first;
    std::vector<int> loads(Full + 1);
    for (const auto& [mask, load] : priced_routes) {
        loads[mask] = load;
        if (load >= cover_min_load) by_first[first(mask)].push_back(mask);
    }
    // Each next route includes the first uncovered customer. Cache the exact
    // count and best two distinct costs for splitting each two-route remainder.
    std::vector<int> split_index(Full + 1, -1);
    std::vector<Split> cached_splits;
    auto split = [&](Mask remaining) -> const Split& {
        int& position = split_index[remaining];
        if (position != -1) return cached_splits[position];
        position = static_cast<int>(cached_splits.size());
        Split& entry = cached_splits.emplace_back();
        auto consider = [&](Mask route) {
            const int left = result.costs[route];
            const int right = result.costs[remaining ^ route];
            if (left == Inf || right == Inf) return;
            const int cost = left + right;
            ++entry.count;
            if (cost < entry.best) {
                entry.second = entry.best;
                entry.best = cost;
                entry.best_count = 1;
                entry.route = route;
            } else if (cost == entry.best) {
                ++entry.best_count;
            } else {
                entry.second = std::min(entry.second, cost);
            }
        };
        const auto& bucket = by_first[first(remaining)];
        if ((1U << (__builtin_popcount(remaining) - 1)) < bucket.size()) {
            const Mask anchor = 1U << first(remaining);
            const Mask rest = remaining ^ anchor;
            for (Mask tail = rest;; tail = (tail - 1) & rest) {
                consider(anchor | tail);
                if (!tail) break;
            }
        } else {
            for (Mask route : bucket) {
                if ((route & remaining) == route) consider(route);
            }
        }
        return entry;
    };
    for (Mask route1 : by_first[0]) {
        const Mask after_first = Full ^ route1;
        if (!after_first) continue;
        for (Mask route2 : by_first[first(after_first)]) {
            if ((route2 & after_first) != route2) continue;
            if (total_demand - loads[route1] - loads[route2] > 2 * capacity) continue;
            const Mask remaining = after_first ^ route2;
            if (!remaining) continue;
            const Split& last = split(remaining);
            if (!last.count) continue;
            const int first_cost = result.costs[route1] + result.costs[route2];
            const int cost = first_cost + last.best;
            result.partitions += last.count;
            if (cost < result.best) {
                result.second = result.best;
                result.best = cost;
                result.best_count = last.best_count;
                result.best_masks = {route1, route2, last.route, remaining ^ last.route};
            } else if (cost == result.best) {
                result.best_count += last.best_count;
            } else {
                result.second = std::min(result.second, cost);
            }
            if (last.second != Inf) {
                result.second = std::min(result.second, first_cost + last.second);
            }
        }
    }
    result.cover_ms = elapsed_ms(cover_start);
    return result;
}
}  // namespace

int main() {
    int capacity, min_load, repeats, export_costs;
    if (!(std::cin >> capacity >> min_load >> repeats >> export_costs) ||
        capacity < 1 || min_load < 1 || min_load > capacity || repeats < 1) {
        throw std::runtime_error("Invalid solver settings");
    }
    std::array<int, Customers> demand{};
    for (int& quantity : demand) {
        if (!(std::cin >> quantity) || quantity <= 0) throw std::runtime_error("Invalid demand");
    }
    Distances distances{};
    for (auto& row : distances) {
        for (int& distance : row) {
            if (!(std::cin >> distance) || distance < 0) {
                throw std::runtime_error("Invalid distance matrix");
            }
        }
    }
    std::vector<double> pricing_times, cover_times;
    Result result;
    for (int i = 0; i < repeats; ++i) {
        result = solve(capacity, min_load, demand, distances);
        pricing_times.push_back(result.pricing_ms);
        cover_times.push_back(result.cover_ms);
    }
    std::cout << result.candidates << ' ' << result.partitions << ' ' << result.best_count
              << ' ' << (result.best == Inf ? -1 : result.best)
              << ' ' << (result.second == Inf ? -1 : result.second) << '\n';
    for (Mask route : result.best_masks) std::cout << route << ' ';
    std::cout << '\n';
    for (int i = 0; i < repeats; ++i) {
        std::cout << pricing_times[i] << ' ' << cover_times[i] << '\n';
    }
    if (export_costs) {
        for (Mask mask = 1; mask <= Full; ++mask) {
            if (result.costs[mask] != Inf) std::cout << mask << ' ' << result.costs[mask] << '\n';
        }
    }
}

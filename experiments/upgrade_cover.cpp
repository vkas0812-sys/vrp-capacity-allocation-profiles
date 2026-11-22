// Enumerate four-route partitions once and retain the optimum by upgrades used.
#include <algorithm>
#include <array>
#include <chrono>
#include <string>
#include <unordered_map>
#include <cstdint>
#include <iostream>
#include <limits>
#include <vector>

struct Route {
    int mask, cost, upgraded;
};

struct Split {
    std::uint64_t count = 0;
    int cost = std::numeric_limits<int>::max();
    int route = 0;
};

int main(int argc, char** argv) {
    std::string mode = argc == 2 ? argv[1] : "direct";
    if (argc > 2 || (mode != "direct" && mode != "split" && mode != "cache")) return 1;
    int n, count;
    if (!(std::cin >> n >> count) || n != 20 || count < 1) return 1;
    const int full = (1 << n) - 1;
    std::vector<std::vector<Route>> buckets(n);
    std::vector<int> costs(full + 1, -1), upgrades(full + 1);
    for (int i = 0; i < count; ++i) {
        Route r;
        if (!(std::cin >> r.mask >> r.cost >> r.upgraded) || r.mask <= 0 ||
            r.mask > full || r.cost < 0 || (r.upgraded != 0 && r.upgraded != 1) ||
            costs[r.mask] != -1) return 1;
        buckets[__builtin_ctz(r.mask)].push_back(r);
        costs[r.mask] = r.cost;
        upgrades[r.mask] = r.upgraded;
    }
    std::array<std::uint64_t,5> partitions{};
    std::array<int,5> optimum;
    optimum.fill(std::numeric_limits<int>::max());
    std::array<int,4> route{};
    std::array<std::array<int,4>,5> witnesses{};
    using Profile = std::array<Split,3>;
    const auto start = std::chrono::steady_clock::now();
    std::unordered_map<int,Profile> cache;
    auto two_routes = [&](int left) {
        Profile profile{};
        const int anchor = left & -left;
        const int rest = left ^ anchor;
        auto consider = [&](int first) {
            const int second = left ^ first;
            if (costs[first] < 0 || costs[second] < 0) return;
            auto& bin = profile[upgrades[first] + upgrades[second]];
            ++bin.count;
            const int value = costs[first] + costs[second];
            if (value < bin.cost) {
                bin.cost = value;
                bin.route = first;
            }
        };
        const auto& candidates = buckets[__builtin_ctz(left)];
        if ((1U << __builtin_popcount(rest)) < candidates.size()) {
            for (int sub = rest;; sub = (sub - 1) & rest) {
                consider(anchor | sub);
                if (!sub) break;
            }
        } else {
            for (const auto& r : candidates)
                if ((r.mask & left) == r.mask) consider(r.mask);
        }
        return profile;
    };
    auto visit = [&](auto&& self, int left, int used, int total, int depth) -> void {
        if (!left) return;
        if (depth == 2 && mode != "direct") {
            Profile local{};
            const Profile* profile;
            if (mode == "cache") {
                auto [it, fresh] = cache.try_emplace(left);
                if (fresh) it->second = two_routes(left);
                profile = &it->second;
            } else {
                local = two_routes(left);
                profile = &local;
            }
            for (int extra = 0; extra <= 2; ++extra) {
                const auto& bin = (*profile)[extra];
                if (bin.count == 0) continue;
                const int b = used + extra;
                partitions[b] += bin.count;
                if (total + bin.cost < optimum[b]) {
                    optimum[b] = total + bin.cost;
                    witnesses[b] = {route[0], route[1], bin.route, left ^ bin.route};
                }
            }
            return;
        }
        if (depth == 3) {
            if (costs[left] < 0) return;
            const int budget = used + upgrades[left], value = total + costs[left];
            ++partitions[budget];
            if (value < optimum[budget]) {
                optimum[budget] = value;
                route[3] = left;
                witnesses[budget] = route;
            }
            return;
        }
        for (const auto& r : buckets[__builtin_ctz(left)]) {
            if ((left & r.mask) != r.mask) continue;
            route[depth] = r.mask;
            self(self, left ^ r.mask, used + r.upgraded, total + r.cost, depth + 1);
        }
    };
    visit(visit, full, 0, 0, 0);
    if (argc == 2)
        std::cerr << std::chrono::duration<double,std::milli>(
            std::chrono::steady_clock::now() - start).count() << '\n';
    for (int b = 0; b <= 4; ++b) {
        std::cout << partitions[b] << ' ' << (partitions[b] ? optimum[b] : -1);
        for (int mask : witnesses[b]) std::cout << ' ' << mask;
        std::cout << '\n';
    }
}

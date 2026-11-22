// Join complementary pairs of routes and classify covers by their four overloads.
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <map>
#include <vector>

struct Route { int mask, cost, excess; };
struct Pair { int low, high, cost, first; std::uint64_t ways; };
struct Cover { int cost; std::array<int,4> masks; std::uint64_t ways; };

int main() {
    int n, budget, size;
    if (!(std::cin >> n >> budget >> size) || n != 20 || budget != 4 || size < 1) return 1;
    const int full = (1 << n) - 1;
    std::vector<Route> routes(size);
    for (auto& r : routes)
        if (!(std::cin >> r.mask >> r.cost >> r.excess) || r.mask <= 0 || r.mask > full ||
            r.cost < 0 || r.excess < 0 || r.excess > budget) return 1;

    std::vector<std::vector<Pair>> pairs(full+1);
    for (int j=0; j<size; ++j) {
        const auto& a = routes[j];
        for (int i=0; i<j; ++i) {
            const auto& b = routes[i];
            if ((a.mask & b.mask) || a.excess+b.excess > budget) continue;
            auto& entries = pairs[a.mask | b.mask];
            const int lo = std::min(a.excess,b.excess);
            const int hi = std::max(a.excess,b.excess);
            auto it = std::find_if(entries.begin(),entries.end(),[&](const Pair& p){
                return p.low==lo && p.high==hi;
            });
            if (it == entries.end()) {
                entries.push_back({lo,hi,a.cost+b.cost,a.mask,1});
            } else {
                ++it->ways;
                if (a.cost+b.cost < it->cost) { it->cost=a.cost+b.cost; it->first=a.mask; }
            }
        }
    }
    std::map<std::array<int,4>,Cover> profiles;
    // Customer zero fixes the orientation of each 2+2 division.
    for (int left=1; left<full; left+=2) {
        const int right = full ^ left;
        for (const auto& a : pairs[left]) for (const auto& b : pairs[right]) {
            if (a.low+a.high+b.low+b.high > budget) continue;
            std::array<int,4> key{a.low,a.high,b.low,b.high};
            std::sort(key.begin(),key.end());
            auto& entry = profiles[key];
            if (!entry.ways || a.cost+b.cost < entry.cost) {
                entry.cost=a.cost+b.cost;
                entry.masks={a.first,left^a.first,b.first,right^b.first};
            }
            entry.ways+=a.ways*b.ways;
        }
    }
    for (const auto& [key,entry] : profiles) {
        if (entry.ways%3 != 0) return 2;
        for (int e : key) std::cout << e << ' ';
        std::cout << entry.ways/3 << ' ' << entry.cost;
        for (int m : entry.masks) std::cout << ' ' << m;
        std::cout << '\n';
    }
}

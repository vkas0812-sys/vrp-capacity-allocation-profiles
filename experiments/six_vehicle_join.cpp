// Six-route overload profiles via two complementary groups of three routes.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <map>
#include <string>
#include <vector>

using Mask = unsigned;
struct Route { Mask mask; int cost, load, code; };
struct Bin {
    std::uint64_t count;
    std::array<Mask,3> routes;
    int cost, code, next, spent, deficit;
};

struct Groups {
    std::vector<int> head;
    std::vector<Mask> unions;
    std::vector<Bin> bins;
    explicit Groups(size_t size): head(size,-1) {}
    void add(Mask mask,int code,int spent,int deficit,int cost,std::uint64_t count,
             std::array<Mask,3> routes) {
        if (head[mask]<0) unions.push_back(mask);
        for (int i=head[mask];i>=0;i=bins[i].next) {
            auto& bin=bins[i];
            if (bin.code!=code) continue;
            bin.count+=count;
            if (cost<bin.cost) { bin.cost=cost; bin.routes=routes; }
            return;
        }
        const int next=head[mask];
        head[mask]=static_cast<int>(bins.size());
        bins.push_back({count,routes,cost,code,next,spent,deficit});
    }
};

struct Solution {
    std::uint64_t count=0;
    int cost=0;
    std::array<Mask,6> routes{};
};

int main(int argc,char** argv) {
    // The baseline groups every complementary triple; anchored modes require all
    // selected customers to occur together on one side of the 3+3 join.
    int anchor_count=0;
    if (argc>1) {
        const std::string mode=argv[1];
        if (mode=="two") anchor_count=2;
        else if (mode=="three") anchor_count=3;
        else if (mode!="baseline") return 1;
    }
    if (argc>2) return 1;
    const Mask anchors=(1u<<anchor_count)-1;
    constexpr int anchor_unit=1<<14; // Above the four base-eight overload digits.
    int n,q,m;
    if (!(std::cin>>n>>q>>m) || n!=24 || q!=100 || m<1) return 1;
    const Mask full=(1u<<n)-1;
    std::vector<Route> routes(m);
    for (auto& r:routes) {
        if (!(std::cin>>r.mask>>r.cost>>r.load) || !r.mask || r.mask>full ||
            r.load<q-4 || r.load>q+4 || r.cost<0) return 1;
        const int e=std::max(r.load-q,0);
        r.code=(e ? 1<<(3*(e-1)) : 0) + ((r.mask&anchors) ? anchor_unit : 0);
    }
    auto start=std::chrono::steady_clock::now();
    std::sort(routes.begin(),routes.end(),[](const Route& a,const Route& b){
        return __builtin_ctz(a.mask)<__builtin_ctz(b.mask);
    });
    std::array<std::vector<Route>,8> buckets;
    for (const auto& r:routes) buckets[r.mask&anchors].push_back(r);
    const Mask triple_full=anchors ? ((full>>anchor_count)<<1)|1u : full;
    Groups triples(triple_full+1);
    {
        Groups pairs(full+1);
        for (int j=0;j<m;++j) {
            const auto& b=routes[j];
            for (int i=0;i<j;++i) {
                const auto& a=routes[i];
                if (a.mask & b.mask) continue;
                const int spent=std::max(0,a.load-q)+std::max(0,b.load-q);
                const int deficit=spent+2*q-a.load-b.load;
                if (spent<=4 && deficit<=4)
                    pairs.add(a.mask|b.mask,a.code+b.code,spent,deficit,a.cost+b.cost,1,
                              {a.mask,b.mask,0});
            }
        }
        // Exactly one route in a triple contains its smallest customer.
        for (Mask mask:pairs.unions) {
            const int anchor=__builtin_ctz(mask);
            auto extend = [&](const std::vector<Route>& candidates) {
              for (const auto& r:candidates) {
                if (__builtin_ctz(r.mask)>=anchor) break;
                if (mask&r.mask) continue;
                const int e=std::max(0,r.load-q), d=std::max(0,q-r.load);
                for (int i=pairs.head[mask];i>=0;i=pairs.bins[i].next) {
                    const auto& p=pairs.bins[i];
                    if (p.spent+e>4 || p.deficit+d>4) continue;
                    const Mask united=mask|r.mask;
                    const Mask index=anchors ? ((united>>anchor_count)<<1)|(united&1u) : united;
                    triples.add(index,p.code+r.code,p.spent+e,p.deficit+d,p.cost+r.cost,
                                p.count,{p.routes[0],p.routes[1],r.mask});
                }
              }
            };
            const Mask present=mask&anchors;
            extend(buckets[anchors ^ present]);
            if (anchors && !present) extend(buckets[0]);
        }
    }
    std::map<int,Solution> solutions;
    for (Mask mask:triples.unions) {
        if (!(mask&1)) continue;
        for (int i=triples.head[mask];i>=0;i=triples.bins[i].next)
            for (int j=triples.head[triple_full^mask];j>=0;j=triples.bins[j].next) {
                const auto& a=triples.bins[i]; const auto& b=triples.bins[j];
                if (a.spent+b.spent>4) continue;
                const int code=a.code+b.code;
                auto& s=solutions[code%anchor_unit];
                const int touched=code/anchor_unit;
                // For s touched routes, C(6-s,3-s) orientations keep all
                // anchors on the left: 10, 4, 1 for s=1,2,3 respectively.
                const int scale=!anchors ? 1 : (touched==1 ? 2 : (touched==2 ? 5 : 20));
                if (!s.count || a.cost+b.cost<s.cost) {
                    s.cost=a.cost+b.cost;
                    std::copy(a.routes.begin(),a.routes.end(),s.routes.begin());
                    std::copy(b.routes.begin(),b.routes.end(),s.routes.begin()+3);
                }
                s.count+=a.count*b.count*scale;
            }
    }
    for (const auto& [code,s]:solutions) {
        const int divisor=anchors ? 20 : 10;
        if (s.count%divisor) return 2;
        std::cout<<code<<' '<<s.count/divisor<<' '<<s.cost;
        for (Mask r:s.routes) std::cout<<' '<<r;
        std::cout<<'\n';
    }
    if (argc>1) std::cerr<<triples.unions.size()<<' '<<triples.bins.size()<<' ';
    std::cerr<<std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count()<<'\n';
}

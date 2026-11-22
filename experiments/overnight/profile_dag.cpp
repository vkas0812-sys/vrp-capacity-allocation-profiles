// Exact anchored subset DAG for a tight fleet. Columns are already priced.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>
using Mask=uint32_t;
using Count=unsigned __int128;
using Clock=std::chrono::steady_clock;
double secs(Clock::time_point t){return std::chrono::duration<double>(Clock::now()-t).count();}
std::string decimal(Count x){std::string s; do {s.push_back(char('0'+x%10));x/=10;}while(x);std::reverse(s.begin(),s.end());return s;}
struct Route {Mask mask; int load,excess; uint32_t code; std::vector<int> costs;};
struct Edge {int route,child;};
struct Label {uint32_t code; int spent,cost; Count count;};
struct State {std::vector<Edge> edges; std::vector<Label> labels;};
struct Index {
    std::string mode; std::vector<int> dense; std::unordered_map<Mask,int> hash;
    std::vector<uint64_t> bits; std::vector<int> prefix;
    Index(std::string m,int n,int k,int q,int budget,const std::vector<int>& d):mode(m){
        const size_t size=size_t(1)<<n;
        if(m=="hash") return;
        if(m=="dense"){
            if(size*sizeof(int)>800ULL*1024*1024)throw std::length_error("dense_index_limit");
            dense.assign(size,-1);return;
        }
        if(m!="rank")throw std::runtime_error("unknown_index");
        // Rank only masks whose aggregate load can belong to a complete set of routes.
        int low=n/2;
        std::vector<int> a(1<<low),b(1<<(n-low));
        for(unsigned i=1;i<a.size();++i)a[i]=a[i&(i-1)]+d[__builtin_ctz(i)];
        for(unsigned i=1;i<b.size();++i)b[i]=b[i&(i-1)]+d[low+__builtin_ctz(i)];
        bits.assign((size+63)/64,0);
        for(unsigned hi=0;hi<b.size();++hi)for(unsigned lo=0;lo<a.size();++lo){
            int load=a[lo]+b[hi],t=(load+q/2)/q;
            if(t<=k && std::abs(load-t*q)<=budget){
                Mask x=(hi<<low)|lo;bits[x>>6]|=uint64_t(1)<<(x&63);
            }
        }
        prefix.resize(bits.size()+1);
        for(size_t i=0;i<bits.size();++i)prefix[i+1]=prefix[i]+__builtin_popcountll(bits[i]);
        dense.assign(prefix.back(),-1);
    }
    unsigned slot(Mask x)const{
        if(mode=="dense")return x;
        uint64_t bit=uint64_t(1)<<(x&63);
        if(!(bits[x>>6]&bit))throw std::runtime_error("invalid_rank");
        return prefix[x>>6]+__builtin_popcountll(bits[x>>6]&(bit-1));
    }
    int get(Mask x)const{
        if(mode!="hash")return dense[slot(x)];
        auto p=hash.find(x);return p==hash.end()?-1:p->second;
    }
    void set(Mask x,int v){if(mode=="hash")hash.emplace(x,v);else dense[slot(x)]=v;}
};
int main(int argc,char** argv){try{
    if(argc!=2)return 1;
    int n,k,q,B,m,scenarios;
    if(!(std::cin>>n>>k>>q>>B>>m>>scenarios)||n<4||n>28||k<2||k>8||B<1||B>8||2*B>=q||m<1||scenarios<1)return 1;
    std::vector<int>d(n);int total=0;for(auto& x:d){std::cin>>x;total+=x;}if(total!=k*q)return 1;
    std::vector<Route> routes(m);std::vector<std::vector<int>> bucket(n);
    std::unordered_map<Mask,int> lookup;
    for(int i=0;i<m;++i){auto& r=routes[i];std::cin>>r.mask>>r.load;
        if(!r.mask||r.mask>=(1u<<n)||std::abs(r.load-q)>B||lookup.count(r.mask))return 1;
        r.excess=std::max(0,r.load-q);r.code=r.excess?1u<<(4*(r.excess-1)):0;
        r.costs.resize(scenarios);for(int& v:r.costs)if(!(std::cin>>v)||v<0)return 1;
        bucket[__builtin_ctz(r.mask)].push_back(i);lookup[r.mask]=i;
    }
    auto start=Clock::now();Index index(argv[1],n,k,q,B,d);
    std::vector<State> states(1);index.set(0,0);size_t edge_count=0;
    auto build=[&](auto&& self,Mask left,int load,int t)->int{
        int old=index.get(left);if(old!=-1)return old;
        std::vector<Edge> edges;
        if(t==1){
            auto it=lookup.find(left);if(it!=lookup.end())edges.push_back({it->second,0});
        }else{
            for(int id:bucket[__builtin_ctz(left)]){const auto& r=routes[id];
                if((left&r.mask)!=r.mask||left==r.mask)continue;
                int remain=load-r.load;
                if(std::abs(remain-(t-1)*q)>B)continue;
                int child=self(self,left^r.mask,remain,t-1);
                if(!states[child].edges.empty())edges.push_back({id,child});
            }
        }
        edge_count+=edges.size();
        if(states.size()>=1200000||edge_count>6000000)throw std::length_error("dag_state_or_edge_limit");
        int id=states.size();states.push_back({std::move(edges),{}});index.set(left,id);return id;
    };
    int root=build(build,(1u<<n)-1,total,k);double build_s=secs(start);
    for(int s=0;s<scenarios;++s){
        auto t=Clock::now();size_t labels=1;states[0].labels={{0,0,0,1}};
        for(size_t j=1;j<states.size();++j){
            auto& dst=states[j].labels;dst.clear();
            for(const auto& edge:states[j].edges){const auto& r=routes[edge.route];
                for(const auto& l:states[edge.child].labels){
                    int spent=l.spent+r.excess;if(spent>B)continue;
                    uint32_t key=l.code+r.code;int cost=l.cost+r.costs[s];
                    auto it=std::find_if(dst.begin(),dst.end(),[key](const Label& x){return x.code==key;});
                    if(it==dst.end())dst.push_back({key,spent,cost,l.count});
                    else {it->count+=l.count;it->cost=std::min(it->cost,cost);}
                }
            }
            labels+=dst.size();if(labels>9000000)throw std::length_error("label_limit");
        }
        std::cout<<"T "<<s<<' '<<build_s<<' '<<secs(t)<<' '<<states.size()<<' '<<edge_count<<' '<<labels<<'\n';
        for(const auto& l:states[root].labels)std::cout<<"L "<<s<<' '<<l.code<<' '<<decimal(l.count)<<' '<<l.cost<<'\n';
    }
    return 0;
}catch(const std::length_error& e){std::cerr<<e.what();return 3;}
catch(const std::bad_alloc&){std::cerr<<"memory_limit";return 3;}
catch(const std::exception& e){std::cerr<<e.what();return 1;}}

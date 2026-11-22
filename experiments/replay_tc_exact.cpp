#define main tc_reference_main
#include "tc-qoblib_routing_experiments.cpp"
#undef main
int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "Usage: replay_tc_exact INSTANCE_DIRECTORY\n";
        return 2;
    }
    std::vector<std::string> paths;
    for (const auto& entry : fs::directory_iterator(argv[1])) {
        if (entry.path().extension() == ".vrp") paths.push_back(entry.path().string());
    }
    std::sort(paths.begin(), paths.end());
    std::cout << "instance,tight_subsets,partitions,optimum,second_distinct_cost,exact_ms\n";
    for (const auto& file : paths) {
        auto instance = read_vrp(file);
        auto result = run_tight_subspace_and_sqa(instance);
        std::cout << instance.name << ',' << result.num_valid_subsets << ','
                  << result.num_feasible_partitions << ',' << result.exact_optimal_cost << ','
                  << result.second_best_cost << ',' << result.exact_time_ms << '\n';
    }
}

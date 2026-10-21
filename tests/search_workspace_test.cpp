#include "../artifacts/search_optimization/fixtures.hpp"
#include <future>
#include <type_traits>

namespace {
void require(bool ok,const std::string& message) {
    if(!ok) throw std::runtime_error(message);
}
struct Input {size_t fixture;cv::Mat mask;float threshold;std::string label;};
}
int main() {
    try {
        static_assert(!std::is_copy_constructible<line2Dup::MatchWorkspace>::value,"workspace not copyable");
        cv::setNumThreads(1);omp_set_dynamic(0);omp_set_num_threads(1);
        const auto fixtures=search_experiment::loadFixtures();
        std::vector<Input> inputs;
        for(size_t i=0;i<fixtures.size();++i) inputs.push_back({i,{},fixtures[i].threshold,fixtures[i].name});
        cv::Mat zero(fixtures[0].image.size(),CV_8UC1,cv::Scalar(0));
        cv::Mat full(zero.size(),CV_8UC1,cv::Scalar(255));
        cv::Mat partial=zero.clone();partial(cv::Rect(100,100,400,300)).setTo(255);
        inputs.push_back({0,zero,75,"zero mask after positives"});
        inputs.push_back({0,full,75,"full mask"});
        inputs.push_back({0,partial,75,"partial mask"});
        inputs.push_back({0,{},101,"no candidates above 100"});
        inputs.push_back({8,{},90,"case1 color/size/Detector switch"});
        inputs.push_back({0,{},75,"restore LED gray"});
        std::vector<search_experiment::Keys> expected;
        std::vector<size_t> counts;
        for(const auto& input:inputs) {
            const auto& f=fixtures[input.fixture];
            const auto found=f.reference->match(f.image,input.threshold,{f.class_id},input.mask);
            expected.push_back(search_experiment::keys(found));counts.push_back(found.size());
        }
        for(size_t i=0;i<9;++i) require(counts[i]>0,"Fixture must contain a positive V4 match");
        require(counts[9]==0 && counts[12]==0,"Negative fixtures must produce no candidates");
        std::array<line2Dup::MatchWorkspace,8> workspaces;
        size_t comparisons=0,strictDifferences=0;
        // Reuse the same workspace while growing and shrinking worker counts.
        for(int threads : {1,4,2,4}) {
            omp_set_num_threads(threads);
            for(unsigned bits=0;bits<8;++bits) for(size_t i=0;i<inputs.size();++i) {
                const auto& input=inputs[i];const auto& f=fixtures[input.fixture];
                line2Dup::MatchTimings timing;
                const auto found=f.detector->match(f.image,input.threshold,workspaces[bits],
                    search_experiment::options(bits),&timing,{f.class_id},input.mask);
                const auto actual=search_experiment::keys(found);
                require(actual.semantic==expected[i].semantic,"Semantic mismatch flags="+std::to_string(bits)+" "+input.label);
                require(found.size()==counts[i],"Candidate count mismatch "+input.label);
                if(actual.strict!=expected[i].strict) ++strictDifferences;
                require(std::isfinite(timing.search_ms)&&timing.search_ms>=0,"Invalid search timing");
                require(timing.total_ms+1e-9>=timing.preprocess_ms+timing.search_ms,"Overlapping phase timers");
                ++comparisons;
            }
        }
        // Moved workspaces must retain independent ownership of search scratch.
        auto moved=std::move(workspaces[7]);
        const auto& f=fixtures[0];
        require(search_experiment::keys(f.detector->match(f.image,75,moved,
            search_experiment::options(7),nullptr,{f.class_id})).semantic==expected[0].semantic,"Moved workspace mismatch");
        auto worker=[&](size_t which) {
            omp_set_num_threads(1);
            line2Dup::MatchWorkspace workspace;
            for(int n=0;n<3;++n) {
                const auto& fixture=fixtures[which];
                const auto found=fixture.detector->match(fixture.image,fixture.threshold,workspace,
                    search_experiment::options(7),nullptr,{fixture.class_id});
                require(search_experiment::keys(found).semantic==expected[which].semantic,"Concurrent independent workspace mismatch");
            }
        };
        auto a=std::async(std::launch::async,worker,size_t(0));
        auto b=std::async(std::launch::async,worker,size_t(1));a.get();b.get();
        std::cout << "PASS " << comparisons << " V4 equivalence calls; 8 flag combinations, 9 positive fixtures, masks, empty candidates, worker resize, Detector/size/channel changes, move and two concurrent workers; strict_set_differences=" << strictDifferences << '\n';
        return 0;
    } catch(const std::exception& e) {std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}
}

#include "../line2Dup.cpp"
#include "../artifacts/search_optimization/fixtures.hpp"
#include <future>
#include <random>

namespace {
void require(bool ok, const std::string& message) {
    if (!ok) throw std::runtime_error(message);
}
std::size_t prep_cases = 0;

void checkPreparation() {
#if defined(MIPP_SSE)
    // Independent scalar LM addressing. Extra elements make all legacy
    // wrapped-row reads in these deliberately unusual templates readable.
    std::mt19937 rng(1423);
    for (int T : {1, 3, 4, 8}) {
        const int W = 96, H = 80;
        std::vector<cv::Mat> memories(8);
        for (auto& memory : memories) {
            memory.create(T*T, W*H + 32, CV_8UC1);
            for (int row = 0; row < memory.rows; ++row)
                for (int col = 0; col < memory.cols; ++col) {
                    const unsigned char values[] = {0,3,4};
                    memory.ptr<unsigned char>(row)[col] = values[rng()%3];
                }
        }
        for (int count : {1, 46, 63, 64, 111, 236}) {
            line2Dup::Template templ;
            for (int i = 0; i < count; ++i)
                templ.features.emplace_back(int(rng()%(14*T))-3*T,
                                            int(rng()%(14*T))-3*T, rng()%8);
            for (const cv::Point center : {cv::Point(20*T+1,20*T+2),cv::Point(8*T,8*T),
                                          cv::Point(4*T+1,5*T+2),cv::Point(-T,-2*T)}) {
                // Original coordinate offset uses C++ truncation towards zero.
                const int ox = (center.x/T-8)*T, oy = (center.y/T-8)*T;
                unsigned bestRaw=0; float bestScore=0; int bestY=-1,bestX=-1;
                for (int row=0;row<16;++row) for(int col=0;col<16;++col) {
                    unsigned sum=0;
                    for (const auto& f:templ.features) {
                        const int x=f.x+ox, y=f.y+oy;
                        if(x<0||y<0||x>=W*T||y>=H*T) continue;
                        const int grid=(y%T)*T+x%T;
                        const int index=(y/T)*W+x/T+row*W+col;
                        sum+=memories[f.label].ptr<unsigned char>(grid)[index];
                    }
                    const float score=(int(sum)*100.f)/(4*count);
                    if(score>bestScore) {bestRaw=sum;bestScore=score;bestY=row;bestX=col;}
                }
                std::vector<const unsigned char*> streams;
                const auto got=line2Dup::similarityLocalMaximum(memories,templ,{W*T,H*T},T,center,streams);
                require(got.raw==bestRaw&&got.score==bestScore&&got.row==bestY&&got.col==bestX,
                        "adjusted feature preparation mismatch");
                ++prep_cases;
            }
        }
    }
#endif
}
}

int main() {
    try {
        checkPreparation();
        cv::setNumThreads(1); omp_set_dynamic(0); omp_set_num_threads(1);
        const auto fixtures=search_experiment::loadFixtures();
        struct Input {std::size_t fixture;cv::Mat mask;float threshold;};
        std::vector<Input> inputs;
        for(std::size_t i=0;i<fixtures.size();++i) inputs.push_back({i,{},fixtures[i].threshold});
        cv::Mat zero(fixtures[0].image.size(),CV_8UC1,cv::Scalar(0));
        cv::Mat partial=zero.clone();partial(cv::Rect(100,100,400,300)).setTo(255);
        inputs.push_back({0,zero,75}); inputs.push_back({0,partial,75});
        inputs.push_back({0,{},101}); inputs.push_back({8,{},90}); inputs.push_back({0,{},75});
        std::vector<search_experiment::Keys> expected;
        std::vector<std::size_t> counts;
        for(const auto& in:inputs) {
            const auto& f=fixtures[in.fixture];
            const auto result=f.reference->match(f.image,in.threshold,{f.class_id},in.mask);
            expected.push_back(search_experiment::keys(result));counts.push_back(result.size());
        }
        std::size_t calls=0,strictDiffs=0;
        line2Dup::MatchWorkspace workspace;
        for(int threads:{1,4,2,4}) {
            omp_set_num_threads(threads);
            for(unsigned bits=0;bits<8;++bits) for(std::size_t i=0;i<inputs.size();++i) {
                const auto& in=inputs[i];const auto& f=fixtures[in.fixture];
                auto options=search_experiment::options(bits);options.fused_local_search=true;
                const auto result=f.detector->match(f.image,in.threshold,workspace,options,nullptr,{f.class_id},in.mask);
                const auto actual=search_experiment::keys(result);
                require(actual.semantic==expected[i].semantic&&result.size()==counts[i],
                        "V4 mismatch flags="+std::to_string(bits)+" image="+f.name);
                strictDiffs+=actual.strict!=expected[i].strict;++calls;
            }
        }
        auto moved=std::move(workspace);
        auto options=search_experiment::options(7);options.fused_local_search=true;
        require(search_experiment::keys(fixtures[0].detector->match(fixtures[0].image,75,moved,
            options,nullptr,{fixtures[0].class_id})).semantic==expected[0].semantic,"moved local streams mismatch");
        for (std::size_t i : {std::size_t(0), std::size_t(8)}) {
            const auto& f=fixtures[i];
            const auto result=f.detector->match(f.image,f.threshold,{f.class_id});
            require(search_experiment::keys(result).semantic==expected[i].semantic &&
                    result.size()==counts[i], "default legacy-signature dispatch mismatch");
            ++calls;
        }
        auto worker=[&](std::size_t i) {
            omp_set_num_threads(1);line2Dup::MatchWorkspace own;
            for(int n=0;n<3;++n) require(search_experiment::keys(fixtures[i].detector->match(
                fixtures[i].image,fixtures[i].threshold,own,options,nullptr,{fixtures[i].class_id})).semantic==expected[i].semantic,
                "concurrent local stream mismatch");
        };
        auto a=std::async(std::launch::async,worker,0),b=std::async(std::launch::async,worker,1);a.get();b.get();
        std::cout<<"PASS local search: "<<prep_cases<<" independent preparation cases, "<<calls
                 <<" V4 calls; masks, float fallback, workspace resize/move and concurrency; strict_differences="<<strictDiffs<<'\n';
        return 0;
    } catch(const std::exception& error) {std::cerr<<"FAIL local search: "<<error.what()<<'\n';return 1;}
}

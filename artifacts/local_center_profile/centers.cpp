// The fixture builder uses the isolated V9 namespace. Suppress its production
// header include so this executable needs no current production matcher object.
#include "source/line2Dup.h"
#define CXXLINEMOD_H
#define line2Dup profiledLine2Dup
#include "fixtures_v9.hpp"
#undef line2Dup
#undef CXXLINEMOD_H

namespace {
struct Census {
    std::uint64_t calls=0,unique=0,max_frequency=0,x_clamped=0,y_clamped=0;
    std::map<std::uint64_t,std::uint64_t> frequency;
    void add(const search_profile::Level& level) {
        calls+=level.local_calls;unique+=level.centers.size();
        x_clamped+=level.x_clamped;y_clamped+=level.y_clamped;
        std::uint64_t reconstructed=0;
        for(const auto& item:level.centers) {
            reconstructed+=item.second;++frequency[item.second];
            max_frequency=std::max(max_frequency,item.second);
        }
        CV_Assert(reconstructed==level.local_calls);
    }
};
void describe(std::ostream& out) {
    out<<"{\"purpose\":\"count-only local-center repetition census\",\n"
       <<"\"snapshot\":\"V9 6b7be69 isolated source, unchanged search semantics\",\n"
       <<"\"center_key\":\"class, template_id, level, x/T, y/T after clamp and before local similarity\",\n"
       <<"\"calls_per_image\":{\"V4_reference\":1,\"instrumented_V9\":1},\n"
       <<"\"validation\":\"exact V4 semantic set and raw count required; strict set recorded\",\n"
       <<"\"cv_threads\":1,\"omp_threads\":4,\"timing\":\"no performance conclusion; map-counter and retained old timer overhead\",\n"
       <<"\"LED\":{\"templates\":900,\"levels\":3,\"steps\":[4,8,8],\"threshold\":75},\n"
       <<"\"case1\":{\"templates\":361,\"levels\":2,\"steps\":[4,8],\"threshold\":90}}\n";
}
}
int main(int argc,char** argv) {
    try {
        std::string output;
        for(int i=1;i<argc;++i) {
            const std::string arg=argv[i];
            if(arg=="--describe") {describe(std::cout);return 0;}
            if(arg!="--output"||i+1==argc) throw std::runtime_error("Use --output DIRECTORY");
            output=argv[++i];
        }
        if(output.empty()) throw std::runtime_error("Need --output DIRECTORY");
        std::ofstream config(output+"/config.json"),validation(output+"/validation.csv"),summary(output+"/centers_by_level.csv"),
                      frequencies(output+"/center_frequency.csv"),templates(output+"/centers_by_template.csv");
        if(!config||!validation||!summary||!frequencies||!templates) throw std::runtime_error("Create a fresh output directory first");
        describe(config);
        validation<<"dataset,image,v4_count,instrumented_count,v4_semantic,instrumented_semantic,semantic_equal,strict_equal,count_equal\n";
        summary<<"dataset,image,level,total_calls,unique_centers,redundant_calls,redundant_pct,max_frequency,duplicate_centers,x_clamped,y_clamped\n";
        frequencies<<"dataset,image,level,frequency,unique_centers,calls\n";
        templates<<"dataset,image,class_id,template_id,level,total_calls,unique_centers,redundant_calls,max_frequency\n";
        summary<<std::setprecision(12);
        cv::setNumThreads(1);omp_set_dynamic(0);omp_set_num_threads(4);
        const auto fixtures=search_experiment::loadFixtures();int failures=0,strictDifferences=0;
        for(const auto& f:fixtures) {
            f.reference->resetWorkspace();
            const auto reference=f.reference->match(f.image,f.threshold,{f.class_id});
            profiledLine2Dup::MatchWorkspace workspace;profiledLine2Dup::MatchTimings timings;
            const auto found=f.detector->match(f.image,f.threshold,workspace,search_experiment::options(7),&timings,{f.class_id});
            const auto a=search_experiment::keys(reference),b=search_experiment::keys(found);
            const bool semantic=a.semantic==b.semantic,strict=a.strict==b.strict,count=reference.size()==found.size();
            validation<<f.dataset<<','<<f.name<<','<<reference.size()<<','<<found.size()<<','<<a.semantic.size()<<','<<b.semantic.size()<<','
                      <<semantic<<','<<strict<<','<<count<<'\n';
            failures+=!semantic||!count;strictDifferences+=!strict;
            if(!semantic||!count) throw std::runtime_error("V4 semantic/count check failed; no census published for "+f.name);
            std::vector<Census> levels(f.detector->pyramidLevels()-1);
            for(const auto& p:timings.profile.templates) for(int level=0;level<p.coarse_level;++level) {
                const auto& raw=p.levels[level];levels[level].add(raw);Census perTemplate;perTemplate.add(raw);
                templates<<f.dataset<<','<<f.name<<','<<p.class_id<<','<<p.template_id<<','<<level<<','<<perTemplate.calls<<','
                         <<perTemplate.unique<<','<<perTemplate.calls-perTemplate.unique<<','<<perTemplate.max_frequency<<'\n';
            }
            for(std::size_t level=0;level<levels.size();++level) {
                const auto& c=levels[level];const auto singleton=c.frequency.count(1)?c.frequency.at(1):0;
                const auto redundant=c.calls-c.unique;const double percent=c.calls?100.*redundant/c.calls:0;
                summary<<f.dataset<<','<<f.name<<','<<level<<','<<c.calls<<','<<c.unique<<','<<redundant<<','<<percent<<','<<c.max_frequency<<','
                       <<c.unique-singleton<<','<<c.x_clamped<<','<<c.y_clamped<<'\n';
                for(const auto& entry:c.frequency)
                    frequencies<<f.dataset<<','<<f.name<<','<<level<<','<<entry.first<<','<<entry.second<<','<<entry.first*entry.second<<'\n';
            }
            validation.flush();summary.flush();frequencies.flush();templates.flush();
            std::cout<<"completed "<<f.dataset<<'/'<<f.name<<" semantic="<<semantic<<" strict="<<strict<<" count="<<count<<std::endl;
        }
        std::ofstream status(output+"/status.json");
        status<<"{\"semantic_or_count_failures\":"<<failures<<",\"strict_set_differences\":"<<strictDifferences<<",\"completed_images\":9}\n";
        return failures?2:0;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}

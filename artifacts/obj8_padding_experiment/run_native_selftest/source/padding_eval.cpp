// Isolated adapter: the public evaluator is included unchanged for its frozen
// dataset/config/meta/raw/box/order/NMS/metric helpers. Its main is never called.
#define main frozen_public_evaluator_entry
#include "../public_evaluation/tless_eval.cpp"
#undef main
#include "padding_plan.hpp"
#include <cstring>
#include <tuple>
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <psapi.h>

namespace pad=obj8_padding;
static void ensure(bool value,const char* reason){if(!value)throw std::runtime_error(reason);}
static bool exact(const Detection& a,const Detection& b) {
    return a.class_id==b.class_id && a.template_id==b.template_id && a.match_x==b.match_x && a.match_y==b.match_y &&
        std::memcmp(&a.score,&b.score,sizeof(float))==0 && a.box.x==b.box.x && a.box.y==b.box.y && a.box.w==b.box.w && a.box.h==b.box.h;
}
static bool exactRows(const std::vector<Detection>& a,const std::vector<Detection>& b) {
    if(a.size()!=b.size())return false;
    for(std::size_t i=0;i<a.size();++i)if(!exact(a[i],b[i]))return false;
    return true;
}
static std::vector<std::string> fields(const std::string& row) {
    std::stringstream line(row);std::string cell;std::vector<std::string> out;
    while(std::getline(line,cell,','))out.push_back(cell);return out;
}
static std::vector<Detection> readRaw(const fs::path& path,const Frame& frame,const std::string& variant,
                                     const std::vector<TemplateMeta>& meta) {
    gzFile file=gzopen(path.string().c_str(),"rb");ensure(file!=nullptr,"Missing reference raw archive");
    std::string contents;char block[65536];int count;
    while((count=gzread(file,block,sizeof block))>0)contents.append(block,std::size_t(count));
    const int closed=gzclose(file);ensure(count>=0 && closed==Z_OK,"Raw gzip CRC/read failed");
    std::stringstream lines(contents);std::string row;std::getline(lines,row);
    ensure(row=="scene,image,variant,class_id,rank,score,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h","Raw schema changed");
    std::vector<Detection> result;
    while(std::getline(lines,row)) {
        const auto cells=fields(row);ensure(cells.size()==16,"Raw CSV width changed");
        ensure(std::stoi(cells[0])==frame.scene && std::stoi(cells[1])==frame.image && cells[2]==variant && std::stoull(cells[4])==result.size(),"Raw frame/variant/rank changed");
        Detection d;d.class_id=cells[3];d.score=std::stof(cells[5]);d.template_id=std::stoi(cells[6]);d.match_x=std::stoi(cells[10]);d.match_y=std::stoi(cells[11]);
        d.box={std::stod(cells[12]),std::stod(cells[13]),std::stod(cells[14]),std::stod(cells[15])};
        const auto& m=findMeta(meta,d.class_id,d.template_id);const auto expected=boxAtMatch(d.match_x,d.match_y,64,m.silhouette,m.tl_x,m.tl_y);
        ensure(std::isfinite(d.score) && d.score>=85 && std::stoi(cells[7])==m.image && std::stof(cells[8])==m.angle && std::stof(cells[9])==m.scale &&
               d.box.x==expected.x && d.box.y==expected.y && d.box.w==expected.w && d.box.h==expected.h,"Raw fields/metadata/box changed");
        if(!result.empty())ensure(!canonicalLess(d,result.back()),"Raw ordering changed");result.push_back(d);
    }return result;
}
static pad::U peakRss() {
    PROCESS_MEMORY_COUNTERS counters{};counters.cb=sizeof(counters);
    ensure(GetProcessMemoryInfo(GetCurrentProcess(),&counters,sizeof(counters))!=0,"Cannot query peak working set");
    return pad::U(counters.PeakWorkingSetSize);
}
static void checkResources(const fs::path& output,const std::chrono::steady_clock::time_point& began,int minutes) {
    ensure(peakRss()<=1610612736ULL,"Process peak RSS exceeded fixed budget");
    ensure(std::chrono::duration<double>(std::chrono::steady_clock::now()-began).count()<=minutes*60.0,"Stage time budget exceeded");
    pad::U bytes=0;
    for(const auto& entry:fs::recursive_directory_iterator(output))if(entry.is_regular_file() && entry.path().filename().string().find("_raw.csv.gz")!=std::string::npos)bytes=pad::add(bytes,entry.file_size());
    ensure(bytes<=536870912ULL,"New raw-output byte budget exceeded");
}
static std::vector<pad::Layer> loadedLayers(const line2Dup::Detector& detector) {
    ensure(detector.pyramidLevels()==2 && detector.getT(0)==4 && detector.getT(1)==8 && detector.numTemplates()==3456 && detector.classIds()==std::vector<std::string>{"tless_object_8"},"Unexpected loaded bank layout");
    std::vector<pad::Layer> result;
    for(const auto& c:detector.classIds())for(int id=0;id<detector.numTemplates(c);++id) {
        const auto& pyramid=detector.getTemplates(c,id);ensure(pyramid.size()==2,"Loaded pyramid incomplete");
        for(std::size_t level=0;level<pyramid.size();++level) {
            const auto& t=pyramid[level];ensure(t.pyramid_level==int(level) && !t.features.empty(),"Loaded template level/feature mismatch");
            pad::Layer row;row.class_id=c;row.template_id=id;row.level=int(level);row.width=t.width;row.height=t.height;
            row.min_x=row.min_y=std::numeric_limits<std::int64_t>::max();row.max_x=row.max_y=std::numeric_limits<std::int64_t>::min();
            for(const auto& f:t.features){ensure(f.label>=0 && f.label<8,"Invalid loaded orientation label");row.min_x=std::min(row.min_x,std::int64_t(f.x));row.min_y=std::min(row.min_y,std::int64_t(f.y));row.max_x=std::max(row.max_x,std::int64_t(f.x));row.max_y=std::max(row.max_y,std::int64_t(f.y));}
            result.push_back(row);
        }
    }return result;
}
static bool feasible(const pad::Layer& row,pad::U width,pad::U height) {
    const pad::U t=row.level==0?4:8,w=width>>row.level,h=height>>row.level;
    if(w%t || h%t)return false;
    if(row.level==0)return w>=pad::U(row.width)+16*t && h>=pad::U(row.height)+16*t;
    return w>=std::max(pad::U(row.width),pad::U(row.max_x)+1) && h>=std::max(pad::U(row.height),pad::U(row.max_y)+1);
}
static void writeGeometry(const std::vector<pad::Layer>& layers,const pad::Plan& plan,const fs::path& output) {
    std::ofstream csv(output/"geometry.csv");csv<<"class_id,template_id,level,T,width,height,min_x,min_y,max_x,max_y,old_width,old_height,new_width,new_height,old_declared_fit,old_complete_fit,new_complete_fit\n";
    int before=0,after=0,historical=0;
    for(const auto& row:layers) {
        const pad::U oldw=848>>row.level,oldh=672>>row.level,neww=plan.width>>row.level,newh=plan.height>>row.level,t=row.level==0?4:8;
        const bool old=feasible(row,848,672),next=feasible(row,plan.width,plan.height);
        const bool declared=row.level==0 ? oldw>=pad::U(row.width)+16*t && oldh>=pad::U(row.height)+16*t : oldw>=pad::U(row.width) && oldh>=pad::U(row.height);
        before+=!old;after+=!next;historical+=!declared;
        csv<<row.class_id<<','<<row.template_id<<','<<row.level<<','<<t<<','<<row.width<<','<<row.height<<','<<row.min_x<<','<<row.min_y<<','<<row.max_x<<','<<row.max_y<<','<<oldw<<','<<oldh<<','<<neww<<','<<newh<<','<<declared<<','<<old<<','<<next<<'\n';
    }
    ensure(historical==630 && before==634 && after==0,"Actual bank geometry differs from frozen static derivation");
}
struct Pipeline {std::vector<Detection> raw,selected;double match_ms=0,total_ms=0;};
static Pipeline call(line2Dup::Detector& detector,const std::vector<TemplateMeta>& meta,const cv::Mat& input,
                     const pad::Plan& plan,line2Dup::MatchWorkspace& workspace,bool fused,const Config& config) {
    const auto begin=std::chrono::steady_clock::now();cv::Mat padded;
    cv::copyMakeBorder(input,padded,int(plan.padding[1]),int(plan.padding[3]),int(plan.padding[0]),int(plan.padding[2]),cv::BORDER_CONSTANT,cv::Scalar(0));
    ensure(padded.cols==int(plan.width) && padded.rows==int(plan.height),"Actual padding dimensions changed");
    line2Dup::MatchOptions options;options.fused_local_search=fused;
    const auto matchBegin=std::chrono::steady_clock::now();const auto matches=detector.match(padded,85.f,workspace,options,nullptr,{"tless_object_8"});const auto matchEnd=std::chrono::steady_clock::now();
    Pipeline result;result.raw=convert(matches,meta,int(plan.padding[0]));result.selected=postprocess(result.raw,config,85);
    const auto end=std::chrono::steady_clock::now();result.match_ms=std::chrono::duration<double,std::milli>(matchEnd-matchBegin).count();result.total_ms=std::chrono::duration<double,std::milli>(end-begin).count();
    return result;
}
struct Totals {Counts all,eligible;int negative_frames=0,negative_with_fp=0,negative_fp=0,old_gt_retained=0,old_tp_identity_retained=0,new_gt=0,lost_gt=0;pad::U raw=0;};
static void append(Totals& total,const Counts& all,const Counts& eligible,bool negative,std::size_t raw,int oldGt,int oldIdentity,int newGt,int lostGt) {
    add(total.all,all);add(total.eligible,eligible);total.raw+=raw;
    total.negative_frames+=negative;total.negative_with_fp+=negative && all.fp>0;total.negative_fp+=negative?all.fp:0;
    total.old_gt_retained+=oldGt;total.old_tp_identity_retained+=oldIdentity;total.new_gt+=newGt;total.lost_gt+=lostGt;
}
static void writeTotals(cv::FileStorage& out,const std::string& name,const Totals& totals) {
    out<<name<<"{";writeCounts(out,"allGT",totals.all);writeCounts(out,"visibility_ge_0_5",totals.eligible);
    out<<"raw_candidates"<<double(totals.raw)<<"negative_frames"<<totals.negative_frames<<"negative_frames_with_fp"<<totals.negative_with_fp<<"negative_fp"<<totals.negative_fp;
    out<<"baseline_gt_retained"<<totals.old_gt_retained<<"baseline_tp_detection_retained"<<totals.old_tp_identity_retained<<"new_gt"<<totals.new_gt<<"lost_baseline_gt"<<totals.lost_gt<<"}";
}
static void quality(const std::string& mode,const cv::FileStorage& verified,line2Dup::Detector& detector,
                    const std::vector<TemplateMeta>& meta,const Config& config,const pad::Plan& autoPlan,const fs::path& output,
                    const std::chrono::steady_clock::time_point& began) {
    const fs::path root=str(verified["dataset_root"]);std::map<std::pair<int,int>,Frame> indexed;
    for(const auto& f:readFrames(root,false,"development",{8}))indexed.emplace(std::make_pair(f.scene,f.image),f);
    std::array<Totals,2> totals;std::map<int,std::array<Totals,2>> scenes;
    std::array<line2Dup::MatchWorkspace,4> workspaces;
    std::ofstream per(output/"per_frame_metrics.csv"),selected(output/"selected_detections.csv"),equality(output/"candidate_equality.csv"),retention(output/"gt_retention.csv");
    per<<"scene,image,arm,raw,tp,fp,fn,gt,eligible_tp,eligible_fp,eligible_fn,eligible_gt,ignored,negative_fp,baseline_gt_retained,baseline_tp_detection_retained,new_gt,lost_baseline_gt\n";
    selected<<"scene,image,arm,rank,class_id,score,template_id,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h,allGT_label,allGT_id,eligible_label,eligibleGT_id\n";selected<<std::setprecision(17);
    equality<<"scene,image,arm,fallback_count,fused_count,exact_fields_and_float32_bits,old_baseline_cache_equal,fallback_match_ms,fused_match_ms,fallback_pipeline_ms,fused_pipeline_ms\n";
    retention<<"scene,image,gt_id,baseline_detected,auto_detected\n";
    fs::create_directories(output/"auto");if(mode=="pilot")fs::create_directories(output/"baseline_fresh");
    pad::Plan baseline;baseline.width=848;baseline.height=672;baseline.padding={{64,64,64,68}};baseline.alignment=16;
    std::size_t frames=0;pad::U matchCalls=0;double decodeMs=0;
    for(const auto& node:verified["frames"]) {
        const auto key=std::make_pair(int(node["scene_id"]),int(node["image_id"]));const auto found=indexed.find(key);ensure(found!=indexed.end(),"Frame outside development");const auto& f=found->second;
        ensure(str(node["rgb"])==f.rgb,"Frame RGB/index mismatch");
        const auto old=readRaw(str(node["fallback_raw"]),f,"fallback",meta),oldFused=readRaw(str(node["fused_raw"]),f,"fused",meta);
        ensure(exactRows(old,oldFused) && old.size()==std::size_t(double(node["raw_count"])),"Frozen baseline candidate mismatch");
        const auto decodeBegin=std::chrono::steady_clock::now();const auto image=cv::imread((root/f.rgb).string(),cv::IMREAD_GRAYSCALE);decodeMs+=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-decodeBegin).count();
        ensure(!image.empty() && image.cols==720 && image.rows==540,"Actual image dimension mismatch");
        if(mode=="pilot") {
            const auto a=call(detector,meta,image,baseline,workspaces[0],false,config),b=call(detector,meta,image,baseline,workspaces[1],true,config);matchCalls+=2;
            writeRaw(output/"baseline_fresh",f,"fallback",a.raw,meta);writeRaw(output/"baseline_fresh",f,"fused",b.raw,meta);
            equality<<f.scene<<','<<f.image<<",baseline,"<<a.raw.size()<<','<<b.raw.size()<<','<<exactRows(a.raw,b.raw)<<','<<(exactRows(a.raw,old) && exactRows(b.raw,oldFused))<<','<<a.match_ms<<','<<b.match_ms<<','<<a.total_ms<<','<<b.total_ms<<'\n';
            ensure(exactRows(a.raw,b.raw) && exactRows(a.raw,old) && exactRows(b.raw,oldFused),"Fresh baseline differs from frozen same-padding output");
        }
        const auto a=call(detector,meta,image,autoPlan,workspaces[2],false,config),b=call(detector,meta,image,autoPlan,workspaces[3],true,config);matchCalls+=2;
        writeRaw(output/"auto",f,"fallback",a.raw,meta);writeRaw(output/"auto",f,"fused",b.raw,meta);
        equality<<f.scene<<','<<f.image<<",auto,"<<a.raw.size()<<','<<b.raw.size()<<','<<exactRows(a.raw,b.raw)<<",-1,"<<a.match_ms<<','<<b.match_ms<<','<<a.total_ms<<','<<b.total_ms<<'\n';
        ensure(exactRows(a.raw,b.raw),"Auto-padding fallback/fused candidate mismatch");
        ensure(a.raw.size()<=1000000 && b.raw.size()<=1000000,"Raw candidate budget exceeded; full archive preserved");
        const auto oldKept=postprocess(old,config,85);const auto oldCounts=evaluate(oldKept,f.gt,.5,false,.5);
        std::set<int> oldGt,newGt;for(std::size_t i=0;i<oldKept.size();++i)if(oldCounts.labels[i]=="TP")oldGt.insert(oldCounts.gt_ids[i]);
        const auto newCounts=evaluate(a.selected,f.gt,.5,false,.5);for(std::size_t i=0;i<a.selected.size();++i)if(newCounts.labels[i]=="TP")newGt.insert(newCounts.gt_ids[i]);
        for(const auto& g:f.gt)retention<<f.scene<<','<<f.image<<','<<g.id<<','<<oldGt.count(g.id)<<','<<newGt.count(g.id)<<'\n';
        for(int arm=0;arm<2;++arm) {
            const auto& raw=arm==0?old:a.raw;const auto& kept=arm==0?oldKept:a.selected;const auto all=evaluate(kept,f.gt,.5,false,.5),eligible=evaluate(kept,f.gt,.5,true,.5);
            int retainedGt=0,retainedIdentity=0,added=0;
            for(std::size_t i=0;i<kept.size();++i)if(all.labels[i]=="TP") {
                if(oldGt.count(all.gt_ids[i]))++retainedGt;else ++added;
                for(std::size_t j=0;j<oldKept.size();++j)if(oldCounts.labels[j]=="TP" && exact(kept[i],oldKept[j])){++retainedIdentity;break;}
            }
            const int lost=int(oldGt.size())-retainedGt;append(totals[arm],all,eligible,f.gt.empty(),raw.size(),retainedGt,retainedIdentity,added,lost);append(scenes[f.scene][arm],all,eligible,f.gt.empty(),raw.size(),retainedGt,retainedIdentity,added,lost);
            const auto name=arm==0?"baseline":"auto";
            per<<f.scene<<','<<f.image<<','<<name<<','<<raw.size()<<','<<all.tp<<','<<all.fp<<','<<all.fn<<','<<all.gt<<','<<eligible.tp<<','<<eligible.fp<<','<<eligible.fn<<','<<eligible.gt<<','<<eligible.ignored<<','<<(f.gt.empty()?all.fp:0)<<','<<retainedGt<<','<<retainedIdentity<<','<<added<<','<<lost<<'\n';
            for(std::size_t i=0;i<kept.size();++i) {const auto& d=kept[i];selected<<f.scene<<','<<f.image<<','<<name<<','<<i<<','<<d.class_id<<','<<d.score<<','<<d.template_id<<','<<d.match_x<<','<<d.match_y<<','<<d.box.x<<','<<d.box.y<<','<<d.box.w<<','<<d.box.h<<','<<all.labels[i]<<','<<all.gt_ids[i]<<','<<eligible.labels[i]<<','<<eligible.gt_ids[i]<<'\n';}
        }
        ++frames;checkResources(output,began,mode=="pilot"?10:60);std::cout<<"PADDING "<<mode<<' '<<frameKey(f)<<" baseline="<<old.size()<<" auto="<<a.raw.size()<<" exact=1\n";
    }
    ensure(frames==std::size_t(mode=="pilot"?8:400) && matchCalls==pad::U(mode=="pilot"?32:800),"Incomplete fixed stage");
    cv::FileStorage summary((output/"comparison_metrics.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
    summary<<"protocol"<<"obj8_full_bank_minimum_padding_development_v1"<<"split"<<"development"<<"stage"<<mode<<"frames"<<int(frames)<<"matcher_calls"<<double(matchCalls)<<"all_fallback_fused_fields_exact"<<1<<"heldout_images_read"<<0;
    summary<<"baseline_size"<<std::vector<int>{848,672}<<"auto_size"<<std::vector<int>{848,800}<<"baseline_padding_ltrb"<<std::vector<int>{64,64,64,68}<<"auto_padding_ltrb"<<std::vector<int>{64,64,64,196};
    writeTotals(summary,"baseline",totals[0]);writeTotals(summary,"auto",totals[1]);summary<<"per_scene"<<"[";
    for(const auto& item:scenes){summary<<"{"<<"scene_id"<<item.first;writeTotals(summary,"baseline",item.second[0]);writeTotals(summary,"auto",item.second[1]);summary<<"}";}summary<<"]";
    summary<<"decode_total_ms"<<decodeMs<<"peak_rss_bytes"<<double(peakRss())<<"quality_call_timing_is_diagnostic_only"<<1<<"paired_performance_benchmark"<<0;
}
static double percentile(std::vector<double> values,double q) {
    ensure(!values.empty(),"Empty timing distribution");std::sort(values.begin(),values.end());
    return values[std::max<std::size_t>(1,std::size_t(std::ceil(q*values.size())))-1];
}
static void timing(const cv::FileStorage& verified,line2Dup::Detector& detector,const std::vector<TemplateMeta>& meta,const Config& config,
                   const pad::Plan& autoPlan,const fs::path& qualityPath,const fs::path& output,const std::chrono::steady_clock::time_point& began) {
    const fs::path root=str(verified["dataset_root"]);std::map<std::pair<int,int>,Frame> indexed;
    for(const auto& f:readFrames(root,false,"development",{8}))indexed.emplace(std::make_pair(f.scene,f.image),f);
    cv::FileStorage qualitySummary((qualityPath/"comparison_metrics.json").string(),cv::FileStorage::READ);
    ensure(qualitySummary.isOpened() && str(qualitySummary["stage"])=="development" && int(qualitySummary["frames"])==400 && int(qualitySummary["all_fallback_fused_fields_exact"])==1,"Timing needs complete exact full-development quality reference");
    pad::Plan baseline;baseline.width=848;baseline.height=672;baseline.padding={{64,64,64,68}};baseline.alignment=16;
    std::array<line2Dup::MatchWorkspace,4> workspaces;std::array<std::vector<double>,4> matchSamples,totalSamples;
    std::array<std::vector<double>,2> matchRatios,totalRatios;pad::U calls=0;std::size_t frames=0;
    std::ofstream csv(output/"timing_samples.csv");csv<<"scene,image,round,warmup,order,arm,path,match_ms,external_call_ms,raw,selected\n";csv<<std::setprecision(17);
    for(const auto& node:verified["frames"]) {
        const auto key=std::make_pair(int(node["scene_id"]),int(node["image_id"]));const auto& f=indexed.at(key);
        const auto image=cv::imread((root/f.rgb).string(),cv::IMREAD_GRAYSCALE);ensure(!image.empty() && image.cols==720 && image.rows==540,"Timing image dimension changed");
        std::array<std::vector<Detection>,4> reference;
        reference[0]=readRaw(str(node["fallback_raw"]),f,"fallback",meta);reference[1]=readRaw(str(node["fused_raw"]),f,"fused",meta);
        reference[2]=readRaw(qualityPath/"auto"/(frameKey(f)+"_fallback_raw.csv.gz"),f,"fallback",meta);reference[3]=readRaw(qualityPath/"auto"/(frameKey(f)+"_fused_raw.csv.gz"),f,"fused",meta);
        ensure(exactRows(reference[0],reference[1]) && exactRows(reference[2],reference[3]),"Timing reference path equality failed");
        for(int round=0;round<8;++round) {
            std::array<double,4> match{},total{};
            for(int place=0;place<4;++place) {
                const int variant=(place+round)%4;const bool automatic=variant>=2,fused=(variant%2)==1;
                const auto result=call(detector,meta,image,automatic?autoPlan:baseline,workspaces[variant],fused,config);++calls;
                ensure(exactRows(result.raw,reference[variant]),"Timed output differs from its frozen arm/path reference");
                csv<<f.scene<<','<<f.image<<','<<round<<','<<(round==0)<<','<<place<<','<<(automatic?"auto":"baseline")<<','<<(fused?"fused":"fallback")<<','<<result.match_ms<<','<<result.total_ms<<','<<result.raw.size()<<','<<result.selected.size()<<'\n';
                match[variant]=result.match_ms;total[variant]=result.total_ms;
                if(round){matchSamples[variant].push_back(result.match_ms);totalSamples[variant].push_back(result.total_ms);}
                checkResources(output,began,30);
            }
            if(round)for(int path=0;path<2;++path){ensure(match[path]>0 && total[path]>0,"Invalid clock interval");matchRatios[path].push_back(match[path+2]/match[path]);totalRatios[path].push_back(total[path+2]/total[path]);}
        }
        ++frames;std::cout<<"TIMING "<<frameKey(f)<<" complete\n";
    }
    ensure(frames==64 && calls==2048,"Incomplete fixed timing stage");
    cv::FileStorage out((output/"timing_metrics.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
    out<<"protocol"<<"obj8_full_bank_minimum_padding_development_v1"<<"frames"<<64<<"warmup_rounds"<<1<<"measured_rounds"<<7<<"matcher_calls"<<double(calls)<<"all_timed_candidates_exact_to_own_reference"<<1<<"paired_performance_benchmark"<<1<<"heldout_images_read"<<0<<"peak_rss_bytes"<<double(peakRss());
    out<<"variants"<<"[";
    for(int variant=0;variant<4;++variant)out<<"{"<<"arm"<<(variant>=2?"auto":"baseline")<<"path"<<(variant%2?"fused":"fallback")<<"measured_samples"<<int(matchSamples[variant].size())<<"match_median_ms"<<percentile(matchSamples[variant],.5)<<"match_p95_ms"<<percentile(matchSamples[variant],.95)<<"external_call_median_ms"<<percentile(totalSamples[variant],.5)<<"external_call_p95_ms"<<percentile(totalSamples[variant],.95)<<"}";
    out<<"]"<<"paired_ratios_auto_over_baseline"<<"[";
    for(int path=0;path<2;++path)out<<"{"<<"path"<<(path?"fused":"fallback")<<"samples"<<int(matchRatios[path].size())<<"match_median"<<percentile(matchRatios[path],.5)<<"match_p95"<<percentile(matchRatios[path],.95)<<"external_call_median"<<percentile(totalRatios[path],.5)<<"external_call_p95"<<percentile(totalRatios[path],.95)<<"}";
    out<<"]";
}
static void selftest(const fs::path& output) {
    const auto p=pad::make_plan(720,540,{{64,64,64,68}},
        {{"object",0,0,734,734,0,0,734,734},{"object",0,1,367,367,0,0,367,367}},{4,8});
    ensure(p.width==848 && p.height==800 && p.padding==std::array<pad::U,4>{{64,64,64,196}},"Native planner integration failed");
    cv::Mat image(540,720,CV_8U,cv::Scalar(37)),padded;
    cv::copyMakeBorder(image,padded,64,196,64,64,cv::BORDER_CONSTANT,cv::Scalar(0));
    ensure(padded.cols==848 && padded.rows==800 && padded.at<unsigned char>(64,64)==37 && padded.at<unsigned char>(63,64)==0 && padded.at<unsigned char>(604,64)==0,"Padding/origin integration failed");
    gzipSelfTest(output);cv::FileStorage out((output/"adapter_selftest.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
    out<<"passed"<<1<<"dataset_images_read"<<0<<"matcher_calls"<<0<<"synthetic_image_created"<<1;
}
int main(int argc,char** argv) {
    fs::path output;bool created=false;std::string mode="unknown";
    try {
        std::map<std::string,std::string> args;
        for(int i=1;i<argc;i+=2){ensure(i+1<argc,"Arguments require values");ensure(args.emplace(argv[i],argv[i+1]).second,"Duplicate argument");}
        for(const auto& item:args)ensure(item.first=="--mode" || item.first=="--output" || item.first=="--verified" || item.first=="--quality","Unknown argument");
        mode=args.at("--mode");output=fs::absolute(args.at("--output"));ensure(!fs::exists(output),"Output directory must be new");fs::create_directories(output);created=true;std::ofstream(output/".gitignore")<<"*\n";
        cv::setNumThreads(1);
#ifdef _OPENMP
        omp_set_num_threads(4);omp_set_dynamic(0);
#endif
        const auto began=std::chrono::steady_clock::now();
        if(mode=="selftest"){selftest(output);return 0;}
        ensure(mode=="pilot" || mode=="development" || mode=="timing","Only declared development stages are allowed");
        cv::FileStorage verified(args.at("--verified"),cv::FileStorage::READ);
        ensure(verified.isOpened() && int(verified["verified"])==1 && int(verified["schema_version"])==1 && str(verified["split"])=="development" && readObjectIds(verified["target_objects"])==std::vector<int>{8} && str(verified["padding_mode"])==mode && str(verified["padding_protocol_sha256"])=="ab9207f2dd492622aed8f563997b00ca6d137d5c93fa0f2c99b67f7ec756573d","Missing frozen verified padding input");
        const fs::path training=str(verified["training_directory"]);cv::FileStorage cfg(str(verified["config_file"]),cv::FileStorage::READ);const auto config=readConfig(cfg);
        ensure(config.features==32 && config.coarse==85 && config.selected==85 && config.angle_step==30 && config.scales==std::vector<double>{.75,1,1.5,2} && config.thresholds==std::vector<double>{85},"Fixed recipe changed");
        const auto meta=readMeta(training/"template_metadata.json");line2Dup::Detector detector(32,{4,8},20,40);detector.readClasses({"tless_object_8"},(training/"templates_%s.yml.gz").string());
        ensure(meta.size()==3456 && detector.numTemplates()==3456,"Template bank size changed");
        const auto layers=loadedLayers(detector);
        const auto plan=pad::make_plan(720,540,{{64,64,64,68}},layers,{4,8});
        ensure(plan.width==848 && plan.height==800 && plan.padding==std::array<pad::U,4>{{64,64,64,196}},"Computed size differs from predeclared size");writeGeometry(layers,plan,output);
        if(mode=="timing")timing(verified,detector,meta,config,plan,fs::absolute(args.at("--quality")),output,began);
        else quality(mode,verified,detector,meta,config,plan,output,began);
        return 0;
    }catch(const std::exception& error) {
        std::cerr<<"PADDING FAILED: "<<error.what()<<'\n';
        if(created)try{cv::FileStorage failure((output/"failure.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);failure<<"failed"<<1<<"incomplete"<<1<<"mode"<<mode<<"reason"<<error.what()<<"do_not_count_missing_frames_as_negative"<<1;}catch(...){}
        return 1;
    }
}

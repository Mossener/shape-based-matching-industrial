// V31 three-arm successor, adapted from the V30 adapter. Native validation pending.
// Link the exact ../control_v11/line2Dup.cpp as the separate core translation unit.
#define main frozen_public_evaluator_entry
#include "../frozen_helpers/tless_eval.cpp"
#undef main
#include "quality_support.hpp"
using namespace rgb_stratified_quality;

static std::vector<Frame> schedule(const cv::FileStorage& inputs,int object,const std::string& mode){
    std::map<std::pair<int,int>,Frame> indexed;for(const auto& f:readFrames(str(inputs["dataset_root"]),false,"development",{object}))need(indexed.emplace(std::make_pair(f.scene,f.image),f).second,"Duplicate development frame");
    std::vector<Frame> result;std::set<std::pair<int,int>> seen;
    for(const auto& node:inputs["development"]){const auto key=std::make_pair(int(node["scene_id"]),int(node["image_id"]));need(seen.insert(key).second,"Duplicate frozen schedule frame");const auto& f=indexed.at(key);need(f.rgb==str(node["rgb"]),"Frozen development source path changed");
        const bool use=mode=="development" || (mode=="timing"?int(node["timing"])!=0:int(node["pilot"])!=0);if(use)result.push_back(f);
    }
    need(seen.size()==400 && result.size()==std::size_t(mode=="timing"?64:mode=="development"?400:8),"Fixed schedule count changed");return result;
}
static cv::Mat decode(const fs::path& root,const Frame& f,double& decodeMs){const auto begin=Clock::now();auto image=cv::imread((root/f.rgb).string(),cv::IMREAD_GRAYSCALE);decodeMs+=milliseconds(Clock::now()-begin);need(!image.empty() && image.type()==CV_8UC1 && image.cols==720 && image.rows==540,"Development image type/dimensions changed");return image;}
static bool pilotFrame(const cv::FileStorage& inputs,const Frame& f){for(const auto& n:inputs["development"])if(int(n["scene_id"])==f.scene && int(n["image_id"])==f.image)return int(n["pilot"])!=0;throw std::runtime_error("Missing frozen pilot flag");}
static fs::path rawPath(const fs::path& root,int obj,const std::string& arm,const Frame& f,const std::string& path){return root/("obj"+std::to_string(obj))/arm/(frameKey(f)+"_"+path+"_raw.csv.gz");}
static std::array<Bank,3> banks(const cv::FileNode& node,bool rgbOnly){
    const int object=int(node["object_id"]);std::array<Bank,3> result;
    result[0]=loadBank(str(node["control_training"]),object,int(node["control_template_count"]),ARMS[0]);
    if(!rgbOnly){result[1]=loadBank(str(node["pooled_training"]),object,int(node["pooled_template_count"]),ARMS[1]);result[2]=loadBank(str(node["stratified_training"]),object,int(node["stratified_template_count"]),ARMS[2]);}
    return result;
}
static void bankTiming(std::ofstream& stream,const Bank& b){stream<<b.object<<','<<b.arm<<','<<b.meta.size()<<','<<b.metadataMs<<','<<b.bankMs<<'\n';need(stream.good(),"Bank-load timing write failed");}
static void retain(std::ofstream& stream,int object,const Frame& frame,const std::array<Pipeline,3>& results,const std::array<Bank,3>& bank,const std::array<Counts,3>& counted,const std::string& metric){
    std::array<std::map<int,std::size_t>,3> detected;
    for(int arm=0;arm<3;++arm)for(std::size_t i=0;i<results[arm].selected.size();++i)if(counted[arm].labels[i]=="TP")need(detected[arm].emplace(counted[arm].gt_ids[i],i).second,"Duplicate matched GT identity");
    for(int arm=1;arm<3;++arm)for(const auto& gt:frame.gt){
        if(metric=="eligible" && gt.visibility<.5)continue;
        const auto a=detected[0].find(gt.id),b=detected[arm].find(gt.id);const bool first=a!=detected[0].end(),second=b!=detected[arm].end();int same=-1;
        if(first && second){const auto& x=results[0].selected[a->second];const auto& y=results[arm].selected[b->second];const auto& m=findMeta(bank[0].meta,x.class_id,x.template_id);const auto& n=findMeta(bank[arm].meta,y.class_id,y.template_id);same=int(std::tie(m.image,m.angle,m.scale)==std::tie(n.image,n.angle,n.scale));}
        const char* status=first?(second?"retained":"lost"):(second?"gained":"neither");
        stream<<object<<','<<frame.scene<<','<<frame.image<<','<<metric<<','<<gt.id<<','<<ARMS[arm]<<','<<first<<','<<second<<','<<same<<','<<status<<'\n';
    }need(stream.good(),"GT/pose retention write failed");
}
static void quality(const std::string& mode,const cv::FileStorage& inputs,const Padding& common,const fs::path& previous,const fs::path& output,const Clock::time_point& began){
    const bool gate=mode=="old_gate";const int armCount=gate?1:3;const Padding pad=gate?Padding{848,672,{{64,64,64,68}}}:common;const fs::path dataset=str(inputs["dataset_root"]);
    std::ofstream equality(output/"candidate_equality.csv"),per(output/"per_frame_metrics.csv"),selected(output/"selected_detections.csv"),retention(output/"gt_retention.csv"),load(output/"bank_load_timings.csv"),gt(output/"ground_truth.csv");
    equality<<"object_id,scene,image,arm,fallback_count,fused_count,exact_order_fields_score_bits,reference_exact,fallback_match_ms,fused_match_ms,fallback_external_ms,fused_external_ms\n";
    per<<"object_id,scene,image,arm,raw,selected,tp,fp,fn,gt,eligible_tp,eligible_fp,eligible_fn,eligible_gt,ignored,all_iou_sum,eligible_iou_sum,negative_fp\n";
    selected<<"object_id,scene,image,arm,rank,class_id,score,score_bits,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h,allGT_label,allGT_id,eligible_label,eligible_id\n";
    retention<<"object_id,scene,image,metric,gt_id,comparison_arm,rgb_control_detected,comparison_detected,same_pose_if_both,identity_change\n";load<<"object_id,arm,templates,metadata_load_ms,bank_load_ms\n";gt<<"object_id,scene,image,gt_id,class_id,visibility,bbox_x,bbox_y,bbox_w,bbox_h\n";
    equality<<std::setprecision(17);per<<std::setprecision(17);selected<<std::setprecision(17);load<<std::setprecision(17);gt<<std::setprecision(17);
    std::array<Totals,3> pooled{};std::map<int,std::array<Totals,3>> pooledScenes;std::size_t frameObjects=0,objectCount=0;double decodeMs=0;
    for(const auto& item:inputs["banks"]){const int object=int(item["object_id"]);need(object==OBJECTS.at(objectCount++),"Quality object order/scope changed");auto bank=banks(item,gate);for(int arm=0;arm<armCount;++arm)bankTiming(load,bank[arm]);checkpoint(began,mode=="development"?240:30);
        std::array<line2Dup::MatchWorkspace,6> workspace;std::array<Totals,3> totals{};std::map<int,std::array<Totals,3>> scenes;
        const auto directory=output/("obj"+std::to_string(object));fs::create_directories(directory);
        for(const auto& frame:schedule(inputs,object,mode)){const auto image=decode(dataset,frame,decodeMs);std::array<Pipeline,3> results;
            for(const auto& truth:frame.gt)gt<<object<<','<<frame.scene<<','<<frame.image<<','<<truth.id<<','<<truth.class_id<<','<<truth.visibility<<','<<truth.box.x<<','<<truth.box.y<<','<<truth.box.w<<','<<truth.box.h<<'\n';
            for(int arm=0;arm<armCount;++arm){auto first=call(bank[arm],image,pad,workspace[arm*2],false);checkpoint(began,mode=="development"?240:30);auto second=call(bank[arm],image,pad,workspace[arm*2+1],true);checkpoint(began,mode=="development"?240:30);
                archive(directory/ARMS[arm],frame,"fallback",first,bank[arm]);archive(directory/ARMS[arm],frame,"fused",second,bank[arm]);const bool equal=exactRows(first.raw,second.raw) && exactRows(first.selected,second.selected);bool reference=true;
                if(gate){const fs::path old=str(item["original_pilot_raw"]);reference=exactRows(first.raw,readRaw(old/(frameKey(frame)+"_fallback_raw.csv.gz"),frame,"fallback",bank[arm].meta)) && exactRows(second.raw,readRaw(old/(frameKey(frame)+"_fused_raw.csv.gz"),frame,"fused",bank[arm].meta));}
                if(arm==0 && !gate){const fs::path old=str(item["c0_common_raw"]);reference=exactRows(first.raw,readRaw(old/(frameKey(frame)+"_fallback_raw.csv.gz"),frame,"fallback",bank[arm].meta)) && exactRows(second.raw,readRaw(old/(frameKey(frame)+"_fused_raw.csv.gz"),frame,"fused",bank[arm].meta));}
                if(mode=="development" && pilotFrame(inputs,frame))reference=reference && exactRows(first.raw,readRaw(rawPath(previous,object,ARMS[arm],frame,"fallback"),frame,"fallback",bank[arm].meta)) && exactRows(second.raw,readRaw(rawPath(previous,object,ARMS[arm],frame,"fused"),frame,"fused",bank[arm].meta));
                equality<<object<<','<<frame.scene<<','<<frame.image<<','<<ARMS[arm]<<','<<first.raw.size()<<','<<second.raw.size()<<','<<equal<<','<<reference<<','<<first.matchMs<<','<<second.matchMs<<','<<first.totalMs<<','<<second.totalMs<<'\n';equality.flush();need(equal && reference,"Ordered fields/score bits or own exact reference mismatch; raw evidence preserved");results[arm]=std::move(first);
            }
            std::array<Counts,3> all{},eligible{};
            for(int arm=0;arm<armCount;++arm){const auto& r=results[arm];all[arm]=evaluate(r.selected,frame.gt,.5,false,.5);eligible[arm]=evaluate(r.selected,frame.gt,.5,true,.5);const auto& a=all[arm];const auto& e=eligible[arm];
                append(totals[arm],a,e,frame.gt.empty(),r.raw.size());append(scenes[frame.scene][arm],a,e,frame.gt.empty(),r.raw.size());append(pooled[arm],a,e,frame.gt.empty(),r.raw.size());append(pooledScenes[frame.scene][arm],a,e,frame.gt.empty(),r.raw.size());
                per<<object<<','<<frame.scene<<','<<frame.image<<','<<ARMS[arm]<<','<<r.raw.size()<<','<<r.selected.size()<<','<<a.tp<<','<<a.fp<<','<<a.fn<<','<<a.gt<<','<<e.tp<<','<<e.fp<<','<<e.fn<<','<<e.gt<<','<<e.ignored<<','<<a.matched_iou_sum<<','<<e.matched_iou_sum<<','<<(frame.gt.empty()?a.fp:0)<<'\n';
                for(std::size_t i=0;i<r.selected.size();++i){const auto& d=r.selected[i];const auto& m=findMeta(bank[arm].meta,d.class_id,d.template_id);selected<<object<<','<<frame.scene<<','<<frame.image<<','<<ARMS[arm]<<','<<i<<','<<d.class_id<<','<<d.score<<','<<scoreBits(d.score)<<','<<d.template_id<<','<<m.image<<','<<m.angle<<','<<m.scale<<','<<d.match_x<<','<<d.match_y<<','<<d.box.x<<','<<d.box.y<<','<<d.box.w<<','<<d.box.h<<','<<a.labels[i]<<','<<a.gt_ids[i]<<','<<e.labels[i]<<','<<e.gt_ids[i]<<'\n';}
            }
            if(!gate){retain(retention,object,frame,results,bank,all,"allGT");retain(retention,object,frame,results,bank,eligible,"eligible");}
            need(equality.good() && per.good() && selected.good() && retention.good() && load.good() && gt.good(),"Quality numeric evidence write failed");checkpoint(began,mode=="development"?240:30);++frameObjects;std::cout<<"QUALITY "<<mode<<" object "<<object<<' '<<frameKey(frame)<<" calls "<<calls<<'\n';
        }
        cv::FileStorage report((directory/"metrics.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);report<<"object_id"<<object;for(int arm=0;arm<armCount;++arm)writeTotals(report,ARMS[arm],totals[arm]);report<<"per_scene"<<"[";for(const auto& scene:scenes){report<<"{"<<"scene_id"<<scene.first;for(int arm=0;arm<armCount;++arm)writeTotals(report,ARMS[arm],scene.second[arm]);report<<"}";}report<<"]";
    }
    const std::uint64_t expected=gate?96:mode=="pilot"?288:14400;need(objectCount==6 && frameObjects==std::size_t(mode=="development"?2400:48) && calls==expected,"Quality stage fixed budget/coverage incomplete");
    for(auto* stream:{&equality,&per,&selected,&retention,&load,&gt}){stream->close();need(!stream->fail(),"Quality numeric close failed");}
    cv::FileStorage report((output/"stage_summary.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);report<<"passed"<<1<<"stage"<<mode<<"objects"<<OBJECTS<<"unique_frames"<<(mode=="development"?400:8)<<"object_frame_combinations"<<int(frameObjects)<<"matcher_calls"<<double(calls)<<"exact_same_arm_paths"<<1<<"complete_raw_archives"<<1<<"raw_output_bytes"<<double(rawBytes)<<"decode_total_ms"<<decodeMs<<"peak_rss_bytes"<<double(peakRss())<<"decode_and_bank_load_excluded_from_external_call"<<1<<"paired_performance_benchmark"<<0;
    for(int arm=0;arm<armCount;++arm)writeTotals(report,ARMS[arm],pooled[arm]);report<<"per_scene"<<"[";for(const auto& scene:pooledScenes){report<<"{"<<"scene_id"<<scene.first;for(int arm=0;arm<armCount;++arm)writeTotals(report,ARMS[arm],scene.second[arm]);report<<"}";}report<<"]";
}
static void timing(const cv::FileStorage& inputs,const Padding& common,const fs::path& previous,const fs::path& output,const Clock::time_point& began){
    const fs::path dataset=str(inputs["dataset_root"]);std::ofstream csv(output/"timing_samples.csv"),pairs(output/"timing_pairs.csv"),load(output/"bank_load_timings.csv");
    csv<<"object_id,scene,image,frame_ordinal,round,warmup,order,arm,path,match_ms,external_call_ms,raw,selected,exact_own_reference\n";
    pairs<<"object_id,scene,image,frame_ordinal,round,path,numerator,denominator,match_ratio,external_ratio\n";
    load<<"object_id,arm,templates,metadata_load_ms,bank_load_ms\n";csv<<std::setprecision(17);pairs<<std::setprecision(17);load<<std::setprecision(17);
    std::array<std::vector<double>,6> matchSamples,totalSamples;double decodeMs=0;int objects=0,frameObjects=0;
    for(const auto& item:inputs["banks"]){const int object=int(item["object_id"]);need(object==OBJECTS.at(objects++),"Timing object order/scope changed");auto bank=banks(item,false);for(const auto& b:bank)bankTiming(load,b);std::array<line2Dup::MatchWorkspace,6> workspace;
        int frameOrdinal=0;
        for(const auto& frame:schedule(inputs,object,"timing")){const auto image=decode(dataset,frame,decodeMs);std::array<std::vector<Detection>,6> references;
            for(int v=0;v<6;++v)references[v]=readRaw(rawPath(previous,object,ARMS[v/2],frame,PATHS[v%2]),frame,PATHS[v%2],bank[v/2].meta);
            for(int arm=0;arm<3;++arm)need(exactRows(references[2*arm],references[2*arm+1]),"Own timing reference path equality failed");
            for(int round=0;round<13;++round){std::array<double,6> match{},total{};
                for(int order=0;order<6;++order){const int variant=(order+frameOrdinal+round)%6;const auto result=call(bank[variant/2],image,common,workspace[variant],variant%2!=0);const bool equal=exactRows(result.raw,references[variant]);
                    csv<<object<<','<<frame.scene<<','<<frame.image<<','<<frameOrdinal<<','<<round<<','<<(round==0)<<','<<order<<','<<ARMS[variant/2]<<','<<PATHS[variant%2]<<','<<result.matchMs<<','<<result.totalMs<<','<<result.raw.size()<<','<<result.selected.size()<<','<<equal<<'\n';csv.flush();need(equal && csv.good(),"Timed call differs from own arm/path full raw reference");
                    match[variant]=result.matchMs;total[variant]=result.totalMs;if(round){matchSamples[variant].push_back(result.matchMs);totalSamples[variant].push_back(result.totalMs);}checkpoint(began,90);
                }
                if(round)for(int path=0;path<2;++path)for(const auto& pair:std::array<std::pair<int,int>,3>{{{1,0},{2,0},{2,1}}}){
                    const int n=pair.first*2+path,d=pair.second*2+path;need(match[d]>0 && total[d]>0,"Nonpositive paired clock interval");
                    pairs<<object<<','<<frame.scene<<','<<frame.image<<','<<frameOrdinal<<','<<round<<','<<PATHS[path]<<','<<ARMS[pair.first]<<','<<ARMS[pair.second]<<','<<match[n]/match[d]<<','<<total[n]/total[d]<<'\n';
                }
            }++frameObjects;++frameOrdinal;std::cout<<"TIMING object "<<object<<' '<<frameKey(frame)<<" calls "<<calls<<'\n';
        }need(frameOrdinal==64,"Timing fixed-frame ordinal differs");
    }
    need(objects==6 && frameObjects==384 && calls==29952,"Incomplete fixed timing schedule");csv.close();pairs.close();load.close();need(!csv.fail() && !pairs.fail() && !load.fail(),"Timing evidence close failed");
    cv::FileStorage out((output/"stage_summary.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);out<<"passed"<<1<<"stage"<<"timing"<<"objects"<<OBJECTS<<"unique_frames"<<64<<"object_frame_combinations"<<384<<"matcher_calls"<<double(calls)<<"warmup_rounds"<<1<<"measured_rounds"<<12<<"formal_rows"<<27648<<"exact_own_reference_every_call"<<1<<"decode_total_ms"<<decodeMs<<"peak_rss_bytes"<<double(peakRss())<<"decode_and_bank_load_excluded_from_external_call"<<1<<"paired_performance_benchmark"<<1<<"variants"<<"[";
    for(int v=0;v<6;++v){need(matchSamples[v].size()==4608,"Formal samples per variant differ");out<<"{"<<"arm"<<ARMS[v/2]<<"path"<<PATHS[v%2]<<"samples"<<int(matchSamples[v].size())<<"match_median_ms"<<percentile(matchSamples[v],.5)<<"match_p95_ms"<<percentile(matchSamples[v],.95)<<"external_median_ms"<<percentile(totalSamples[v],.5)<<"external_p95_ms"<<percentile(totalSamples[v],.95)<<"}";}out<<"]";
}
int main(int argc,char** argv){fs::path output;bool created=false;std::string mode="unknown";try{
    std::map<std::string,std::string> args;for(int i=1;i<argc;i+=2){need(i+1<argc,"Arguments require values");need(args.emplace(argv[i],argv[i+1]).second,"Duplicate argument");}for(const auto& item:args)need(item.first=="--mode" || item.first=="--output" || item.first=="--inputs" || item.first=="--previous","Unknown quality argument");
    mode=args.at("--mode");need(mode=="selftest" || mode=="old_gate" || mode=="pilot" || mode=="development" || mode=="timing","Only fixed development modes allowed");output=fs::absolute(args.at("--output"));need(!fs::exists(output),"Native output must be fresh");fs::create_directories(output);created=true;std::ofstream(output/".gitignore")<<"*\n";cv::setNumThreads(1);
#ifdef _OPENMP
    omp_set_num_threads(4);omp_set_dynamic(0);
#endif
    const auto began=Clock::now();if(mode=="selftest"){selftest(output);return 0;}
    maximumCalls=mode=="old_gate"?96:mode=="pilot"?288:mode=="development"?14400:29952;
    cv::FileStorage inputs(args.at("--inputs"),cv::FileStorage::READ);need(inputs.isOpened() && str(inputs["version"])=="rgb_stratified_quality_inputs_v1" && readObjectIds(inputs["objects"])==OBJECTS,"Missing frozen quality inputs");cv::FileStorage plan(str(inputs["common_padding_json"]),cv::FileStorage::READ);need(plan.isOpened() && int(plan["geometry_feasible"])==1 && int(plan["banks"])==18,"Missing frozen full-bank union padding");const auto pad=padding(plan);
    const fs::path previous=args.count("--previous")?fs::absolute(args.at("--previous")):fs::path{};
    if(mode=="timing")timing(inputs,pad,previous,output,began);else quality(mode,inputs,pad,previous,output,began);return 0;
}catch(const std::exception& error){std::cerr<<"RGB STRATIFIED QUALITY FAILED: "<<error.what()<<'\n';if(created)try{cv::FileStorage fail((output/"failure.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);fail<<"incomplete"<<1<<"stage"<<mode<<"reason"<<error.what()<<"matcher_invocations_started"<<double(calls)<<"last_native_raw_count"<<double(lastNativeRaw)<<"raw_output_bytes"<<double(rawBytes)<<"missing_frames_are_not_negatives"<<1;}catch(...){}return 1;}}


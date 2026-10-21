// Independent binary-source/empty-selection-mask successor. Copies retain the original
// source helpers, while every matching/feature implementation comes from the
// explicitly compiled private V11 Git bytes. The original entry is not called.
#define main frozen_public_evaluator_entry
#include "frozen_helpers/tless_eval.cpp"
#undef main
#include "frozen_helpers/padding_plan.hpp"
#include "silhouette_source.hpp"
#include "empty_mask_policy.hpp"
#include <cstdint>
#include <limits>
#include <memory>
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
static const std::vector<int> OBJECTS{1,2,5,8,12,17};
static void ensure(bool value,const std::string& message){if(!value)throw std::runtime_error(message);}
static std::vector<std::string> splitCsv(const std::string& row) {
    std::vector<std::string> values;std::size_t first=0;
    for(std::size_t i=0;i<=row.size();++i)if(i==row.size() || row[i]==','){values.push_back(row.substr(first,i-first));first=i+1;}
    return values;
}
static pad::U peakRss() {
    PROCESS_MEMORY_COUNTERS counters{};counters.cb=sizeof(counters);
    ensure(GetProcessMemoryInfo(GetCurrentProcess(),&counters,sizeof(counters))!=0,"Cannot read process peak working set");
    return pad::U(counters.PeakWorkingSetSize);
}
static void checkpoint(const std::chrono::steady_clock::time_point& began,int minutes) {
    ensure(peakRss()<=1610612736ULL,"Process peak RSS exceeds frozen 1.5 GiB ceiling");
    ensure(std::chrono::duration<double>(std::chrono::steady_clock::now()-began).count()<=minutes*60.,"Stage soft time checkpoint exceeded");
}
using PoseKey=std::tuple<int,int,double>;
struct AttemptGeometry {int x=0,y=0,width=0,height=0,canvas=0,maskX=0,maskY=0,maskWidth=0,maskHeight=0;};
static std::map<PoseKey,AttemptGeometry> originalAttempts(const fs::path& file,int obj) {
    std::ifstream stream(file);ensure(stream.good(),"Cannot read original pose attempts");std::string row;std::getline(stream,row);
    ensure(row=="class_id,training_image,angle,scale,success,template_id,source_crop_x,source_crop_y,source_crop_w,source_crop_h,canvas,mask_x,mask_y,mask_w,mask_h,templ_tl_x,templ_tl_y,features_l0,features_l1,error","Original attempts CSV schema changed");
    std::map<PoseKey,AttemptGeometry> result;
    while(std::getline(stream,row)) {
        if(!row.empty() && row.back()=='\r')row.pop_back();const auto c=splitCsv(row);
        ensure(c.size()==20 && c[0]==classForObject(obj),"Original attempts record changed");
        AttemptGeometry g{std::stoi(c[6]),std::stoi(c[7]),std::stoi(c[8]),std::stoi(c[9]),std::stoi(c[10]),std::stoi(c[11]),std::stoi(c[12]),std::stoi(c[13]),std::stoi(c[14])};
        ensure(result.emplace(PoseKey{std::stoi(c[1]),std::stoi(c[2]),std::stod(c[3])},g).second,"Duplicate original pose key");
    }
    ensure(result.size()==3456,"Original pose coverage changed");return result;
}
static void sameGeometry(const AttemptGeometry& g,const cv::Rect& roi,int side,const cv::Rect& mask) {
    ensure(std::tie(g.x,g.y,g.width,g.height,g.canvas,g.maskX,g.maskY,g.maskWidth,g.maskHeight)==
           std::tie(roi.x,roi.y,roi.width,roi.height,side,mask.x,mask.y,mask.width,mask.height),"Silhouette pose geometry differs from frozen original attempt");
}
struct Trained {int object=0,attempts=0,successful=0,opencvErrors=0;fs::path directory;};
static void featureDiagnostics(std::ofstream& csv,const std::vector<line2Dup::Template>& layers,int obj,int image,int angle,double scale,int id,const cv::Mat& source) {
    // Mirror the frozen extractor's explicit floor-half pyrDown output size.
    // The returned Mat sizes are diagnostics; they never alter the source,
    // feature bank, training border or successful-pose decision.
    cv::Mat reduced;cv::pyrDown(source,reduced,{source.cols/2,source.rows/2});
    const std::array<cv::Size,2> sizes{{source.size(),reduced.size()}};
    for(const auto& layer:layers) {
        const auto actual=sizes.at(layer.pyramid_level);bool invalid=false;
        int minX=std::numeric_limits<int>::max(),minY=minX,maxX=std::numeric_limits<int>::min(),maxY=maxX;
        int absoluteMinX=minX,absoluteMinY=minY,absoluteMaxX=maxX,absoluteMaxY=maxY,edge=minX;
        for(const auto& feature:layer.features) {
            const int x=feature.x+layer.tl_x,y=feature.y+layer.tl_y;
            invalid=invalid || x<0 || x>=actual.width || y<0 || y>=actual.height;
            minX=std::min(minX,feature.x);minY=std::min(minY,feature.y);maxX=std::max(maxX,feature.x);maxY=std::max(maxY,feature.y);
            absoluteMinX=std::min(absoluteMinX,x);absoluteMinY=std::min(absoluteMinY,y);absoluteMaxX=std::max(absoluteMaxX,x);absoluteMaxY=std::max(absoluteMaxY,y);
            edge=std::min(edge,std::min(std::min(x,y),std::min(actual.width-1-x,actual.height-1-y)));
        }
        csv<<classForObject(obj)<<','<<image<<','<<angle<<','<<scale<<','<<id<<','<<layer.pyramid_level<<','<<actual.width<<','<<actual.height<<','<<layer.tl_x<<','<<layer.tl_y<<','<<layer.width<<','<<layer.height<<','<<layer.features.size()<<','<<minX<<','<<minY<<','<<maxX<<','<<maxY<<','<<absoluteMinX<<','<<absoluteMinY<<','<<absoluteMaxX<<','<<absoluteMaxY<<','<<edge<<'\n';
        ensure(csv.good(),"Feature canvas diagnostics write failed");
        if(invalid){csv.flush();ensure(false,"Selected feature outside actual training layer canvas; invalid diagnostics preserved");}
    }
}
static Trained trainSilhouette(const fs::path& dataset,const fs::path& original,const fs::path& sourceOnly,const fs::path& output,int obj,
                                const std::chrono::steady_clock::time_point& began) {
    ensure(!fs::exists(output),"Object training directory must be fresh");fs::create_directories(output);
    std::ofstream attempts(output/"template_attempts.csv"),errors(output/"attempt_errors.txt"),features(output/"feature_geometry.csv");
    ensure(attempts.good() && errors.good() && features.good(),"Cannot create training evidence");
    attempts<<"class_id,training_image,angle,scale,success,template_id,source_crop_x,source_crop_y,source_crop_w,source_crop_h,canvas,mask_x,mask_y,mask_w,mask_h,templ_tl_x,templ_tl_y,features_l0,features_l1,error\n";
    const auto originals=originalAttempts(original/"template_attempts.csv",obj);
    const auto sourceOnlyOriginals=originalAttempts(sourceOnly/"template_attempts.csv",obj);
    features<<"class_id,training_image,angle,scale,template_id,level,canvas_width,canvas_height,tl_x,tl_y,width,height,actual_features,min_x,min_y,max_x,max_y,min_absolute_x,min_absolute_y,max_absolute_x,max_absolute_y,min_canvas_edge_distance\n";
    std::set<PoseKey> visited;std::vector<TemplateMeta> metadata;Config config;
    line2Dup::Detector detector(32,{4,8},20,40);int count=0,opencvErrors=0;
    for(const auto& frame:readFrames(dataset,true,"",{obj})) {
        const auto image=cv::imread((dataset/frame.rgb).string(),cv::IMREAD_GRAYSCALE);
        const auto mask=cv::imread((dataset/frame.mask).string(),cv::IMREAD_GRAYSCALE);
        ensure(!image.empty() && !mask.empty() && image.type()==CV_8UC1 && image.size()==mask.size(),"Invalid training grayscale/mask source");
        // Validate before cropping so nonbinary pixels outside the object ROI
        // cannot silently disappear. This clone is validation-only here.
        silhouette_experiment::training_source(mask);
        const auto roi=maskBox(mask);const auto crop=image(roi),cropMask=mask(roi);
        for(double scale:config.scales)for(int angle=0;angle<360;angle+=config.angle_step) {
            const PoseKey key{frame.image,angle,scale};const auto old=originals.find(key);
            ensure(old!=originals.end() && visited.insert(key).second,"Missing/duplicate original pose key");
            int side=int(std::ceil(std::hypot(roi.width,roi.height)*scale))+2*config.border;side=(side+15)/16*16;
            auto affine=cv::getRotationMatrix2D({roi.width/2.f,roi.height/2.f},angle,scale);
            affine.at<double>(0,2)+=side/2.-roi.width/2.;affine.at<double>(1,2)+=side/2.-roi.height/2.;
            cv::Mat originalGrayWarp,warpedMask;
            cv::warpAffine(crop,originalGrayWarp,affine,{side,side},cv::INTER_LINEAR,cv::BORDER_CONSTANT,cv::Scalar(0));
            cv::warpAffine(cropMask,warpedMask,affine,{side,side},cv::INTER_NEAREST,cv::BORDER_CONSTANT,cv::Scalar(0));
            const auto silhouette=maskBox(warpedMask);sameGeometry(old->second,roi,side,silhouette);sameGeometry(sourceOnlyOriginals.at(key),roi,side,silhouette);
            const auto maskBefore=warpedMask.clone();auto source=silhouette_experiment::training_source(warpedMask);
            ensure(source.data!=warpedMask.data,"Source/object-mask ownership alias");
            int id=-1,tx=0,ty=0,n0=0,n1=0;std::string error;
            try{id=empty_mask_experiment::add_template(detector,source,classForObject(obj));if(id<0)error="insufficient_features";}
            catch(const cv::Exception& e){error="opencv_exception";++opencvErrors;errors<<"image "<<frame.image<<" angle "<<angle<<" scale "<<scale<<'\n'<<e.what()<<'\n';}
            ensure(cv::countNonZero(maskBefore!=warpedMask)==0,"Feature extraction mutated the original object mask");
            if(id>=0) {
                ensure(id==int(metadata.size()),"Mask-bank template IDs are not dense");const auto& layers=detector.getTemplates(classForObject(obj),id);
                ensure(layers.size()==2 && layers[0].pyramid_level==0 && layers[1].pyramid_level==1,"Extracted layer layout changed");
                tx=layers[0].tl_x;ty=layers[0].tl_y;n0=int(layers[0].features.size());n1=int(layers[1].features.size());
                // Requested 32/16 are extractor targets, not bounds: V11's
                // unchanged exhaustive selector may return fewer or more.
                ensure(n0>0 && n1>0,"Successful extracted layer is empty");
                featureDiagnostics(features,layers,obj,frame.image,angle,scale,id,source);
                metadata.push_back({id,frame.image,tx,ty,float(angle),float(scale),{double(silhouette.x),double(silhouette.y),double(silhouette.width),double(silhouette.height)},classForObject(obj)});
            }
            attempts<<classForObject(obj)<<','<<frame.image<<','<<angle<<','<<scale<<','<<int(id>=0)<<','<<id<<','<<roi.x<<','<<roi.y<<','<<roi.width<<','<<roi.height<<','<<side<<','<<silhouette.x<<','<<silhouette.y<<','<<silhouette.width<<','<<silhouette.height<<','<<tx<<','<<ty<<','<<n0<<','<<n1<<','<<error<<'\n';
            ++count;ensure(attempts.good() && errors.good() && features.good(),"Training evidence write failed");checkpoint(began,120);
        }
        attempts.flush();errors.flush();features.flush();std::cout<<"BINARY_EMPTY_MASK_TRAIN object "<<obj<<" image "<<frame.image<<" attempts "<<count<<" successful "<<metadata.size()<<'\n';
    }
    ensure(count==3456 && visited.size()==originals.size() && visited.size()==sourceOnlyOriginals.size(),"Incomplete mask-bank training coverage");attempts.close();errors.close();features.close();
    ensure(!attempts.fail() && !errors.fail() && !features.fail(),"Training evidence close failed");
    if(!metadata.empty())detector.writeClasses((output/"templates_%s.yml.gz").string());
    writeMeta(output/"template_metadata.json",metadata);
    cv::FileStorage configOut((output/"training_config.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
    writeConfig(configOut,config);configOut<<"target_objects"<<std::vector<int>{obj}<<"template_count"<<int(metadata.size())<<"attempts"<<count<<"opencv_exception_attempts"<<opencvErrors<<"training_source"<<"clone of binary official warped object mask"<<"feature_selection_mask"<<"empty cv::Mat()"<<"all_original_pose_geometries_equal"<<1<<"all_source_only_pose_geometries_equal"<<1;
    return {obj,count,int(metadata.size()),opencvErrors,output};
}
static void trainAll(const cv::FileStorage& closure,const fs::path& output,const std::chrono::steady_clock::time_point& began) {
    ensure(readObjectIds(closure["objects"])==OBJECTS,"Frozen six-object scope changed");
    const fs::path dataset=str(closure["dataset_root"]);std::vector<Trained> trained;
    for(const auto& bank:closure["rgb_banks"]) {
        const int obj=int(bank["object_id"]);ensure(obj==OBJECTS.at(trained.size()),"RGB bank order/scope changed");
        trained.push_back(trainSilhouette(dataset,str(bank["rgb_training"]),str(bank["source_only_training"]),output/("obj"+std::to_string(obj)),obj,began));
    }
    ensure(trained.size()==6,"Not all six mask banks were trained");int attempts=0,zero=0,opencvErrors=0;
    cv::FileStorage summary((output/"training_summary.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
    summary<<"objects"<<"[";for(const auto& object:trained){attempts+=object.attempts;zero+=object.successful==0;opencvErrors+=object.opencvErrors;summary<<"{"<<"object_id"<<object.object<<"attempts"<<object.attempts<<"successful_templates"<<object.successful<<"opencv_exception_attempts"<<object.opencvErrors<<"directory"<<object.directory.string()<<"}";}summary<<"]";
    ensure(attempts==20736,"Total training attempt budget changed");
    summary<<"attempts"<<attempts<<"zero_success_objects"<<zero<<"opencv_exception_attempts"<<opencvErrors<<"training_attempts_complete"<<1<<"comparison_feasible"<<int(zero==0 && opencvErrors==0)<<"incomplete_comparison"<<int(zero!=0 || opencvErrors!=0)<<"matcher_calls"<<0<<"peak_rss_bytes"<<double(peakRss());summary.release();
    ensure(opencvErrors==0,"OpenCV extraction exception occurred; all attempts preserved, comparison incomplete");
    ensure(zero==0,"At least one silhouette bank has zero successful templates; all attempts preserved, comparison incomplete");
}
struct Bank {std::string arm;int object=0;fs::path directory;int count=0;};
static std::vector<pad::Layer> scanBank(const Bank& bank,std::ofstream& csv) {
    line2Dup::Detector detector(32,{4,8},20,40);const auto cls=classForObject(bank.object);
    detector.readClasses({cls},(bank.directory/"templates_%s.yml.gz").string());
    ensure(detector.numTemplates()==bank.count && detector.numTemplates(cls)==bank.count && bank.count>0 && detector.classIds()==std::vector<std::string>{cls},"Loaded bank identity/count changed");
    const auto meta=readMeta(bank.directory/"template_metadata.json");ensure(int(meta.size())==bank.count,"Loaded metadata count changed");
    std::vector<pad::Layer> result;
    for(int id=0;id<bank.count;++id) {
        ensure(meta.at(id).class_id==cls && meta.at(id).id==id,"Loaded metadata ID/class changed");const auto& layers=detector.getTemplates(cls,id);ensure(layers.size()==2,"Loaded bank pyramid incomplete");
        for(int level=0;level<2;++level) {
            const auto& t=layers.at(level);ensure(t.pyramid_level==level && !t.features.empty(),"Loaded feature level invalid");
            pad::Layer row;row.class_id=bank.arm+"/"+cls;row.template_id=id;row.level=level;row.width=t.width;row.height=t.height;
            row.min_x=row.min_y=std::numeric_limits<std::int64_t>::max();row.max_x=row.max_y=std::numeric_limits<std::int64_t>::min();
            for(const auto& feature:t.features){ensure(feature.label>=0 && feature.label<8,"Loaded orientation label invalid");row.min_x=std::min(row.min_x,std::int64_t(feature.x));row.min_y=std::min(row.min_y,std::int64_t(feature.y));row.max_x=std::max(row.max_x,std::int64_t(feature.x));row.max_y=std::max(row.max_y,std::int64_t(feature.y));}
            csv<<bank.arm<<','<<bank.object<<','<<cls<<','<<id<<','<<level<<','<<t.width<<','<<t.height<<','<<row.min_x<<','<<row.min_y<<','<<row.max_x<<','<<row.max_y<<','<<t.features.size()<<'\n';
            ensure(csv.good(),"Loaded geometry CSV write failed");result.push_back(row);
        }
    }return result;
}
static void planAll(const cv::FileStorage& closure,const fs::path& training,const fs::path& output) {
    cv::FileStorage summary((training/"training_summary.json").string(),cv::FileStorage::READ);
    ensure(summary.isOpened() && int(summary["training_attempts_complete"])==1 && int(summary["attempts"])==20736 && int(summary["comparison_feasible"])==1,"Cannot plan an incomplete or zero-success mask bank");
    std::map<int,int> masks;for(const auto& object:summary["objects"])ensure(masks.emplace(int(object["object_id"]),int(object["successful_templates"])).second,"Duplicate mask summary object");
    ensure(masks.size()==6,"Missing trained object");std::vector<Bank> banks;
    for(const auto& item:closure["rgb_banks"]) {
        const int obj=int(item["object_id"]);ensure(std::find(OBJECTS.begin(),OBJECTS.end(),obj)!=OBJECTS.end(),"Unexpected planner object");
        banks.push_back({"rgb",obj,str(item["rgb_training"]),int(item["rgb_template_count"])});
        banks.push_back({"binary_empty_mask",obj,training/("obj"+std::to_string(obj)),masks.at(obj)});
    }
    ensure(banks.size()==12,"Full union planner requires twelve banks");
    std::ofstream csv(output/"loaded_layers.csv");ensure(csv.good(),"Cannot create loaded geometry CSV");
    csv<<"arm,object_id,class_id,template_id,level,width,height,min_x,min_y,max_x,max_y,actual_features\n";
    std::vector<pad::Layer> all;
    for(const auto& bank:banks){auto loaded=scanBank(bank,csv);all.insert(all.end(),loaded.begin(),loaded.end());}
    csv.close();ensure(!csv.fail(),"Cannot close complete geometry CSV");
    pad::Limits limits;limits.axis=2048;limits.pixels=2097152;limits.bytes_per_pixel=512;limits.dynamic_bytes=1073741824;
    const auto plan=pad::make_plan(720,540,{{64,64,64,68}},all,{4,8},limits);
    cv::FileStorage out((output/"common_padding_plan.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
    out<<"source_size"<<std::vector<int>{720,540}<<"width"<<int(plan.width)<<"height"<<int(plan.height)<<"alignment"<<int(plan.alignment)<<"padding_ltrb"<<std::vector<int>{int(plan.padding[0]),int(plan.padding[1]),int(plan.padding[2]),int(plan.padding[3])}<<"pixels"<<double(plan.pixels)<<"estimated_dynamic_bytes"<<double(plan.estimated_bytes)<<"banks"<<12<<"loaded_layers"<<double(all.size())<<"geometry_feasible"<<1<<"development_images_decoded"<<0<<"matcher_calls"<<0;
}
int main(int argc,char** argv) {
    fs::path output;bool created=false;std::string mode="unknown";
    try {
        std::map<std::string,std::string> args;for(int i=1;i<argc;i+=2){ensure(i+1<argc,"Arguments need values");ensure(args.emplace(argv[i],argv[i+1]).second,"Duplicate argument");}
        for(const auto& item:args)ensure(item.first=="--mode" || item.first=="--output" || item.first=="--closure" || item.first=="--training","Unknown experiment argument");
        mode=args.at("--mode");ensure(mode=="train" || mode=="plan","Only reviewed training/planner modes are implemented");
        output=fs::absolute(args.at("--output"));ensure(!fs::exists(output),"Output directory must be new");fs::create_directories(output);created=true;
        std::ofstream(output/".gitignore")<<"*\n";cv::setNumThreads(1);
#ifdef _OPENMP
        omp_set_num_threads(4);omp_set_dynamic(0);
#endif
        cv::FileStorage closure(args.at("--closure"),cv::FileStorage::READ);ensure(closure.isOpened() && str(closure["version"])=="silhouette_empty_mask_input_closure_v1","Missing reviewed successor input closure");
        const auto began=std::chrono::steady_clock::now();
        if(mode=="train")trainAll(closure,output,began);else planAll(closure,fs::absolute(args.at("--training")),output);
        return 0;
    }catch(const std::exception& error) {
        std::cerr<<"SILHOUETTE EXPERIMENT FAILED: "<<error.what()<<'\n';
        if(created)try{cv::FileStorage failure((output/"failure.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);failure<<"incomplete"<<1<<"mode"<<mode<<"reason"<<error.what()<<"missing_frames_are_not_negatives"<<1;}catch(...){}
        return 1;
    }
}

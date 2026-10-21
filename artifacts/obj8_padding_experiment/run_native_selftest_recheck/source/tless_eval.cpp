// Exploratory adapter only: keeps dataset policy and NMS outside the matcher.
#include "line2Dup.h"
#include "eval_metrics.hpp"
#include <opencv2/imgcodecs.hpp>
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <zlib.h>
#ifdef _OPENMP
#include <omp.h>
#endif

namespace fs=std::filesystem;
using namespace public_eval;
static const std::string CLASS="tless_object_1";
struct Frame { std::string split,rgb,mask; int scene=0,image=0; std::vector<GroundTruth> gt; };
struct TemplateMeta { int id=-1,image=0,tl_x=0,tl_y=0; float angle=0,scale=1; Box silhouette; std::string class_id; };
struct Config {
    int features=32,angle_step=30,border=16,padding=64;
    double coarse=85,nms=0.3,overlap=0.5,min_visibility=0.5,selected=85;
    std::vector<double> scales={0.75,1.0,1.5,2.0};
    std::vector<double> thresholds={85};
};
static Box boxNode(const cv::FileNode& n) {
    if(n.size()!=4) throw std::runtime_error("Expected xywh box");
    return {double(n[0]),double(n[1]),double(n[2]),double(n[3])};
}
static void writeBox(cv::FileStorage& out,const std::string& name,Box b) { out<<name<<"["<<b.x<<b.y<<b.w<<b.h<<"]"; }
static std::string str(const cv::FileNode& n) { return std::string(n); }
static std::vector<int> readObjectIds(const cv::FileNode& node) {
    std::vector<int> ids; for(const auto& n:node) ids.push_back(int(n)); return ids;
}
static cv::FileStorage openDatasetIndex(const fs::path& root) {
    std::ifstream file(root/"index.json"); if(!file) throw std::runtime_error("Cannot read dataset index");
    std::string text((std::istreambuf_iterator<char>(file)),std::istreambuf_iterator<char>());
    // Test-instance mask fields are intentionally null in schema2. OpenCV's JSON
    // reader rejects null, while the adapter only needs the fields that remain.
    bool quoted=false,escaped=false;
    for(size_t at=0;at<text.size();++at) {
        const char ch=text[at];
        if(quoted) { if(escaped) escaped=false; else if(ch=='\\') escaped=true; else if(ch=='\"') quoted=false; continue; }
        if(ch=='\"') { quoted=true; continue; }
        if(text.compare(at,4,"null")==0) { text.replace(at,4,"\"\""); ++at; }
    }
    cv::FileStorage in(text,cv::FileStorage::READ|cv::FileStorage::MEMORY);
    if(!in.isOpened()) throw std::runtime_error("Cannot parse dataset index");
    return in;
}
static std::vector<int> datasetObjects(const fs::path& root,const std::string& key,const std::vector<int>& fallback={1}) {
    auto in=openDatasetIndex(root);
    const auto node=in[key]; return node.empty()?fallback:readObjectIds(node);
}
static std::string classForObject(int obj) { return "tless_object_"+std::to_string(obj); }
static std::vector<Frame> readFrames(const fs::path& root,bool training,const std::string& split,const std::vector<int>& targets) {
    auto in=openDatasetIndex(root);
    std::set<int> targetSet(targets.begin(),targets.end());
    std::vector<Frame> frames;
    const bool tiny=(in["schema_version"].empty() || int(in["schema_version"])<2);
    const std::string desiredSplit=(!tiny && split=="heldout")?"heldout_scene":split;
    for(const auto& n:in[training?"training":"test"]) {
        if(!training && str(n["split"])!=desiredSplit) continue;
        int target=0;
        if(training) {
            target=n["target_obj_id"].empty()?0:int(n["target_obj_id"]);
            if(target==0 && !n["instances"].empty()) target=int(n["instances"][0]["obj_id"]);
        }
        if(training && !targetSet.count(target)) continue;
        Frame f;f.split=str(n["split"]);f.rgb=str(n["rgb"]);f.scene=int(n["scene_id"]);f.image=int(n["image_id"]);
        for(const auto& a:n["instances"]) {
            const int object=int(a["obj_id"]); if(!targetSet.count(object)) continue;
            f.gt.push_back({int(a["gt_id"]),boxNode(a["bbox_obj"]),double(a["visib_fract"]),classForObject(object)});
            if(training) f.mask=str(a["mask"]);
        }
        if(training && f.mask.empty() && !n["instances"].empty()) f.mask=str(n["instances"][0]["mask"]);
        if(training && (f.gt.size()!=1 || f.mask.empty())) throw std::runtime_error("Training requires one target and its official mask");
        if(!training || !f.gt.empty()) frames.push_back(f);
    }
    const size_t expected = tiny ? (training?72u:16u) : (training?72u*targets.size():(split=="development"?400u:400u));
    if(frames.size()!=expected) throw std::runtime_error("Unexpected frozen split size; refusing a silently changed dataset");
    return frames;
}
static cv::Rect maskBox(const cv::Mat& mask) {
    std::vector<cv::Point> points;cv::findNonZero(mask,points);
    if(points.empty()) throw std::runtime_error("Empty object mask");
    return cv::boundingRect(points);
}
static std::string frameKey(const Frame& f) { return "s"+std::to_string(f.scene)+"_i"+std::to_string(f.image); }
static void writeConfig(cv::FileStorage& out,const Config& c) {
    out<<"features"<<c.features<<"angle_step"<<c.angle_step<<"scales"<<c.scales<<"pyramid_T"<<std::vector<int>{4,8};
    out<<"weak_threshold"<<20<<"strong_threshold"<<40<<"training_border"<<c.border<<"input_padding"<<c.padding;
    out<<"coarse_threshold"<<c.coarse<<"post_threshold_grid"<<c.thresholds<<"selected_post_threshold"<<c.selected;
    out<<"nms_iou"<<c.nms<<"match_iou"<<c.overlap<<"eligible_visibility"<<c.min_visibility;
    out<<"score_semantics"<<"Coarse candidate score strictly > fixed coarse_threshold; refined scores >= coarse_threshold. Post score filter >= selected_post_threshold. Filtering cached fixed-coarse results is not equivalent to match(selected_post_threshold), because intermediate pyramid candidate filtering may differ.";
    out<<"ordering"<<"score descending, class_id ascending, template_id ascending, match_y ascending, match_x ascending, then bbox y/x/w/h";
    out<<"nms_rule"<<"Adapter only; within each class suppress IoU strictly > nms_iou. No candidate truncation.";
    out<<"ignore_rule"<<"Eligible GT first, greedy one-to-one; then each low-visibility GT may ignore at most one remaining detection by IoU>=match_iou. Extra duplicates remain FP.";
}
static Config readConfig(const cv::FileStorage& in) {
    Config c;c.features=int(in["features"]);c.selected=double(in["selected_post_threshold"]);c.coarse=double(in["coarse_threshold"]);c.nms=double(in["nms_iou"]);c.overlap=double(in["match_iou"]);c.min_visibility=double(in["eligible_visibility"]);c.padding=int(in["input_padding"]);
    c.angle_step=int(in["angle_step"]);c.border=int(in["training_border"]);in["scales"]>>c.scales;in["post_threshold_grid"]>>c.thresholds;
    if((c.coarse!=50 && c.coarse!=85) || c.nms!=0.3 || c.overlap!=0.5 || c.min_visibility!=0.5 || c.padding!=64 || c.thresholds.empty())throw std::runtime_error("Unsupported changed evaluation policy; create and review an explicit new adapter version");
    for(double t:c.thresholds)if(t<c.coarse)throw std::runtime_error("Post threshold below fixed coarse threshold");
    return c;
}
static void writeMeta(const fs::path& path,const std::vector<TemplateMeta>& meta) {
    cv::FileStorage out(path.string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);out<<"templates"<<"[";
    for(const auto& m:meta) { out<<"{"<<"class_id"<<m.class_id<<"template_id"<<m.id<<"training_image_id"<<m.image<<"angle"<<m.angle<<"scale"<<m.scale<<"tl_x"<<m.tl_x<<"tl_y"<<m.tl_y;writeBox(out,"warped_mask_bbox",m.silhouette);out<<"}"; }
    out<<"]";
}
static std::vector<TemplateMeta> readMeta(const fs::path& path) {
    cv::FileStorage in(path.string(),cv::FileStorage::READ);if(!in.isOpened()) throw std::runtime_error("Cannot read template metadata");
    std::vector<TemplateMeta> result;
    for(const auto& n:in["templates"]) { TemplateMeta m;m.class_id=n["class_id"].empty()?CLASS:str(n["class_id"]);m.id=int(n["template_id"]);m.image=int(n["training_image_id"]);m.angle=float(n["angle"]);m.scale=float(n["scale"]);m.tl_x=int(n["tl_x"]);m.tl_y=int(n["tl_y"]);m.silhouette=boxNode(n["warped_mask_bbox"]);result.push_back(m); }
    std::map<std::string,int> expected; for(const auto& m:result) if(m.id!=expected[m.class_id]++) throw std::runtime_error("Noncontiguous template metadata");
    std::sort(result.begin(),result.end(),[](const auto& a,const auto& b){return a.class_id!=b.class_id?a.class_id<b.class_id:a.id<b.id;});
    return result;
}
static std::vector<TemplateMeta> train(line2Dup::Detector& detector,const fs::path& root,const fs::path& output,const Config& c,const std::vector<int>& objects) {
    std::ofstream csv(output/"template_attempts.csv");
    csv<<"class_id,training_image,angle,scale,success,template_id,source_crop_x,source_crop_y,source_crop_w,source_crop_h,canvas,mask_x,mask_y,mask_w,mask_h,templ_tl_x,templ_tl_y,features_l0,features_l1,error\n";
    std::vector<TemplateMeta> meta;
    std::map<std::string,int> expected;
    for(const auto& frame:readFrames(root,true,"",objects)) {
        const auto image=cv::imread((root/frame.rgb).string(),cv::IMREAD_GRAYSCALE);
        const auto mask=cv::imread((root/frame.mask).string(),cv::IMREAD_GRAYSCALE);
        if(image.empty() || mask.empty() || image.size()!=mask.size()) throw std::runtime_error("Invalid training RGB/mask");
        const auto roi=maskBox(mask);const auto crop=image(roi),crop_mask=mask(roi);
        for(double scale:c.scales) for(int angle=0;angle<360;angle+=c.angle_step) {
            int side=int(std::ceil(std::hypot(roi.width,roi.height)*scale))+2*c.border;
            side=(side+15)/16*16;
            cv::Mat transform=cv::getRotationMatrix2D({roi.width/2.f,roi.height/2.f},angle,scale);
            transform.at<double>(0,2)+=side/2.0-roi.width/2.0;
            transform.at<double>(1,2)+=side/2.0-roi.height/2.0;
            cv::Mat warped,warped_mask;
            cv::warpAffine(crop,warped,transform,{side,side},cv::INTER_LINEAR,cv::BORDER_CONSTANT,cv::Scalar(0));
            cv::warpAffine(crop_mask,warped_mask,transform,{side,side},cv::INTER_NEAREST,cv::BORDER_CONSTANT,cv::Scalar(0));
            const auto silhouette=maskBox(warped_mask);int id=-1;std::string error;
            const std::string classId=frame.gt.front().class_id;
            try { id=detector.addTemplate(warped,classId,warped_mask);if(id<0)error="insufficient_features"; }
            catch(const cv::Exception&) { error="opencv_exception"; }
            int tx=0,ty=0,n0=0,n1=0;
            if(id>=0) {
                const auto& pyramid=detector.getTemplates(classId,id);tx=pyramid[0].tl_x;ty=pyramid[0].tl_y;n0=int(pyramid[0].features.size());n1=int(pyramid[1].features.size());
                if(id!=expected[classId]++) throw std::runtime_error("Template ID/metadata mismatch");
                meta.push_back({id,frame.image,tx,ty,float(angle),float(scale),{double(silhouette.x),double(silhouette.y),double(silhouette.width),double(silhouette.height)},classId});
            }
            csv<<classId<<','<<frame.image<<','<<angle<<','<<scale<<','<<(id>=0)<<','<<id<<','<<roi.x<<','<<roi.y<<','<<roi.width<<','<<roi.height<<','<<side<<','<<silhouette.x<<','<<silhouette.y<<','<<silhouette.width<<','<<silhouette.height<<','<<tx<<','<<ty<<','<<n0<<','<<n1<<','<<error<<'\n';
        }
        std::cout<<"TRAIN image "<<frame.image<<" cumulative successful "<<meta.size()<<'\n';
    }
    if(meta.empty()) throw std::runtime_error("No templates extracted; retain failures and revise development config explicitly");
    detector.writeClasses((output/"templates_%s.yml.gz").string());writeMeta(output/"template_metadata.json",meta);
    return meta;
}
static const TemplateMeta& findMeta(const std::vector<TemplateMeta>& meta,const std::string& classId,int id) {
    const auto it=std::lower_bound(meta.begin(),meta.end(),std::make_pair(classId,id),[](const auto& t,const auto& key){return t.class_id!=key.first?t.class_id<key.first:t.id<key.second;});
    if(it!=meta.end() && it->class_id==classId && it->id==id)return *it;
    throw std::runtime_error("Unknown matched template");
}
static std::vector<Detection> convert(const std::vector<line2Dup::Match>& matches,const std::vector<TemplateMeta>& meta,int padding) {
    std::vector<Detection> out;out.reserve(matches.size());
    for(const auto& m:matches) {
        if(m.template_id<0) throw std::runtime_error("Unknown matched template");
        const auto& t=findMeta(meta,m.class_id,m.template_id);Detection d;
        d.class_id=m.class_id;
        d.box=boxAtMatch(m.x,m.y,padding,t.silhouette,t.tl_x,t.tl_y);d.score=m.similarity;d.template_id=m.template_id;d.match_x=m.x;d.match_y=m.y;
        if(!std::isfinite(d.score)) throw std::runtime_error("Nonfinite candidate score");
        out.push_back(d);
    }
    std::sort(out.begin(),out.end(),canonicalLess);return out;
}
static void writeRaw(const fs::path& output,const Frame& frame,const std::string& variant,const std::vector<Detection>& raw,const std::vector<TemplateMeta>& meta) {
    const auto key=frameKey(frame)+"_"+variant;
    const auto path=output/(key+"_raw.csv.gz");
    gzFile archive=gzopen(path.string().c_str(),"wb1");
    if(!archive)throw std::runtime_error("Cannot open gzip raw candidate archive");
    std::string buffer="scene,image,variant,class_id,rank,score,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h\n";
    size_t uncompressed_bytes=0;
    auto flush=[&]() {
        if(buffer.empty())return;
        const int written=gzwrite(archive,buffer.data(),unsigned(buffer.size()));
        if(written!=int(buffer.size()))throw std::runtime_error("Cannot write complete raw candidate gzip block");
        uncompressed_bytes+=buffer.size();buffer.clear();
    };
    try {
        for(size_t i=0;i<raw.size();++i) {const auto& d=raw[i];const auto& t=findMeta(meta,d.class_id,d.template_id);
            std::ostringstream row;row<<std::setprecision(17)<<frame.scene<<','<<frame.image<<','<<variant<<','<<d.class_id<<','<<i<<','<<d.score<<','<<d.template_id<<','<<t.image<<','<<t.angle<<','<<t.scale<<','<<d.match_x<<','<<d.match_y<<','<<d.box.x<<','<<d.box.y<<','<<d.box.w<<','<<d.box.h<<'\n';
            buffer+=row.str();if(buffer.size()>=65536)flush();
        }flush();
    }catch(...){gzclose(archive);throw;}
    if(gzclose(archive)!=Z_OK)throw std::runtime_error("Cannot finalize raw candidate gzip archive");
    cv::FileStorage manifest((output/(key+"_raw_manifest.json")).string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
    std::set<std::string> classSet;for(const auto& t:meta)classSet.insert(t.class_id);const std::vector<std::string> classIds(classSet.begin(),classSet.end());
    manifest<<"scene_id"<<frame.scene<<"image_id"<<frame.image<<"rgb"<<frame.rgb<<"variant"<<variant<<"class_id"<<(classIds.size()==1?classIds.front():"multiple classes; see class_ids")<<"class_ids"<<classIds<<"raw_candidate_count"<<int(raw.size())<<"format"<<"gzip CSV; all candidates retained, 17 significant score digits"<<"path"<<path.generic_string()<<"compressed_bytes"<<double(fs::file_size(path))<<"uncompressed_bytes"<<double(uncompressed_bytes)<<"zlib_version"<<ZLIB_VERSION;
}
static void gzipSelfTest(const fs::path& output) {
    Frame frame; frame.rgb="synthetic/no-image-read";
    std::vector<TemplateMeta> meta={{0,7,0,0,30,1.5,{1,2,3,4},CLASS}};
    std::vector<Detection> raw;
    for(int i=0;i<2048;++i) { Detection d;d.class_id=CLASS;d.template_id=0;d.match_x=i;d.match_y=-i;d.score=std::nextafter(85.f+float(i%10),100.f);d.box={i-0.5,-i+0.25,3,4};raw.push_back(d); }
    writeRaw(output,frame,"roundtrip",raw,meta); writeRaw(output,frame,"empty",{},meta);
    gzFile input=gzopen((output/"s0_i0_roundtrip_raw.csv.gz").string().c_str(),"rb");if(!input)throw std::runtime_error("Cannot read gzip selftest archive");
    std::string recovered;char block[8192];int count;
    while((count=gzread(input,block,sizeof block))>0)recovered.append(block,size_t(count));
    if(count<0 || gzclose(input)!=Z_OK)throw std::runtime_error("Gzip selftest decode failed");
    std::stringstream lines(recovered);std::string row;std::getline(lines,row);size_t rank=0;
    while(std::getline(lines,row)) {
        std::vector<std::string> cells;std::stringstream line(row);std::string cell;while(std::getline(line,cell,','))cells.push_back(cell);
        if(rank>=raw.size() || cells.size()!=16)throw std::runtime_error("Gzip selftest row count/width mismatch");
        const auto& d=raw[rank];
        if(std::stoul(cells[4])!=rank || cells[3]!=d.class_id || std::stof(cells[5])!=d.score || std::stoi(cells[6])!=d.template_id || std::stoi(cells[10])!=d.match_x || std::stoi(cells[11])!=d.match_y || std::stod(cells[12])!=d.box.x || std::stod(cells[13])!=d.box.y || std::stod(cells[14])!=d.box.w || std::stod(cells[15])!=d.box.h)throw std::runtime_error("Gzip selftest exact candidate roundtrip failed");
        ++rank;
    }
    if(rank!=raw.size() || recovered.size()<65536)throw std::runtime_error("Gzip selftest did not exercise all candidates and batch flush");
    cv::FileStorage result((output/"gzip_self_test.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);result<<"pass"<<1<<"exact_rows"<<int(rank)<<"recovered_bytes"<<int(recovered.size())<<"empty_archive_written"<<1;
    std::cout<<"PASS gzip exact float32/bbox/class/identity roundtrip, 2048 rows and empty archive\n";
}
struct FrameRun { Frame frame;std::vector<Detection> raw;bool equal=false;size_t fused_count=0;double fallback_ms=0,fused_ms=0; };
static std::vector<FrameRun> runFrames(line2Dup::Detector& detector,const std::vector<TemplateMeta>& meta,const fs::path& root,const fs::path& output,const std::string& split,const Config& c,const std::vector<int>& objects,bool pilot=false) {
    line2Dup::MatchOptions fallback,fused;fallback.fused_local_search=false;fused.fused_local_search=true;
    line2Dup::MatchWorkspace a,b;std::vector<FrameRun> runs;
    std::ofstream equality(output/"candidate_equality.csv");equality<<"scene,image,fallback_count,fused_count,exact_multiset_equal,fallback_match_ms,fused_match_ms\n";
    std::vector<std::string> classes;for(int object:objects)classes.push_back(classForObject(object));
    std::set<int> visitedScenes;
    for(const auto& frame:readFrames(root,false,split,objects)) {
        if(pilot && !visitedScenes.insert(frame.scene).second)continue;
        const auto image=cv::imread((root/frame.rgb).string(),cv::IMREAD_GRAYSCALE);if(image.empty())throw std::runtime_error("Missing test image");
        const int right=c.padding+(16-(image.cols+2*c.padding)%16)%16;
        const int bottom=c.padding+(16-(image.rows+2*c.padding)%16)%16;
        cv::Mat padded;cv::copyMakeBorder(image,padded,c.padding,bottom,c.padding,right,cv::BORDER_CONSTANT,cv::Scalar(0));
        const auto a0=std::chrono::steady_clock::now();const auto fallbackMatches=detector.match(padded,float(c.coarse),a,fallback,nullptr,classes);const auto a1=std::chrono::steady_clock::now();
        auto raw=convert(fallbackMatches,meta,c.padding);
        const auto b0=std::chrono::steady_clock::now();const auto fusedMatches=detector.match(padded,float(c.coarse),b,fused,nullptr,classes);const auto b1=std::chrono::steady_clock::now();
        auto other=convert(fusedMatches,meta,c.padding);
        const double fallbackMs=std::chrono::duration<double,std::milli>(a1-a0).count(),fusedMs=std::chrono::duration<double,std::milli>(b1-b0).count();
        bool equal=equalCandidates(raw,other);
        writeRaw(output,frame,"fallback",raw,meta);writeRaw(output,frame,"fused",other,meta);
        equality<<frame.scene<<','<<frame.image<<','<<raw.size()<<','<<other.size()<<','<<equal<<','<<fallbackMs<<','<<fusedMs<<'\n';
        runs.push_back({frame,std::move(raw),equal,other.size(),fallbackMs,fusedMs});
        std::cout<<"MATCH "<<split<<' '<<frameKey(frame)<<" candidates "<<runs.back().raw.size()<<" exact equality "<<equal<<'\n';
    }return runs;
}
static std::vector<Detection> postprocess(const std::vector<Detection>& raw,const Config& c,double threshold) {
    if(threshold<c.coarse)throw std::runtime_error("Post threshold below coarse threshold");
    std::vector<Detection> selected;for(const auto& d:raw)if(d.score>=threshold)selected.push_back(d);return nms(std::move(selected),c.nms);
}
static void add(Counts& a,const Counts& b) {a.tp+=b.tp;a.fp+=b.fp;a.fn+=b.fn;a.gt+=b.gt;a.ignored+=b.ignored;a.matched_iou_sum+=b.matched_iou_sum;}
static Counts evaluateClass(const std::vector<Detection>& detections,const std::vector<GroundTruth>& gt,const std::string& classId,double overlap,bool eligible,double visibility) {
    std::vector<Detection> d; for(const auto& item:detections) if(item.class_id==classId || item.class_id.empty()) d.push_back(item);
    std::vector<GroundTruth> g; for(const auto& item:gt) if(item.class_id==classId || item.class_id.empty()) g.push_back(item);
    return evaluate(std::move(d),g,overlap,eligible,visibility);
}
static double precision(const Counts& c) {return c.tp+c.fp?double(c.tp)/(c.tp+c.fp):0;}
static double recall(const Counts& c) {return c.gt?double(c.tp)/c.gt:0;}
static double f1(const Counts& c) {return 2*c.tp+c.fp+c.fn?2.0*c.tp/(2*c.tp+c.fp+c.fn):0;}
static Counts aggregate(const std::vector<FrameRun>& runs,const Config& c,double threshold,bool eligible) {
    Counts total;for(const auto& r:runs)add(total,evaluate(postprocess(r.raw,c,threshold),r.frame.gt,c.overlap,eligible,c.min_visibility));return total;
}
static double selectThreshold(const std::vector<FrameRun>& runs,const Config& c,const fs::path& output) {
    std::ofstream csv(output/"development_thresholds.csv");csv<<"post_threshold,nms_iou,tp,fp,fn,gt,precision,recall,f1\n";
    Counts best;double chosen=-1;
    for(double t:c.thresholds) {const auto counts=aggregate(runs,c,t,false);
        csv<<t<<','<<c.nms<<','<<counts.tp<<','<<counts.fp<<','<<counts.fn<<','<<counts.gt<<','<<precision(counts)<<','<<recall(counts)<<','<<f1(counts)<<'\n';
        if(chosen<0 || f1(counts)>f1(best) || (f1(counts)==f1(best) && (precision(counts)>precision(best) || (precision(counts)==precision(best) && t>chosen)))) {best=counts;chosen=t;}
    }return chosen;
}
static void writeCounts(cv::FileStorage& out,const std::string& key,const Counts& c) {out<<key<<"{"<<"tp"<<c.tp<<"fp"<<c.fp<<"fn"<<c.fn<<"gt"<<c.gt<<"ignored"<<c.ignored<<"precision"<<precision(c)<<"recall"<<recall(c)<<"f1"<<f1(c)<<"matched_iou_sum"<<c.matched_iou_sum<<"mean_tp_iou"<<(c.tp?c.matched_iou_sum/c.tp:0)<<"}";}
static bool report(const std::vector<FrameRun>& runs,const Config& c,const fs::path& root,const fs::path& output) {
    fs::create_directories(output/"failure_images");std::ofstream csv(output/"selected_detections.csv");
    csv<<"scene,image,rank,class_id,score,template_id,bbox_x,bbox_y,bbox_w,bbox_h,allGT_label,allGT_id,eligible_label,eligibleGT_id\n";
    cv::FileStorage json((output/"metrics.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
    writeConfig(json,c);json<<"quality_source"<<"fallback candidates; fused comparison is equivalence evidence, not a quality improvement"<<"frames"<<"[";
    Counts total_all,total_eligible;int negative_frames=0,negative_with_fp=0,negative_fp=0;bool equal=true;
    std::map<std::string,Counts> class_all,class_eligible; std::map<int,Counts> scene_all,scene_eligible;
    std::map<std::string,std::array<int,3>> class_negatives;std::map<int,std::array<int,3>> scene_negatives;
    std::set<std::string> classes; for(const auto& r:runs) for(const auto& g:r.frame.gt) classes.insert(g.class_id); for(const auto& r:runs) for(const auto& d:r.raw) classes.insert(d.class_id);
    for(const auto& r:runs) {
        auto kept=postprocess(r.raw,c,c.selected);const auto all=evaluate(kept,r.frame.gt,c.overlap,false,c.min_visibility);
        const auto eligible=evaluate(kept,r.frame.gt,c.overlap,true,c.min_visibility);add(total_all,all);add(total_eligible,eligible);add(scene_all[r.frame.scene],all);add(scene_eligible[r.frame.scene],eligible);equal=equal&&r.equal;
        for(const auto& classId:classes) {
            const auto perClass=evaluateClass(kept,r.frame.gt,classId,c.overlap,false,c.min_visibility);
            add(class_all[classId],perClass); add(class_eligible[classId],evaluateClass(kept,r.frame.gt,classId,c.overlap,true,c.min_visibility));
            if(perClass.gt==0){auto& neg=class_negatives[classId];++neg[0];if(perClass.fp)++neg[1];neg[2]+=perClass.fp;}
        }
        if(r.frame.gt.empty()){++negative_frames;negative_fp+=all.fp;if(all.fp)++negative_with_fp;auto& neg=scene_negatives[r.frame.scene];++neg[0];if(all.fp)++neg[1];neg[2]+=all.fp;}
        json<<"{"<<"scene_id"<<r.frame.scene<<"image_id"<<r.frame.image<<"split"<<r.frame.split<<"rgb"<<r.frame.rgb<<"raw_count"<<int(r.raw.size())<<"fused_raw_count"<<int(r.fused_count)<<"exact_candidate_equality"<<int(r.equal)<<"selected_count"<<int(kept.size())<<"fallback_match_ms"<<r.fallback_ms<<"fused_match_ms"<<r.fused_ms;
        writeCounts(json,"allGT",all);writeCounts(json,"visibility_ge_0_5",eligible);
        json<<"ground_truth"<<"[";for(const auto& g:r.frame.gt){json<<"{"<<"gt_id"<<g.id<<"class_id"<<g.class_id<<"visibility"<<g.visibility;writeBox(json,"bbox_obj",g.box);json<<"}";}json<<"]"<<"detections"<<"[";
        for(size_t i=0;i<kept.size();++i){const auto& d=kept[i];
            json<<"{"<<"rank"<<int(i)<<"class_id"<<d.class_id<<"score"<<d.score<<"template_id"<<d.template_id;writeBox(json,"bbox_obj",d.box);json<<"allGT_label"<<all.labels[i]<<"allGT_id"<<all.gt_ids[i]<<"eligible_label"<<eligible.labels[i]<<"eligibleGT_id"<<eligible.gt_ids[i]<<"}";
            csv<<r.frame.scene<<','<<r.frame.image<<','<<i<<','<<d.class_id<<','<<d.score<<','<<d.template_id<<','<<d.box.x<<','<<d.box.y<<','<<d.box.w<<','<<d.box.h<<','<<all.labels[i]<<','<<all.gt_ids[i]<<','<<eligible.labels[i]<<','<<eligible.gt_ids[i]<<'\n';
        }json<<"]";
        if(all.fp || all.fn || !r.equal) {
            auto image=cv::imread((root/r.frame.rgb).string(),cv::IMREAD_COLOR);
            for(const auto& g:r.frame.gt)cv::rectangle(image,cv::Rect(cvRound(g.box.x),cvRound(g.box.y),cvRound(g.box.w),cvRound(g.box.h)),{0,255,0},2);
            for(size_t i=0;i<kept.size();++i){const auto& d=kept[i];cv::rectangle(image,cv::Rect(cvRound(d.box.x),cvRound(d.box.y),cvRound(d.box.w),cvRound(d.box.h)),all.labels[i]=="TP"?cv::Scalar(255,180,0):cv::Scalar(0,0,255),1);}
            std::ostringstream label;label<<"TP "<<all.tp<<" FP "<<all.fp<<" FN "<<all.fn<<" threshold "<<c.selected;
            cv::putText(image,label.str(),{8,22},cv::FONT_HERSHEY_SIMPLEX,0.5,{0,0,255},1);
            const auto path=output/"failure_images"/(frameKey(r.frame)+".png");if(!cv::imwrite(path.string(),image))throw std::runtime_error("Cannot save failure image");json<<"failure_image"<<path.generic_string();
        }json<<"}";
    }json<<"]";writeCounts(json,"allGT_total",total_all);writeCounts(json,"visibility_ge_0_5_total",total_eligible);
    json<<"all_frames_exact_candidate_equality"<<int(equal)<<"negative_frames"<<negative_frames<<"negative_frames_with_fp"<<negative_with_fp<<"negative_fp"<<negative_fp;
    const auto columns=",split,tp,fp,fn,gt,ignored,precision,recall,f1,matched_iou_sum,mean_tp_iou,negative_frames,negative_frames_with_fp,negative_fp\n";
    auto csvCounts=[&](std::ostream& out,const auto& key,const char* split,const Counts& a,const std::array<int,3>& neg){out<<key<<','<<split<<','<<a.tp<<','<<a.fp<<','<<a.fn<<','<<a.gt<<','<<a.ignored<<','<<precision(a)<<','<<recall(a)<<','<<f1(a)<<','<<a.matched_iou_sum<<','<<(a.tp?a.matched_iou_sum/a.tp:0)<<','<<neg[0]<<','<<neg[1]<<','<<neg[2]<<'\n';};
    std::ofstream byClass(output/"per_object_metrics.csv");byClass<<"class_id"<<columns;
    for(const auto& item:class_all){csvCounts(byClass,item.first,"allGT",item.second,class_negatives[item.first]);csvCounts(byClass,item.first,"visibility_ge_0_5",class_eligible[item.first],class_negatives[item.first]);}
    std::ofstream byScene(output/"per_scene_metrics.csv");byScene<<"scene_id"<<columns;
    for(const auto& item:scene_all){csvCounts(byScene,item.first,"allGT",item.second,scene_negatives[item.first]);csvCounts(byScene,item.first,"visibility_ge_0_5",scene_eligible[item.first],scene_negatives[item.first]);}
    auto writeMacro=[&](const std::string& key,const std::map<std::string,Counts>& counts){
        double p=0,r=0,f=0;for(const auto& item:counts){p+=precision(item.second);r+=recall(item.second);f+=f1(item.second);}if(!counts.empty()){p/=counts.size();r/=counts.size();f/=counts.size();}
        json<<key<<"{"<<"objects"<<int(counts.size())<<"precision"<<p<<"recall"<<r<<"f1"<<f<<"}";
    };writeMacro("allGT_object_macro",class_all);writeMacro("visibility_ge_0_5_object_macro",class_eligible);
    std::cout<<"ALL_GT TP="<<total_all.tp<<" FP="<<total_all.fp<<" FN="<<total_all.fn<<" F1="<<f1(total_all)<<" equality="<<equal<<'\n';return equal;
}
static void inspect(const fs::path& root,const fs::path& output) {
    std::ofstream csv(output/"training_and_development_sizes.csv");csv<<"partition,class_id,scene,image,bbox_w,bbox_h,visibility\n";
    const auto objects=datasetObjects(root,"development_objects");
    for(bool training:{true,false})for(const auto& f:readFrames(root,training,"development",objects))for(const auto& g:f.gt)csv<<(training?"training":"development")<<','<<g.class_id<<','<<f.scene<<','<<f.image<<','<<g.box.w<<','<<g.box.h<<','<<g.visibility<<'\n';
    std::cout<<"Wrote training/development sizes only; heldout image sizes not inspected\n";
}
static std::vector<int> parseObjects(const std::string& value) {
    std::vector<int> objects; std::stringstream stream(value); std::string item;
    while(std::getline(stream,item,',')) { if(item.empty()) throw std::runtime_error("Empty object ID"); objects.push_back(std::stoi(item)); }
    if(objects.empty()) throw std::runtime_error("No object IDs");
    std::sort(objects.begin(),objects.end()); objects.erase(std::unique(objects.begin(),objects.end()),objects.end()); return objects;
}
static void writeObjects(cv::FileStorage& out,const std::string& key,const std::vector<int>& objects) { out<<key<<objects; }
static std::vector<int> readObjects(const cv::FileStorage& in,const std::string& key,const fs::path& root) {
    const auto node=in[key]; return node.empty()?datasetObjects(root,"development_objects"):readObjectIds(node);
}
int main(int argc,char** argv) {
    try {
        std::map<std::string,std::string> args;for(int i=1;i<argc;i+=2){if(i+1>=argc)throw std::runtime_error("Arguments require values");args[argv[i]]=argv[i+1];}
        for(const auto& a:args)if(a.first!="--mode" && a.first!="--dataset" && a.first!="--output" && a.first!="--features" && a.first!="--frozen" && a.first!="--trained" && a.first!="--objects")throw std::runtime_error("Unknown argument: "+a.first);
        const auto mode=args.at("--mode");const fs::path root=fs::absolute(args.at("--dataset")),output=fs::absolute(args.at("--output"));
        if(fs::exists(output) && !fs::is_empty(output))throw std::runtime_error("Output must be fresh; refusing to overwrite a run");
        fs::create_directories(output);std::ofstream(output/".gitignore")<<"*\n";
        cv::setNumThreads(1);
#ifdef _OPENMP
        omp_set_num_threads(4);omp_set_dynamic(0);
#endif
        if(mode=="gzip-selftest"){gzipSelfTest(output);return 0;}
        if(mode=="inspect"){inspect(root,output);return 0;}
        const auto objects=args.count("--objects")?parseObjects(args.at("--objects")):datasetObjects(root,"development_objects");
        if(mode=="train" || mode=="develop" || mode=="pilot") {
            const auto allowed=datasetObjects(root,"development_objects");
            for(int object:objects)if(std::find(allowed.begin(),allowed.end(),object)==allowed.end())throw std::runtime_error("Heldout objects cannot be used in development");
        }
        Config c;if(args.count("--features")){c.features=std::stoi(args.at("--features"));if(c.features!=32 && c.features!=48)throw std::runtime_error("Only explicit 32/48 feature development configurations supported");}
        if(mode=="train") {
            line2Dup::Detector detector(c.features,{4,8},20,40);const auto meta=train(detector,root,output,c,objects);
            cv::FileStorage training((output/"training_config.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
            writeConfig(training,c);writeObjects(training,"target_objects",objects);training<<"training_directory"<<output.generic_string()<<"dataset_root"<<root.generic_string()<<"template_count"<<int(meta.size());
            std::cout<<"Template extraction complete; no matching has run\n";return 0;
        }
        if(mode=="develop" || mode=="pilot") {
            if(args.count("--features"))throw std::runtime_error("Develop reads feature settings from --trained; do not override them");
            const fs::path training=fs::absolute(args.at("--trained"));
            cv::FileStorage training_config((training/"training_config.json").string(),cv::FileStorage::READ);
            if(!training_config.isOpened() || fs::path(str(training_config["dataset_root"]))!=root)throw std::runtime_error("Missing or inconsistent training config");
            c=readConfig(training_config);c.coarse=85;c.selected=85;c.thresholds={85};const auto trainedObjects=readObjects(training_config,"target_objects",root);line2Dup::Detector detector(c.features,{4,8},20,40);
            if(trainedObjects.size()!=1) throw std::runtime_error("Current staged development requires one object per run; train with --objects <id>");
            const auto allowed=datasetObjects(root,"development_objects");for(int object:trainedObjects)if(std::find(allowed.begin(),allowed.end(),object)==allowed.end())throw std::runtime_error("Heldout objects cannot be matched in development");
            std::vector<std::string> classes;for(int object:trainedObjects)classes.push_back(classForObject(object));
            detector.readClasses(classes,(training/"templates_%s.yml.gz").string());const auto meta=readMeta(training/"template_metadata.json");
            if(detector.numTemplates()!=int(meta.size()))throw std::runtime_error("Saved template count mismatch");
            const auto runs=runFrames(detector,meta,root,output,"development",c,trainedObjects,mode=="pilot");c.selected=selectThreshold(runs,c,output);
            const bool equal=report(runs,c,root,output);
            cv::FileStorage frozen((output/(mode=="pilot"?"pilot_config.json":"frozen_config.json")).string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
            writeConfig(frozen,c);writeObjects(frozen,"target_objects",trainedObjects);frozen<<"evaluation_stage"<<(mode=="pilot"?"pilot":"development_full")<<"training_directory"<<training.generic_string()<<"dataset_root"<<root.generic_string()<<"objective"<<(mode=="pilot"?"Diagnostic pilot: first official frame of each development scene; no final authorization or recipe selection":"Fixed actual matcher threshold85/post85 baseline; no threshold search; future declared grids select max development micro-F1, ties precision then higher threshold")<<"candidate_equivalence_pass"<<int(equal)<<"template_count"<<int(meta.size());
            return equal?0:2;
        }
        if(mode=="final") {
            if(args.count("--features"))throw std::runtime_error("Final cannot override frozen features");
            cv::FileStorage frozen(args.at("--frozen"),cv::FileStorage::READ);if(!frozen.isOpened())throw std::runtime_error("Cannot open frozen config");
            if(str(frozen["evaluation_stage"])!="development_full")throw std::runtime_error("Only full development configuration can authorize final; pilots cannot");
            if(int(frozen["candidate_equivalence_pass"])!=1)throw std::runtime_error("Development equivalence failed; do not run heldout yet");
            if(fs::path(str(frozen["dataset_root"]))!=root)throw std::runtime_error("Frozen dataset root differs");
            c=readConfig(frozen);const auto frozenObjects=readObjects(frozen,"target_objects",root);
            const fs::path training=str(frozen["training_directory"]);
            const auto marker=training/"heldout_started.json";if(fs::exists(marker))throw std::runtime_error("Heldout was already started for this frozen configuration; refusing a repeat");
            cv::FileStorage lock(marker.string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);lock<<"output"<<output.generic_string()<<"frozen_config"<<fs::absolute(args.at("--frozen")).generic_string();lock.release();
            auto meta=readMeta(training/"template_metadata.json");line2Dup::Detector detector(c.features,{4,8},20,40);std::vector<std::string> classes;for(int object:frozenObjects)classes.push_back(classForObject(object));detector.readClasses(classes,(training/"templates_%s.yml.gz").string());
            if(detector.numTemplates()!=int(meta.size()))throw std::runtime_error("Saved template count mismatch");
            return report(runFrames(detector,meta,root,output,"heldout",c,frozenObjects),c,root,output)?0:2;
        }
        throw std::runtime_error("Mode must be inspect, train, pilot, develop, final, or gzip-selftest");
    }catch(const std::exception& e){std::cerr<<"ERROR "<<e.what()<<'\n';return 1;}
}

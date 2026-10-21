// Adapter-only experiment. Reuse the frozen public dataset/box/NMS/metrics
// implementation; its original main is deliberately never called here.
#define main frozen_public_evaluator_entry
#include "../public_evaluation/tless_eval.cpp"
#undef main
#include "coverage_helper.hpp"
#include "coverage_nms.hpp"
#include <cstring>
#include <tuple>
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <bcrypt.h>

namespace qc=quality_coverage;
using ValidationKey=std::pair<std::string,int>;
static void coverageRequire(bool ok,const char* what){if(!ok)throw std::runtime_error(what);}
static std::string matrixSha256(const cv::Mat& image) {
    BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;
    if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)throw std::runtime_error("SHA256 provider failed");
    DWORD objectBytes=0,returned=0;
    if(BCryptGetProperty(algorithm,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&objectBytes),sizeof(objectBytes),&returned,0)<0){BCryptCloseAlgorithmProvider(algorithm,0);throw std::runtime_error("SHA256 property failed");}
    std::vector<unsigned char> object(objectBytes),digest(32);
    NTSTATUS status=BCryptCreateHash(algorithm,&hash,object.data(),objectBytes,nullptr,0,0);
    for(int y=0;y<image.rows && status>=0;++y)status=BCryptHashData(hash,const_cast<PUCHAR>(image.ptr<unsigned char>(y)),ULONG(image.cols*image.elemSize()),0);
    if(status>=0)status=BCryptFinishHash(hash,digest.data(),ULONG(digest.size()),0);
    if(hash)BCryptDestroyHash(hash);
    BCryptCloseAlgorithmProvider(algorithm,0);
    if(status<0)throw std::runtime_error("SHA256 matrix hash failed");
    std::ostringstream out;for(auto byte:digest)out<<std::hex<<std::setfill('0')<<std::setw(2)<<int(byte);return out.str();
}
static std::vector<std::uint8_t> decodeCoreBits(const cv::Mat& bits) {
    coverageRequire(bits.type()==CV_8UC1 && !bits.empty(),"Expected nonempty CV_8UC1 core bit field");
    std::vector<std::uint8_t> labels(static_cast<std::size_t>(bits.rows)*bits.cols,qc::invalid_label);
    for(int y=0;y<bits.rows;++y)for(int x=0;x<bits.cols;++x) {
        const unsigned value=bits.ptr<unsigned char>(y)[x];if(!value)continue;
        coverageRequire((value&(value-1))==0,"Multi-bit field is spread, not unspread orientation");
        int label=0;while((1u<<label)!=value)++label;
        labels[static_cast<std::size_t>(y)*bits.cols+x]=std::uint8_t(label);
    }
    return labels;
}
static std::vector<qc::Point> sampleDense(const cv::Mat& bits,const cv::Mat& magnitude,const cv::Mat& mask) {
    coverageRequire(bits.size()==magnitude.size() && bits.size()==mask.size() && magnitude.type()==CV_32FC1 && mask.type()==CV_8UC1,"Dense field/magnitude/mask mismatch");
    const auto labels=decodeCoreBits(bits);std::vector<qc::Point> points;
    for(int cy=0;cy<bits.rows;cy+=2)for(int cx=0;cx<bits.cols;cx+=2) {
        float best=1600.f;int bx=-1,by=-1;
        for(int y=cy;y<std::min(cy+2,bits.rows);++y)for(int x=cx;x<std::min(cx+2,bits.cols);++x) {
            const auto label=labels[static_cast<std::size_t>(y)*bits.cols+x];const float strength=magnitude.ptr<float>(y)[x];
            if(mask.ptr<unsigned char>(y)[x] && label<8 && std::isfinite(strength) && strength>best){best=strength;bx=x;by=y;}
        }
        if(bx>=0)points.push_back({bx,by,labels[static_cast<std::size_t>(by)*bits.cols+bx]});
    }
    return points;
}
struct RebuiltWarp {cv::Mat image,mask,transform;cv::Rect crop;};
static RebuiltWarp rebuildWarp(const cv::Mat& image,const cv::Mat& mask,float angle,float scale,int border) {
    coverageRequire(!image.empty() && image.size()==mask.size() && image.type()==CV_8UC1 && mask.type()==CV_8UC1,"Training grayscale/mask mismatch");
    RebuiltWarp out;out.crop=maskBox(mask);const auto roi=out.crop;
    int side=int(std::ceil(std::hypot(roi.width,roi.height)*double(scale)))+2*border;side=(side+15)/16*16;
    out.transform=cv::getRotationMatrix2D({roi.width/2.f,roi.height/2.f},angle,scale);
    out.transform.at<double>(0,2)+=side/2.0-roi.width/2.0;out.transform.at<double>(1,2)+=side/2.0-roi.height/2.0;
    cv::warpAffine(image(roi),out.image,out.transform,{side,side},cv::INTER_LINEAR,cv::BORDER_CONSTANT,cv::Scalar(0));
    cv::warpAffine(mask(roi),out.mask,out.transform,{side,side},cv::INTER_NEAREST,cv::BORDER_CONSTANT,cv::Scalar(0));return out;
}
static bool sameTemplate(const line2Dup::Template& a,const line2Dup::Template& b) {
    if(a.width!=b.width || a.height!=b.height || a.tl_x!=b.tl_x || a.tl_y!=b.tl_y || a.pyramid_level!=b.pyramid_level || a.features.size()!=b.features.size())return false;
    for(std::size_t i=0;i<a.features.size();++i)if(a.features[i].x!=b.features[i].x || a.features[i].y!=b.features[i].y || a.features[i].label!=b.features[i].label)return false;
    // theta is not serialized by core Feature::write; compare the complete saved
    // matching representation, rather than uninitialized/unsaved angle metadata.
    return true;
}
static std::map<ValidationKey,qc::PreparedTemplate> prepareBank(line2Dup::Detector& saved,const std::vector<TemplateMeta>& meta,const fs::path& root,const fs::path& output,const Config& c,const std::vector<int>& objects) {
    std::map<ValidationKey,Frame> training;
    for(const auto& frame:readFrames(root,true,"",objects))coverageRequire(training.emplace(ValidationKey(frame.gt.front().class_id,frame.image),frame).second,"Duplicate class/training image identity");
    std::map<ValidationKey,qc::PreparedTemplate> bank;line2Dup::Detector replay(c.features,{4,8},20,40);
    std::ofstream csv(output/"validation_templates.csv");csv<<"class_id,template_id,training_image,angle,scale,tl_x,tl_y,points,occupied_cells,source_rgb,source_mask,crop_x,crop_y,crop_w,crop_h,canvas,warp_sha256,mask_sha256,a00,a01,a02,a10,a11,a12,features_l0,features_l1,reason\n";csv<<std::setprecision(17);
    gzFile pointFile=gzopen((output/"validation_points.csv.gz").string().c_str(),"wb1");coverageRequire(pointFile!=nullptr,"Cannot open validation point cache");
    std::string pointBuffer="class_id,template_id,point_index,canvas_x,canvas_y,relative_x,relative_y,label,cell\n";
    auto flushPoints=[&](){coverageRequire(gzwrite(pointFile,pointBuffer.data(),unsigned(pointBuffer.size()))==int(pointBuffer.size()),"Validation point cache incomplete");pointBuffer.clear();};
    for(const auto& m:meta) {
        const auto it=training.find({m.class_id,m.image});coverageRequire(it!=training.end(),"Metadata has no trusted training source");
        const auto& frame=it->second;
        const auto image=cv::imread((root/frame.rgb).string(),cv::IMREAD_GRAYSCALE),mask=cv::imread((root/frame.mask).string(),cv::IMREAD_GRAYSCALE);
        const auto warp=rebuildWarp(image,mask,m.angle,m.scale,c.border);const auto silhouette=maskBox(warp.mask);
        coverageRequire(m.silhouette.x==silhouette.x && m.silhouette.y==silhouette.y && m.silhouette.w==silhouette.width && m.silhouette.h==silhouette.height,"Rebuilt official mask bbox differs from frozen metadata");
        const auto& original=saved.getTemplates(m.class_id,m.id);
        coverageRequire(original.size()==2 && original.front().tl_x==m.tl_x && original.front().tl_y==m.tl_y,"Saved template origin/level mismatch");
        const int replayId=replay.addTemplate(warp.image,m.class_id,warp.mask);
        coverageRequire(replayId==m.id,"Reconstructed successful ID differs from frozen bank");
        const auto& reconstructed=replay.getTemplates(m.class_id,replayId);
        coverageRequire(reconstructed.size()==original.size(),"Reconstructed pyramid size mismatch");
        for(std::size_t l=0;l<original.size();++l)coverageRequire(sameTemplate(original[l],reconstructed[l]),"Reconstructed matching template differs from frozen bank");
        line2Dup::ColorGradientPyramid gradient(warp.image,warp.mask,20,c.features,40);cv::Mat bits;gradient.quantize(bits);
        const auto points=sampleDense(bits,gradient.magnitude,warp.mask);auto prepared=qc::prepare_template(points,m.tl_x,m.tl_y);
        std::size_t occupied=0;for(auto n:prepared.cell_points)if(n)++occupied;
        csv<<m.class_id<<','<<m.id<<','<<m.image<<','<<m.angle<<','<<m.scale<<','<<m.tl_x<<','<<m.tl_y<<','<<points.size()<<','<<occupied<<','<<frame.rgb<<','<<frame.mask<<','<<warp.crop.x<<','<<warp.crop.y<<','<<warp.crop.width<<','<<warp.crop.height<<','<<warp.image.cols<<','<<matrixSha256(warp.image)<<','<<matrixSha256(warp.mask);
        for(int y=0;y<2;++y)for(int x=0;x<3;++x)csv<<','<<warp.transform.at<double>(y,x);
        csv<<','<<original[0].features.size()<<','<<original[1].features.size()<<','<<prepared.reason<<'\n';
        for(std::size_t i=0;i<points.size();++i) {
            std::ostringstream row;row<<m.class_id<<','<<m.id<<','<<i<<','<<points[i].x<<','<<points[i].y<<','<<prepared.points[i].x<<','<<prepared.points[i].y<<','<<int(points[i].label)<<','<<int(prepared.cells[i])<<'\n';pointBuffer+=row.str();if(pointBuffer.size()>=65536)flushPoints();
        }
        coverageRequire(bank.emplace(ValidationKey(m.class_id,m.id),std::move(prepared)).second,"Duplicate class/template identity");
    }
    if(!pointBuffer.empty())flushPoints();
    coverageRequire(gzclose(pointFile)==Z_OK,"Cannot close validation point cache");
    return bank;
}
static std::vector<std::string> csvCells(const std::string& row) {
    std::vector<std::string> cells;std::stringstream line(row);std::string cell;while(std::getline(line,cell,','))cells.push_back(cell);return cells;
}
static std::vector<Detection> readRawVerified(const fs::path& file,const Frame& frame,const std::string& variant,const std::vector<TemplateMeta>& meta,const Config& c) {
    gzFile gzip=gzopen(file.string().c_str(),"rb");coverageRequire(gzip!=nullptr,"Cannot open verified raw gzip");
    std::string text;char block[65536];int bytes;
    while((bytes=gzread(gzip,block,sizeof block))>0)text.append(block,std::size_t(bytes));
    const int closed=gzclose(gzip);coverageRequire(bytes>=0 && closed==Z_OK,"Raw gzip decode/CRC failed");
    std::stringstream rows(text);std::string row;std::getline(rows,row);
    coverageRequire(row=="scene,image,variant,class_id,rank,score,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h","Unexpected raw schema");
    std::vector<Detection> detections;
    while(std::getline(rows,row)) {
        const auto cells=csvCells(row);coverageRequire(cells.size()==16,"Raw CSV width mismatch");
        coverageRequire(std::stoi(cells[0])==frame.scene && std::stoi(cells[1])==frame.image && cells[2]==variant && std::stoull(cells[4])==detections.size(),"Raw frame/variant/rank mismatch");
        Detection d;d.class_id=cells[3];d.score=std::stof(cells[5]);d.template_id=std::stoi(cells[6]);d.match_x=std::stoi(cells[10]);d.match_y=std::stoi(cells[11]);d.box={std::stod(cells[12]),std::stod(cells[13]),std::stod(cells[14]),std::stod(cells[15])};
        const auto& t=findMeta(meta,d.class_id,d.template_id);const auto box=boxAtMatch(d.match_x,d.match_y,c.padding,t.silhouette,t.tl_x,t.tl_y);
        coverageRequire(std::isfinite(d.score) && d.score>=c.coarse && std::stoi(cells[7])==t.image && std::stof(cells[8])==t.angle && std::stof(cells[9])==t.scale && d.box.x==box.x && d.box.y==box.y && d.box.w==box.w && d.box.h==box.h,"Raw metadata/box/threshold mismatch");
        if(!detections.empty())coverageRequire(!canonicalLess(d,detections.back()),"Raw candidate canonical order mismatch");
        detections.push_back(d);
    }return detections;
}
static bool sameDetection(const Detection& a,const Detection& b) {
    return a.class_id==b.class_id && a.template_id==b.template_id && a.match_x==b.match_x && a.match_y==b.match_y && std::memcmp(&a.score,&b.score,sizeof(float))==0 && a.box.x==b.box.x && a.box.y==b.box.y && a.box.w==b.box.w && a.box.h==b.box.h;
}
static bool sameCoverage(const qc::Coverage& a,const qc::Coverage& b) {
    return a.verified==b.verified && a.reason==b.reason && a.points==b.points && a.supported==b.supported && a.in_bounds==b.in_bounds && a.occupied_cells==b.occupied_cells && a.cell_points==b.cell_points && a.cell_supported==b.cell_supported && a.cell_coverage==b.cell_coverage && a.balanced==b.balanced && a.unweighted==b.unweighted && a.in_bounds_fraction==b.in_bounds_fraction;
}
static qc::Candidate coverageCandidate(const Detection& d) {
    qc::Candidate result;result.score=d.score;result.class_id=d.class_id;result.template_id=d.template_id;result.x=d.match_x;result.y=d.match_y;result.box={d.box.x,d.box.y,d.box.w,d.box.h};return result;
}
class CoverageCsv {
    gzFile file_=nullptr;std::string pending_;
public:
    explicit CoverageCsv(const fs::path& path){file_=gzopen(path.string().c_str(),"wb1");coverageRequire(file_!=nullptr,"Cannot open coverage CSV");}
    void append(const std::string& row){pending_+=row;if(pending_.size()>=65536)flush();}
    void flush(){if(!pending_.empty()){coverageRequire(gzwrite(file_,pending_.data(),unsigned(pending_.size()))==int(pending_.size()),"Coverage gzip write incomplete");pending_.clear();}}
    void close(){flush();const int result=gzclose(file_);file_=nullptr;coverageRequire(result==Z_OK,"Coverage gzip close failed");}
    ~CoverageCsv(){if(file_)gzclose(file_);}
};
struct CoverageStats {Counts all,eligible;std::size_t negative_frames=0,negative_with_fp=0,negative_fp=0,baseline_gt_retained=0,baseline_tp_detection_retained=0;};
static void appendStats(CoverageStats& total,const Counts& all,const Counts& eligible,bool negative,std::size_t gt_retained,std::size_t detection_retained) {
    add(total.all,all);add(total.eligible,eligible);
    if(negative){++total.negative_frames;if(all.fp)++total.negative_with_fp;total.negative_fp+=all.fp;}
    total.baseline_gt_retained+=gt_retained;total.baseline_tp_detection_retained+=detection_retained;
}
static void writeCoverageStats(cv::FileStorage& json,const std::string& key,const CoverageStats& stats) {
    json<<key<<"{";writeCounts(json,"allGT",stats.all);writeCounts(json,"visibility_ge_0_5",stats.eligible);
    json<<"negative_frames"<<double(stats.negative_frames)<<"negative_frames_with_fp"<<double(stats.negative_with_fp)<<"negative_fp"<<double(stats.negative_fp)<<"baseline_gt_retained"<<double(stats.baseline_gt_retained)<<"baseline_tp_detection_retained"<<double(stats.baseline_tp_detection_retained)<<"}";
}
static std::size_t originalDomainCount(const qc::PreparedTemplate& object,int mx,int my,int width,int height,int padding) {
    std::size_t count=0;for(const auto& point:object.points) {
        const std::int64_t x=std::int64_t(mx)+point.x-padding,y=std::int64_t(my)+point.y-padding;
        if(x>=0 && x<width && y>=0 && y<height)++count;
    }return count;
}
static void coverageEvaluation(const fs::path& verifiedFile,const fs::path& output) {
    cv::FileStorage verified(verifiedFile.string(),cv::FileStorage::READ);
    coverageRequire(verified.isOpened() && int(verified["schema_version"])==1 && int(verified["verified"])==1 && str(verified["split"])=="development","Missing verified development-only input provenance");
    const fs::path root=str(verified["dataset_root"]),training=str(verified["training_directory"]),rawDirectory=str(verified["raw_directory"]),configFile=str(verified["config_file"]);
    const std::string trainingOriginalCore=verified["training"]["original_core_revision"].empty()?"unknown":str(verified["training"]["original_core_revision"]);
    const auto objects=readObjectIds(verified["target_objects"]);coverageRequire(objects.size()==1 && (objects[0]==1 || objects[0]==2 || objects[0]==5 || objects[0]==8 || objects[0]==12 || objects[0]==17),"One allowed development object required");
    cv::FileStorage config(configFile.string(),cv::FileStorage::READ);const auto c=readConfig(config);
    coverageRequire(c.coarse==85 && c.selected==85 && c.thresholds==std::vector<double>{85} && int(config["candidate_equivalence_pass"])==1 && (str(config["evaluation_stage"])=="pilot" || str(config["evaluation_stage"])=="development_full"),"Only frozen actual85/post85 equivalent development raw accepted");
    coverageRequire(fs::equivalent(root,fs::path(str(config["dataset_root"]))) && fs::equivalent(training,fs::path(str(config["training_directory"]))),"Verified config dataset/bank mismatch");
    const auto meta=readMeta(training/"template_metadata.json");line2Dup::Detector detector(c.features,{4,8},20,40);
    detector.readClasses({classForObject(objects[0])},(training/"templates_%s.yml.gz").string());coverageRequire(detector.numTemplates()==int(meta.size()),"Frozen template count mismatch");
    const auto trainingStart=std::chrono::steady_clock::now();const auto bank=prepareBank(detector,meta,root,output,c,objects);const auto trainingEnd=std::chrono::steady_clock::now();
    std::map<std::pair<int,int>,Frame> indexed;for(const auto& f:readFrames(root,false,"development",objects))indexed.emplace(std::make_pair(f.scene,f.image),f);
    const std::array<std::string,4> names={"baseline","coverage_050","coverage_065","coverage_080"};const std::array<double,3> policies={.5,.65,.8};
    std::array<CoverageStats,4> totals;std::map<int,std::array<CoverageStats,4>> byScene;
    std::ofstream preparation(output/"scene_preparation.csv"),perFrame(output/"per_frame_metrics.csv"),geometry(output/"bank_geometry.csv"),detectionsCsv(output/"selected_detections.csv");
    detectionsCsv<<"scene,image,policy,rank,class_id,score,template_id,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h,allGT_label,allGT_id,eligible_label,eligibleGT_id\n";detectionsCsv<<std::setprecision(17);
    preparation<<"scene,image,original_width,original_height,left,top,right,bottom,padded_width,padded_height,raw,post85,verified,unverified,full_point_queries,second_gradient_and_maps_ms,full_verify_ms,coverage_and_nms_ms\n";
    perFrame<<"scene,image,policy,tp,fp,fn,gt,precision,recall,f1,eligible_tp,eligible_fp,eligible_fn,ignored,negative_fp,baseline_gt_retained,baseline_tp_detection_retained,lazy_attempted,lazy_suppressed,lazy_point_queries\n";
    geometry<<"padded_width,padded_height,class_id,template_id,level,width,height,feature_max_x,feature_max_y,feature_extent_fits,local_interval_feasible,coarse_full_placement_feasible\n";
    std::set<std::pair<int,int>> geometrySizes,seenFrames;
    CoverageCsv csv(output/"all_post85_coverage.csv.gz");std::string header="scene,image,class_id,rank,score,template_id,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h,verified,reason,points,supported,occupied_cells,balanced,unweighted,map_in_bounds,map_in_bounds_fraction,original_in_bounds,original_in_bounds_fraction";
    for(int i=0;i<16;++i)header+=",cell_points_"+std::to_string(i);
    for(int i=0;i<16;++i)header+=",cell_supported_"+std::to_string(i);
    for(int i=0;i<16;++i)header+=",cell_coverage_"+std::to_string(i);
    csv.append(header+"\n");
    std::size_t frameCount=0,rawCount=0,pointQueries=0,unverifiedCount=0,baselineTpTotal=0;
    double scenePrepareMs=0,fullVerifyMs=0,policyMs=0;
    for(const auto& node:verified["frames"]) {
        const int scene=int(node["scene_id"]),imageId=int(node["image_id"]);const auto key=std::make_pair(scene,imageId);const auto frameIt=indexed.find(key);
        coverageRequire(frameIt!=indexed.end() && seenFrames.insert(key).second,"Verified frame is duplicated or outside development");const auto& frame=frameIt->second;
        coverageRequire(str(node["rgb"])==frame.rgb,"Verified RGB/index identity mismatch");
        const fs::path fallbackPath=str(node["fallback_raw"]),fusedPath=str(node["fused_raw"]);
        coverageRequire(fs::equivalent(fallbackPath.parent_path(),rawDirectory) && fs::equivalent(fusedPath.parent_path(),rawDirectory),"Raw path escapes verified run directory");
        const auto raw=readRawVerified(fallbackPath,frame,"fallback",meta,c),fused=readRawVerified(fusedPath,frame,"fused",meta,c);
        coverageRequire(raw.size()==std::size_t(double(node["raw_count"])) && raw.size()==fused.size(),"Verified raw row count mismatch");
        for(std::size_t i=0;i<raw.size();++i)coverageRequire(sameDetection(raw[i],fused[i]),"Frozen fallback/fused fields differ");
        const auto input=cv::imread((root/frame.rgb).string(),cv::IMREAD_GRAYSCALE);coverageRequire(!input.empty(),"Missing verified development image");
        const int right=c.padding+(16-(input.cols+2*c.padding)%16)%16,bottom=c.padding+(16-(input.rows+2*c.padding)%16)%16;
        const auto declaredPadding=node["padding"];
        coverageRequire(int(node["width"])==input.cols && int(node["height"])==input.rows && declaredPadding.size()==4 && int(declaredPadding[0])==c.padding && int(declaredPadding[1])==c.padding && int(declaredPadding[2])==right && int(declaredPadding[3])==bottom,"Verified image/padding dimensions disagree with exact baseline input");
        cv::Mat padded;cv::copyMakeBorder(input,padded,c.padding,bottom,c.padding,right,cv::BORDER_CONSTANT,cv::Scalar(0));
        // Record failures; a coverage-only experiment never changes the frozen
        // padding or repairs an infeasible baseline bank before raw-cache use.
        if(geometrySizes.insert({padded.cols,padded.rows}).second)for(const auto& m:meta)for(const auto& t:detector.getTemplates(m.class_id,m.id)) {
            int maxx=-1,maxy=-1;for(const auto& f:t.features){maxx=std::max(maxx,f.x);maxy=std::max(maxy,f.y);}
            const int iw=padded.cols>>t.pyramid_level,ih=padded.rows>>t.pyramid_level;
            const bool local=t.pyramid_level==0 ? iw-t.width-32>=32 && ih-t.height-32>=32 : true;
            const bool coarse=t.pyramid_level==1 ? iw>=maxx+1 && ih>=maxy+1 && iw%8==0 && ih%8==0 : true;
            geometry<<padded.cols<<','<<padded.rows<<','<<m.class_id<<','<<m.id<<','<<t.pyramid_level<<','<<t.width<<','<<t.height<<','<<maxx<<','<<maxy<<','<<(maxx<=t.width && maxy<=t.height)<<','<<local<<','<<coarse<<'\n';
        }
        const auto start=std::chrono::steady_clock::now();line2Dup::ColorGradientPyramid gradient(padded,cv::Mat(),20,c.features,40);cv::Mat bits;gradient.quantize(bits);
        const auto maps=qc::build_support(decodeCoreBits(bits),padded.cols,padded.rows);const auto mapsDone=std::chrono::steady_clock::now();
        std::vector<Detection> post;for(const auto& d:raw)if(d.score>=85)post.push_back(d);
        std::vector<qc::Candidate> candidates;std::vector<qc::Coverage> coverages;candidates.reserve(post.size());coverages.reserve(post.size());
        using CandidateKey=std::tuple<std::string,int,int,int>;std::map<CandidateKey,std::size_t> cached;
        std::size_t unverifiedFrame=0,queries=0;
        for(std::size_t rank=0;rank<post.size();++rank) {
            const auto& d=post[rank];const auto object=bank.find({d.class_id,d.template_id});coverageRequire(object!=bank.end(),"Matched ID missing validation-cache entry");
            const auto value=qc::evaluate(maps,object->second,d.match_x,d.match_y);const auto original=originalDomainCount(object->second,d.match_x,d.match_y,input.cols,input.rows,c.padding);
            candidates.push_back(coverageCandidate(d));coverages.push_back(value);cached.emplace(CandidateKey(d.class_id,d.template_id,d.match_x,d.match_y),rank);
            if(value.verified)queries+=value.points;else ++unverifiedFrame;
            std::ostringstream row;row<<std::setprecision(17)<<scene<<','<<imageId<<','<<d.class_id<<','<<rank<<','<<d.score<<','<<d.template_id<<','<<d.match_x<<','<<d.match_y<<','<<d.box.x<<','<<d.box.y<<','<<d.box.w<<','<<d.box.h<<','<<value.verified<<','<<value.reason<<','<<value.points<<','<<value.supported<<','<<value.occupied_cells<<','<<value.balanced<<','<<value.unweighted<<','<<value.in_bounds<<','<<value.in_bounds_fraction<<','<<original<<','<<(value.points?double(original)/value.points:0);
            for(auto n:value.cell_points)row<<','<<n;
            for(auto n:value.cell_supported)row<<','<<n;
            for(auto v:value.cell_coverage)row<<','<<v;
            row<<'\n';csv.append(row.str());
        }
        const auto fullDone=std::chrono::steady_clock::now();
        const auto baseline=postprocess(raw,c,85);const auto baselineCounts=evaluate(baseline,frame.gt,c.overlap,false,c.min_visibility);std::set<int> baselineGt;
        for(std::size_t i=0;i<baseline.size();++i)if(baselineCounts.labels[i]=="TP")baselineGt.insert(baselineCounts.gt_ids[i]);
        baselineTpTotal+=baselineCounts.tp;
        for(std::size_t p=0;p<4;++p) {
            std::vector<Detection> selected;std::size_t attempted=0,suppressed=0,lazyQueries=0;
            if(p==0)selected=baseline;
            else {
                const double threshold=policies[p-1];
                auto fromCache=[&](const qc::Candidate& d){return coverages.at(cached.at(CandidateKey(d.class_id,d.template_id,d.x,d.y)));};
                auto fresh=[&](const qc::Candidate& d){return qc::evaluate(maps,bank.at({d.class_id,d.template_id}),d.x,d.y);};
                const auto full=qc::filter_full(candidates,fromCache,threshold,c.nms),lazy=qc::filter_lazy(candidates,fresh,threshold,c.nms);
                coverageRequire(full.kept.size()==lazy.kept.size(),"Full/lazy retained count mismatch");
                for(std::size_t i=0;i<full.kept.size();++i)coverageRequire(full.kept[i].input_index==lazy.kept[i].input_index && sameCoverage(full.kept[i].coverage,lazy.kept[i].coverage),"Full/lazy identity/coverage field mismatch");
                std::vector<Detection> publicInput;for(std::size_t i=0;i<post.size();++i)if(qc::passes(coverages[i],threshold))publicInput.push_back(post[i]);const auto publicExpected=nms(publicInput,c.nms);
                coverageRequire(publicExpected.size()==lazy.kept.size(),"Shared public NMS retained count mismatch");
                for(std::size_t i=0;i<lazy.kept.size();++i){const auto& d=post.at(lazy.kept[i].input_index);coverageRequire(sameDetection(d,publicExpected[i]),"Shared public NMS original field/order mismatch");selected.push_back(d);}
                attempted=lazy.attempted;suppressed=lazy.suppressed;lazyQueries=lazy.point_queries;
            }
            const auto all=evaluate(selected,frame.gt,c.overlap,false,c.min_visibility),eligible=evaluate(selected,frame.gt,c.overlap,true,c.min_visibility);
            for(std::size_t i=0;i<selected.size();++i) {
                const auto& d=selected[i];detectionsCsv<<scene<<','<<imageId<<','<<names[p]<<','<<i<<','<<d.class_id<<','<<d.score<<','<<d.template_id<<','<<d.match_x<<','<<d.match_y<<','<<d.box.x<<','<<d.box.y<<','<<d.box.w<<','<<d.box.h<<','<<all.labels[i]<<','<<all.gt_ids[i]<<','<<eligible.labels[i]<<','<<eligible.gt_ids[i]<<'\n';
            }
            std::size_t gtRetained=0,detectionRetained=0;
            for(std::size_t i=0;i<selected.size();++i)if(all.labels[i]=="TP") {
                if(baselineGt.count(all.gt_ids[i]))++gtRetained;
                for(std::size_t b=0;b<baseline.size();++b)if(baselineCounts.labels[b]=="TP" && sameDetection(selected[i],baseline[b])){++detectionRetained;break;}
            }
            appendStats(totals[p],all,eligible,frame.gt.empty(),gtRetained,detectionRetained);appendStats(byScene[scene][p],all,eligible,frame.gt.empty(),gtRetained,detectionRetained);
            perFrame<<scene<<','<<imageId<<','<<names[p]<<','<<all.tp<<','<<all.fp<<','<<all.fn<<','<<all.gt<<','<<precision(all)<<','<<recall(all)<<','<<f1(all)<<','<<eligible.tp<<','<<eligible.fp<<','<<eligible.fn<<','<<eligible.ignored<<','<<(frame.gt.empty()?all.fp:0)<<','<<gtRetained<<','<<detectionRetained<<','<<attempted<<','<<suppressed<<','<<lazyQueries<<'\n';
        }
        const auto policiesDone=std::chrono::steady_clock::now();const double prepMs=std::chrono::duration<double,std::milli>(mapsDone-start).count(),verifyMs=std::chrono::duration<double,std::milli>(fullDone-mapsDone).count(),nmsMs=std::chrono::duration<double,std::milli>(policiesDone-fullDone).count();
        preparation<<scene<<','<<imageId<<','<<input.cols<<','<<input.rows<<','<<c.padding<<','<<c.padding<<','<<right<<','<<bottom<<','<<padded.cols<<','<<padded.rows<<','<<raw.size()<<','<<post.size()<<','<<post.size()-unverifiedFrame<<','<<unverifiedFrame<<','<<queries<<','<<prepMs<<','<<verifyMs<<','<<nmsMs<<'\n';
        ++frameCount;rawCount+=raw.size();pointQueries+=queries;unverifiedCount+=unverifiedFrame;scenePrepareMs+=prepMs;fullVerifyMs+=verifyMs;policyMs+=nmsMs;
        std::cout<<"COVERAGE development "<<frameKey(frame)<<" complete_post85="<<post.size()<<" no heldout\n";
    }
    coverageRequire(frameCount==verified["frames"].size() && frameCount>0,"Verified frame set incomplete");csv.close();
    cv::FileStorage summary((output/"coverage_metrics.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
    summary<<"protocol"<<"dense_coverage_actual85_development_v1"<<"split"<<"development"<<"frames"<<int(frameCount)<<"target_objects"<<objects<<"training_original_core_revision"<<trainingOriginalCore<<"raw_candidates"<<double(rawCount)<<"full_point_queries"<<double(pointQueries)<<"unverified_candidates"<<double(unverifiedCount)<<"baseline_tp"<<double(baselineTpTotal)<<"full_lazy_public_nms_exact"<<1<<"heldout_images_read"<<0;
    for(std::size_t p=0;p<4;++p)writeCoverageStats(summary,names[p],totals[p]);
    summary<<"per_scene"<<"[";
    for(const auto& scene:byScene){summary<<"{"<<"scene_id"<<scene.first;for(std::size_t p=0;p<4;++p)writeCoverageStats(summary,names[p],scene.second[p]);summary<<"}";}summary<<"]";
    summary<<"timing_diagnostic_only"<<"{"<<"bank_reconstruction_ms"<<std::chrono::duration<double,std::milli>(trainingEnd-trainingStart).count()<<"second_gradient_and_maps_total_ms"<<scenePrepareMs<<"full_verification_and_csv_total_ms"<<fullVerifyMs<<"three_policy_checks_and_metrics_total_ms"<<policyMs<<"paired_performance_benchmark"<<0<<"}";
}
static void integrationSelfTest(const fs::path& output) {
    cv::Mat large(5,13,CV_8UC1,cv::Scalar(0));auto bits=large(cv::Rect(2,1,9,3));
    for(int k=0;k<8;++k)bits.at<unsigned char>(1,k)=std::uint8_t(1u<<k);
    const auto labels=decodeCoreBits(bits);for(int k=0;k<8;++k)coverageRequire(labels[9+k]==k,"Single-bit decoding failed");
    coverageRequire(labels[0]==255 && labels[17]==255,"Core zero must become invalid, not label0");
    bits.at<unsigned char>(0,0)=3;bool caught=false;try{decodeCoreBits(bits);}catch(const std::runtime_error&){caught=true;}coverageRequire(caught,"Spread multibit field must be rejected");bits.setTo(0);
    cv::Mat magnitude(3,9,CV_32F,cv::Scalar(1600)),mask(3,9,CV_8U,cv::Scalar(255));bits.setTo(1);
    coverageRequire(sampleDense(bits,magnitude,mask).empty(),"Strong equality1600 must be excluded");
    magnitude.at<float>(0,1)=1601;magnitude.at<float>(1,0)=1601;magnitude.at<float>(2,8)=1602;
    const auto points=sampleDense(bits,magnitude,mask);
    coverageRequire(points.size()==2 && points[0].x==1 && points[0].y==0 && points[1].x==8 && points[1].y==2,"Canvas2x2 strongest/yx tie and odd sizes");
    mask.at<unsigned char>(0,1)=0;coverageRequire(sampleDense(bits,magnitude,mask)[0].x==0,"Official mask inclusion");
    line2Dup::ColorGradientPyramid bridge(cv::Mat(5,5,CV_8U,cv::Scalar(0)),cv::Mat(5,5,CV_8U,cv::Scalar(255)),20,32,40);
    bridge.angle.setTo(128);bridge.angle_ori.setTo(0);bridge.magnitude.setTo(1601);cv::Mat histogramBits;bridge.quantize(histogramBits);
    const auto histogramPoints=sampleDense(histogramBits,bridge.magnitude,bridge.mask);
    coverageRequire(!histogramPoints.empty() && histogramPoints.front().label==7,"Use exported histogram label rather than re-quantizing raw angle_ori");
    cv::Mat abc=(cv::Mat_<unsigned char>(1,3)<<97,98,99);
    coverageRequire(matrixSha256(abc)=="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad","Known SHA256 row-byte fixture");
    const auto blank=qc::build_support(decodeCoreBits(cv::Mat(3,5,CV_8U,cv::Scalar(0))),5,3);
    const auto unsupported=qc::evaluate(blank,qc::prepare_template({{2,1,0}}),0,0);
    coverageRequire(unsupported.verified && unsupported.balanced==0 && !qc::passes(unsupported,.5),"Blank core field is verified unsupported");
    // Same padded context is required: uniform nonzero input has no internal
    // gradient, while zero padding creates an artificial transition.
    cv::Mat image(17,19,CV_8U,cv::Scalar(200)),padded;
    cv::copyMakeBorder(image,padded,64,79,64,77,cv::BORDER_CONSTANT,cv::Scalar(0));
    line2Dup::ColorGradientPyramid original(image,cv::Mat(),20,32,40),pad(padded,cv::Mat(),20,32,40);
    cv::Mat a,b;original.quantize(a);pad.quantize(b);
    coverageRequire(cv::countNonZero(a)==0 && cv::countNonZero(b)>0,"Padded gradient context differs at original border");
    coverageRequire(padded.cols%16==0 && padded.rows%16==0,"Baseline odd image alignment");
    // Exact warp reconstruction matches a separately assembled asymmetric case.
    cv::Mat source(11,15,CV_8U),sourceMask(11,15,CV_8U,cv::Scalar(0));
    for(int y=0;y<source.rows;++y)for(int x=0;x<source.cols;++x)source.at<unsigned char>(y,x)=std::uint8_t((x*17+y*23+x*y)%256);
    sourceMask(cv::Rect(2,1,9,7)).setTo(255);sourceMask.at<unsigned char>(3,4)=0;
    for(float angle:{0.f,30.f,90.f})for(float scale:{.75f,1.f,1.5f,2.f}) {
        const auto result=rebuildWarp(source,sourceMask,angle,scale,16);
        const auto roi=cv::Rect(2,1,9,7);int side=int(std::ceil(std::sqrt(130.)*scale))+32;side=(side+15)/16*16;
        auto matrix=cv::getRotationMatrix2D({4.5f,3.5f},angle,scale);matrix.at<double>(0,2)+=side/2.-4.5;matrix.at<double>(1,2)+=side/2.-3.5;
        cv::Mat expected,expectedMask;cv::warpAffine(source(roi),expected,matrix,{side,side},cv::INTER_LINEAR,cv::BORDER_CONSTANT,cv::Scalar(0));cv::warpAffine(sourceMask(roi),expectedMask,matrix,{side,side},cv::INTER_NEAREST,cv::BORDER_CONSTANT,cv::Scalar(0));
        coverageRequire(cv::norm(result.image,expected,cv::NORM_INF)==0 && cv::norm(result.mask,expectedMask,cv::NORM_INF)==0,"Training warp reproduction mismatch");
        coverageRequire(matrixSha256(result.image)==matrixSha256(expected),"Warp row-byte hash mismatch");
    }
    const auto templatePoints=qc::prepare_template({{3,4,0},{4,4,0}},7,9);
    coverageRequire(templatePoints.points[0].x==-4 && templatePoints.points[0].y==-5,"Actual origin subtraction once");
    Config fixed;TemplateMeta syntheticMeta;syntheticMeta.id=0;syntheticMeta.image=7;syntheticMeta.tl_x=10;syntheticMeta.tl_y=20;syntheticMeta.angle=30;syntheticMeta.scale=1.5;syntheticMeta.silhouette={3,5,7,9};syntheticMeta.class_id="tless_object_1";
    Frame syntheticFrame;syntheticFrame.scene=99;syntheticFrame.image=3;syntheticFrame.rgb="synthetic/no-dataset-image";
    Detection synthetic;synthetic.class_id=syntheticMeta.class_id;synthetic.template_id=0;synthetic.match_x=200;synthetic.match_y=180;synthetic.score=std::nextafter(85.f,100.f);synthetic.box=boxAtMatch(200,180,64,syntheticMeta.silhouette,10,20);
    const std::vector<TemplateMeta> syntheticBank={syntheticMeta};writeRaw(output,syntheticFrame,"fallback",{synthetic},syntheticBank);
    const auto recovered=readRawVerified(output/"s99_i3_fallback_raw.csv.gz",syntheticFrame,"fallback",syntheticBank,fixed);
    coverageRequire(recovered.size()==1 && sameDetection(recovered[0],synthetic),"Raw float32/box/origin metadata roundtrip");
    auto wrongBank=syntheticBank;wrongBank[0].tl_x+=1;caught=false;
    try{readRawVerified(output/"s99_i3_fallback_raw.csv.gz",syntheticFrame,"fallback",wrongBank,fixed);}catch(const std::runtime_error&){caught=true;}
    coverageRequire(caught,"Raw box/origin integrity mismatch must reject");
    cv::FileStorage report((output/"integration_selftest.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
    report<<"pass"<<1<<"dataset_images_read"<<0<<"single_bit_labels"<<8<<"asymmetric_warp_cases"<<12<<"multibit_rejected"<<1<<"strong_equality_excluded"<<1<<"noncontiguous_roi"<<1<<"padded_context_difference"<<1<<"histogram_label_bridge"<<1<<"known_sha256_fixture"<<1<<"raw_exact_roundtrip"<<1<<"raw_metadata_mismatch_rejected"<<1;
    std::cout<<"PASS synthetic integration bit decode, strong threshold,2x2 sampler,ROI step,padding context,12 asymmetric warps; no dataset images read\n";
}

// Evaluation is invoked through the source/provenance-validating runner.
int main(int argc,char** argv) {
    try {
        std::map<std::string,std::string> args;
        for(int i=1;i<argc;i+=2){coverageRequire(i+1<argc,"Arguments require values");coverageRequire(args.emplace(argv[i],argv[i+1]).second,"Duplicate argument");}
        for(const auto& entry:args)coverageRequire(entry.first=="--mode" || entry.first=="--output" || entry.first=="--verified","Unknown argument");
        const auto mode=args.at("--mode");coverageRequire(mode=="selftest" || mode=="evaluate","Mode must be selftest/evaluate");
        const fs::path output=fs::absolute(args.at("--output"));coverageRequire(!fs::exists(output),"Output directory must be fresh");fs::create_directories(output);
        cv::setNumThreads(1);
        if(mode=="selftest")integrationSelfTest(output);
        else coverageEvaluation(fs::absolute(args.at("--verified")),output);
        return 0;
    }catch(const std::exception& error){std::cerr<<"ERROR "<<error.what()<<'\n';return 1;}
}

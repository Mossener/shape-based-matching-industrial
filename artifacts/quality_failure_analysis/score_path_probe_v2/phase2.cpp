// Isolated Phase2 source. No production or Phase1 source is edited.
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <psapi.h>
#include "../../silhouette_empty_mask_experiment/private_v11/line2Dup.cpp"
#define main unused_frozen_tless_main
#include "../../silhouette_empty_mask_experiment/frozen_helpers/tless_eval.cpp"
#undef main
#include "../../silhouette_empty_mask_experiment/quality_support.hpp"
namespace probe_v2 { using empty_quality::need; }
// Builder extracts exact Maps/preprocess bytes from pinned Phase1 source.
#include "generated_preprocess.hpp"

namespace probe_v2 {
using empty_quality::scoreBits;
using PointKey=std::pair<int,int>;
using RecordKey=std::tuple<int,int,std::uint32_t>;
static std::string fault="none";
static std::uint64_t coarseCalls=0,localCalls=0,fusedCalls=0,coarseCells=0,localCells=0,digitsWritten=0,decodes=0,controls=0;
static const std::set<int> OBJECTS{1,2,5,8,12,17},SCENES{1,4,6,7,8,10,12,13};
static float normalize(unsigned raw,std::size_t count){need(count>0 && count<8192,"Invalid actual feature denominator");return (int(raw)*100.f)/(4*int(count));}
static RecordKey recordKey(const Detection& d){return {d.match_x,d.match_y,scoreBits(d.score)};}
static int integer(double value){need(std::isfinite(value) && value==std::floor(value) && std::abs(value)<1000000,"Noninteger/unsafe physical coordinate");return int(value);}

struct Gzip {
    gzFile file=nullptr;
    explicit Gzip(const fs::path& path,const std::string& header){file=gzopen(path.string().c_str(),"wb1");need(file,"Cannot create numeric gzip");line(header);}
    void line(const std::string& value){const auto text=value+"\n";need(text.size()<10000000 && gzwrite(file,text.data(),unsigned(text.size()))==int(text.size()),"Numeric gzip write failed");}
    void flush(){need(gzflush(file,Z_SYNC_FLUSH)==Z_OK,"Numeric gzip flush failed");}
    void close(){if(file){auto saved=file;file=nullptr;need(gzclose(saved)==Z_OK,"Numeric gzip close failed");}}
    ~Gzip(){if(file)gzclose(file);}
};
static std::uint64_t outputBytes(const fs::path& output){std::uint64_t result=0;for(const auto& file:fs::recursive_directory_iterator(output))if(file.is_regular_file())result+=file.file_size();return result;}
static void resources(const fs::path& output,const std::chrono::steady_clock::time_point& began){
    need(empty_quality::peakRss()<=1610612736ULL,"Phase2 peak RSS exceeds 1.5 GiB");
    need(outputBytes(output)<=1073741824ULL,"Phase2 complete output exceeds one GiB");
    need(std::chrono::duration<double>(std::chrono::steady_clock::now()-began).count()<=3600,"Phase2 exceeds 60 minutes");
}
struct Stream {const cv::Mat* grid=nullptr;std::int64_t first=0;bool skipped=false;};
static Stream stream(const std::vector<cv::Mat>& lm,int x,int y,int label,cv::Size size,int T,std::int64_t lastDelta){
    need(label>=0 && label<8,"Invalid serialized feature label");
    if(x<0 || y<0 || x>=size.width || y>=size.height)return {nullptr,0,true};
    const auto& grid=lm.at(label);need(grid.type()==CV_8UC1 && grid.isContinuous(),"Independent LM storage contract differs");
    const int phase=(y%T)*T+x%T,W=size.width/T;
    const std::int64_t first=std::int64_t(phase)*grid.cols+std::int64_t(y/T)*W+x/T;
    need(phase>=0 && phase<grid.rows && first>=0 && first+lastDelta<std::int64_t(grid.total()),"Unsupported native LM storage domain");
    return {&grid,first,false};
}
static unsigned read(const Stream& source,std::int64_t delta){
    if(source.skipped)return 0;
    need(source.first+delta>=0 && source.first+delta<std::int64_t(source.grid->total()),"Independent LM read outside actual storage");
    const unsigned value=source.grid->ptr<unsigned char>()[source.first+delta];need(value<=4,"Response outside unchanged LUT range");return value;
}
static void featureVector(Gzip* file,const std::string& kind,int owner,int index,const line2Dup::Feature& f,bool skipped,const std::string& digits){
    if(!file)return;
    std::ostringstream row;row<<kind<<','<<owner<<','<<index<<','<<f.x<<','<<f.y<<','<<f.label<<','<<skipped<<','<<digits.size()<<','<<digits;
    file->line(row.str());digitsWritten+=digits.size();
}
static cv::Mat coarse(const std::vector<cv::Mat>& lm,const line2Dup::Template& tp,cv::Size size,int T,int owner,Gzip* features,Gzip* cells){
    const int W=size.width/T,H=size.height/T,wf=(tp.width-1)/T+1,hf=(tp.height-1)/T+1;
    const int count=(H-hf)*W+(W-wf)+1;need(count>=0 && count<=W*H,"Unsupported native coarse flat span");
    std::vector<unsigned> scalar(W*H,0);
    for(int fi=0;fi<int(tp.features.size());++fi){const auto& f=tp.features[fi];
        const auto source=stream(lm,f.x,f.y,f.label,size,T,std::max(0,count-1));
        std::string contributions(W*H,'0');for(int j=0;j<count;++j){const unsigned value=read(source,j);scalar[j]+=value;contributions[j]=char('0'+value);}
        featureVector(features,"coarse",owner,fi,f,source.skipped,contributions);
    }
#ifdef SCORE_PATH_RED_CONTROLS
    if(fault=="coarse")++scalar.at(0);
#endif
    cv::Mat actual;++coarseCalls;
    if(tp.features.size()<64)line2Dup::similarity_64(lm,tp,actual,size,T);else line2Dup::similarity(lm,tp,actual,size,T);
    need(actual.rows==H && actual.cols==W,"Native coarse output dimensions differ");
    for(int j=0;j<W*H;++j){
        const unsigned raw=actual.type()==CV_8U?actual.at<unsigned char>(j/W,j%W):actual.at<unsigned short>(j/W,j%W);
        need(raw==scalar[j],"Independent coarse oracle mismatch");
        const float native=line2Dup::detail::similarityScore(raw,int(tp.features.size()));
        need(scoreBits(native)==scoreBits(normalize(scalar[j],tp.features.size())),"Independent coarse score bits mismatch");
        if(cells){std::ostringstream row;row<<"coarse,"<<owner<<','<<j/W<<','<<j%W<<','<<raw<<','<<scoreBits(native)<<','<<(j<count)<<','<<(native>85.f);cells->line(row.str());}
    }
    coarseCells+=W*H;return actual;
}
struct Local {cv::Mat native;line2Dup::detail::LocalMaximum best;std::array<unsigned,256> scalar{};int ties=0;};
static Local local(const std::vector<cv::Mat>& lm,const line2Dup::Template& tp,cv::Size size,int T,cv::Point center,int owner,Gzip* features,Gzip* cells,Gzip* maxima){
    Local result;const int W=size.width/T,baseX=(center.x/T-8)*T,baseY=(center.y/T-8)*T;
    for(int fi=0;fi<int(tp.features.size());++fi){const auto& f=tp.features[fi];
        const auto source=stream(lm,f.x+baseX,f.y+baseY,f.label,size,T,15*W+15);
        std::string contributions(256,'0');for(int row=0;row<16;++row)for(int col=0;col<16;++col){
            const unsigned value=read(source,row*W+col);result.scalar[row*16+col]+=value;contributions[row*16+col]=char('0'+value);}
        featureVector(features,"local",owner,fi,f,source.skipped,contributions);
    }
#ifdef SCORE_PATH_RED_CONTROLS
    if(fault=="local")++result.scalar.at(0);
#endif
    ++localCalls;if(tp.features.size()<64)line2Dup::similarityLocal_64(lm,tp,result.native,size,T,center);else line2Dup::similarityLocal(lm,tp,result.native,size,T,center);
    line2Dup::detail::LocalMaximum expected;
    for(int row=0;row<16;++row)for(int col=0;col<16;++col){
        const unsigned raw=result.native.type()==CV_8U?result.native.at<unsigned char>(row,col):result.native.at<unsigned short>(row,col);
        need(raw==result.scalar[row*16+col],"Independent local oracle mismatch");
        if(raw>expected.raw){expected.raw=raw;expected.row=row;expected.col=col;}
        const auto native=line2Dup::detail::similarityScore(raw,int(tp.features.size()));
        need(scoreBits(native)==scoreBits(normalize(result.scalar[row*16+col],tp.features.size())),"Independent local score bits mismatch");
        if(cells){std::ostringstream line;line<<"local,"<<owner<<','<<row<<','<<col<<','<<raw<<','<<scoreBits(native)<<",1,"<<(native>=85.f);cells->line(line.str());}
    }
    if(expected.raw)expected.score=normalize(expected.raw,tp.features.size());
    std::vector<const unsigned char*> streams;++fusedCalls;
    result.best=line2Dup::similarityLocalMaximum(lm,tp,size,T,center,streams);
#ifdef SCORE_PATH_RED_CONTROLS
    if(fault=="winner")++expected.col;
#endif
    need(result.best.raw==expected.raw && result.best.row==expected.row && result.best.col==expected.col && scoreBits(result.best.score)==scoreBits(expected.score),"Independent winner oracle mismatch");
    std::string tieMask;for(unsigned raw:result.scalar){const bool equal=raw==expected.raw;result.ties+=equal;tieMask.push_back(equal?'1':'0');}
    if(maxima){std::ostringstream row;row<<owner<<','<<center.x<<','<<center.y<<','<<baseX<<','<<baseY<<','<<result.best.raw<<','<<scoreBits(result.best.score)<<','<<result.best.row<<','<<result.best.col<<','<<result.ties<<','<<tieMask;maxima->line(row.str());}
    localCells+=256;return result;
}
static std::vector<std::vector<std::string>> csv(const fs::path& file){
    std::ifstream input(file);need(input.good(),"Missing pinned numeric table");std::string line;std::getline(input,line);std::vector<std::vector<std::string>> rows;
    while(std::getline(input,line)){if(!line.empty() && line.back()=='\r')line.pop_back();auto row=empty_quality::fields(line);rows.push_back(std::move(row));}need(input.eof(),"Numeric table read failed");return rows;
}
using FrameKey=std::tuple<int,int,int,std::string>;
struct SavedSelected{Detection detection;std::string allLabel,eligibleLabel;int allId=-1,eligibleId=-1;};
static std::map<FrameKey,std::vector<SavedSelected>> selections(const fs::path& file){
    std::map<FrameKey,std::vector<SavedSelected>> result;for(const auto& c:csv(file)){need(c.size()==22,"Saved selected schema differs");
        SavedSelected item;item.detection.class_id=c[5];item.detection.score=std::stof(c[6]);need(scoreBits(item.detection.score)==std::stoul(c[7]),"Saved selected score bits differ");
        item.detection.template_id=std::stoi(c[8]);item.detection.match_x=std::stoi(c[12]);item.detection.match_y=std::stoi(c[13]);
        item.detection.box={std::stod(c[14]),std::stod(c[15]),std::stod(c[16]),std::stod(c[17])};item.allLabel=c[18];item.allId=std::stoi(c[19]);item.eligibleLabel=c[20];item.eligibleId=std::stoi(c[21]);
        auto& rows=result[{std::stoi(c[0]),std::stoi(c[1]),std::stoi(c[2]),c[3]}];need(std::stoi(c[4])==int(rows.size()),"Saved selected order differs");rows.push_back(item);
    }return result;
}
static std::map<std::tuple<int,int,int>,std::vector<GroundTruth>> truths(const fs::path& file){
    std::map<std::tuple<int,int,int>,std::vector<GroundTruth>> result;for(const auto& c:csv(file)){need(c.size()==10,"Saved truth schema differs");GroundTruth gt;
        gt.id=std::stoi(c[3]);gt.class_id=c[4];gt.visibility=std::stod(c[5]);gt.box={std::stod(c[6]),std::stod(c[7]),std::stod(c[8]),std::stod(c[9])};result[{std::stoi(c[0]),std::stoi(c[1]),std::stoi(c[2])}].push_back(gt);
    }return result;
}
struct FullFrame {std::vector<Detection> pre,post,selected;std::vector<int> keptRank,blocker;};
static FullFrame frameRecords(const fs::path& native,int obj,const std::string& arm,const Frame& frame,const std::vector<TemplateMeta>& meta,const std::vector<GroundTruth>& gt,const std::vector<SavedSelected>& saved,Gzip& nmsFile){
    FullFrame full;const auto dir=native/("obj"+std::to_string(obj))/arm;
    full.pre=empty_quality::readRaw(dir/(frameKey(frame)+"_pre_raw.csv.gz"),frame,"pre",meta);
    full.post=empty_quality::readRaw(dir/(frameKey(frame)+"_post_raw.csv.gz"),frame,"post",meta);
    full.blocker.assign(full.post.size(),-1);
    for(int rank=0;rank<int(full.post.size());++rank){const auto& candidate=full.post[rank];for(int old:full.keptRank){
        if(candidate.class_id==full.post[old].class_id && iou(candidate.box,full.post[old].box)>.3){full.blocker[rank]=old;break;}}
        if(full.blocker[rank]<0){full.keptRank.push_back(rank);full.selected.push_back(candidate);}
    }
    need(full.selected.size()==saved.size(),"Fullclass NMS selected count differs");
    const auto all=evaluate(full.selected,gt,.5,false,.5),eligible=evaluate(full.selected,gt,.5,true,.5);
    for(int rank=0;rank<int(saved.size());++rank)need(empty_quality::exact(full.selected[rank],saved[rank].detection) && all.labels[rank]==saved[rank].allLabel && all.gt_ids[rank]==saved[rank].allId && eligible.labels[rank]==saved[rank].eligibleLabel && eligible.gt_ids[rank]==saved[rank].eligibleId,"Fullclass NMS/assignment gate differs");
    std::map<int,int> selectedRank;for(int i=0;i<int(full.keptRank.size());++i)selectedRank[full.keptRank[i]]=i;
    for(int rank=0;rank<int(full.post.size());++rank){const auto& d=full.post[rank];const int sr=selectedRank.count(rank)?selectedRank.at(rank):-1,block=full.blocker[rank];
        std::ostringstream row;row<<std::setprecision(17)<<obj<<','<<frame.scene<<','<<frame.image<<','<<arm<<','<<rank<<','<<d.template_id<<','<<d.match_x<<','<<d.match_y<<','<<scoreBits(d.score)<<','<<sr<<','<<block<<','<<(block>=0?iou(d.box,full.post[block].box):0)<<','<<(sr>=0?all.labels[sr]:"SUPPRESSED")<<','<<(sr>=0?all.gt_ids[sr]:-1);nmsFile.line(row.str());}
    return full;
}
static void selftest(const fs::path& output){
    std::vector<cv::Mat> lm(8);for(int label=0;label<8;++label){lm[label].create(64,12,CV_8U);for(int row=0;row<64;++row)for(int col=0;col<12;++col)lm[label].at<unsigned char>(row,col)=(label+row+col)%5;}
    line2Dup::Template tp;tp.width=16;tp.height=16;tp.features={{0,0,0},{-1,0,1}};
    const auto actual=coarse(lm,tp,{32,24},8,0,nullptr,nullptr);
    need(actual.rows*actual.cols==12 && actual.at<unsigned char>(0,3)!=0 && actual.at<unsigned char>(1,3)==0,"Coarse wrap/zero tail fixture differs");
    for(int label=0;label<8;++label){lm[label].create(16,1600,CV_8U);for(int row=0;row<16;++row)for(int col=0;col<1600;++col)lm[label].at<unsigned char>(row,col)=(label+row+3*col)%5;}
    tp.width=8;tp.height=8;tp.features={{1,2,0},{5,6,3},{-33,0,7}};
    local(lm,tp,{160,160},4,{64,64},0,nullptr,nullptr,nullptr);
    const auto zero=line2Dup::detail::localMaximum(cv::Mat::zeros(16,16,CV_8U),3);
    need(zero.raw==0 && zero.row==-1 && zero.col==-1 && !(normalize(34,10)>85.f) && normalize(34,10)>=85.f,"Threshold/zero sentinel fixture differs");
    cv::FileStorage summary((output/"selftest_result.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
    summary<<"passed"<<1<<"stage"<<"selftest"<<"coarse_cells"<<12<<"local_cells"<<256<<"scalar_native_oracles"<<1<<"dataset_image_reads"<<0<<"full_class_search_replays"<<0<<"public_detector_match_calls"<<0;
}

struct Bank {
    std::string arm;int obj;std::vector<TemplateMeta> meta;line2Dup::Detector detector;
    Bank(int object,const std::string& name,const fs::path& path,int count):arm(name),obj(object),meta(readMeta(path/"template_metadata.json")),detector(32,{4,8},20,40){
        detector.readClasses({classForObject(obj)},(path/"templates_%s.yml.gz").string());need(meta.size()==count && detector.numTemplates()==count && detector.classIds()==std::vector<std::string>{classForObject(obj)},"Phase2 loaded bank identity differs");
    }
};
struct Parent{int row=0,col=0;cv::Point center,base;int window=-1;};
static void phase2(const fs::path& planPath,const fs::path& output){
    const auto began=std::chrono::steady_clock::now();cv::FileStorage plan(planPath.string(),cv::FileStorage::READ);
    need(plan.isOpened() && str(plan["phase"])=="phase2" && int(plan["rgb_tp_identities"])==215 && int(plan["arm_identity_probes"])==430,"Phase2 fixed input scope differs");
    cv::FileStorage prior(str(plan["prior_input_plan"]["path"]),cv::FileStorage::READ);
    const auto phase1Native=fs::path(str(plan["prior_phase1_receipt"]["path"])).parent_path()/"native";
    fs::path selectedPath,truthPath;for(const auto& pin:prior["numeric_pins"]){const fs::path path=str(pin["path"]);if(path.filename()=="selected_detections.csv")selectedPath=path;if(path.filename()=="ground_truth.csv")truthPath=path;}
    need(!selectedPath.empty() && !truthPath.empty(),"Pinned selected/GT numerics missing");
    const auto savedSelected=selections(selectedPath);const auto savedTruth=truths(truthPath);
    cv::FileStorage padding(str(prior["common_padding_json"]),cv::FileStorage::READ);const auto pad=empty_quality::padding(padding);
    need(pad.width==848 && pad.height==832,"Phase2 common geometry differs");
    Gzip jobFile(output/"jobs.csv.gz","job_id,object_id,scene,image,arm,template_id,training_image,angle,scale,fine_features,coarse_features,gt_id,physical_x,physical_y"),
         vectors(output/"feature_vectors.csv.gz","kind,owner,feature_id,x,y,label,skipped,cells,response_digits"),
         cells(output/"native_cells.csv.gz","kind,owner,row,col,native_raw,native_score_bits,computed,threshold_pass"),
         maxima(output/"local_maxima.csv.gz","window,center_x,center_y,base_x,base_y,raw,score_bits,row,col,ties,tie_mask"),
         anchors(output/"physical_anchors.csv.gz","job,gt_id,physical_x,physical_y,on_grid,in_physical_domain,raw,score_bits,feature_id,response"),
         links(output/"parent_links.csv.gz","job,gt_id,point_x,point_y,coarse_row,coarse_col,coarse_raw,coarse_score_bits,admitted,window,point_raw,point_score_bits,point_fine_pass,winner_x,winner_y,winner_raw,winner_score_bits,point_is_winner,predicts_emission,point_iou_gt"),
         occurrences(output/"occurrences.csv.gz","job,gt_id,match_x,match_y,score_bits,traced_parents,full_pre_multiplicity,post_representative_template,post_rank,nms_selected_rank,nms_blocker,pre_box_x,pre_box_y,pre_box_w,pre_box_h,rep_box_x,rep_box_y,rep_box_w,rep_box_h,pre_iou_gt,rep_iou_gt"),
         nmsFile(output/"fullclass_nms_assignment.csv.gz","object_id,scene,image,arm,post_rank,template,match_x,match_y,score_bits,selected_rank,blocker_post_rank,blocker_iou,allGT_label,allGT_id");
    std::vector<Gzip*> files{&jobFile,&vectors,&cells,&maxima,&anchors,&links,&occurrences,&nmsFile};
    std::set<std::tuple<int,int,int>> frameScope;std::set<std::pair<int,int>> imageScope;
    int jobNumber=0,windowNumber=0,nmsFrames=0,pointCount=0,parentLinks=0,jobTargetRows=0,physicalFeatureProbes=0;
    std::set<std::tuple<int,int,int,std::string,int>> plannedJobKeys,consumedJobKeys;
    std::map<FrameKey,std::vector<cv::FileNode>> jobs;
    for(const auto& job:plan["jobs"]){const auto key=job["key"];need(key.size()==5 && plannedJobKeys.emplace(int(key[0]),int(key[1]),int(key[2]),str(key[3]),int(key[4])).second,"Duplicate/invalid fixed job key");jobs[{int(key[0]),int(key[1]),int(key[2]),str(key[3])}].push_back(job);}
    need(plannedJobKeys.size()==430,"Fixed plan job identity count differs");
    for(const auto& bankNode:prior["banks"]){const int obj=int(bankNode["object_id"]);need(OBJECTS.count(obj),"Reserved/unknown object");
        Bank rgb(obj,"rgb",str(bankNode["rgb_training"]),int(bankNode["rgb_template_count"])),binary(obj,"binary_empty_mask",str(bankNode["binary_training"]),3456);
        for(const auto& frameNode:prior["frames"]){if(int(frameNode["object_id"])!=obj)continue;
            Frame frame;frame.scene=int(frameNode["scene"]);frame.image=int(frameNode["image"]);
            need(SCENES.count(frame.scene) && frameScope.emplace(obj,frame.scene,frame.image).second,"Duplicate/prohibited frame");
            imageScope.emplace(frame.scene,frame.image);
            const cv::Mat image=cv::imread(str(frameNode["image_path"]),cv::IMREAD_GRAYSCALE);++decodes;need(image.type()==CV_8UC1 && image.cols==720 && image.rows==540,"Pinned image decode differs");
            cv::Mat padded;cv::copyMakeBorder(image,padded,pad.ltrb[1],pad.ltrb[3],pad.ltrb[0],pad.ltrb[2],cv::BORDER_CONSTANT,cv::Scalar(0));
            const auto maps=preprocess(padded);
            for(Bank* bank:{&rgb,&binary}){const FrameKey key{obj,frame.scene,frame.image,bank->arm};
                const auto& ground=savedTruth.at({obj,frame.scene,frame.image});
                const auto saved=savedSelected.find(key);const std::vector<SavedSelected> empty;
                const auto full=frameRecords(phase1Native,obj,bank->arm,frame,bank->meta,ground,saved==savedSelected.end()?empty:saved->second,nmsFile);++nmsFrames;
                for(const auto& job:jobs.at(key)){const int jobId=jobNumber++,tid=int(job["key"][4]);const auto& meta=bank->meta.at(tid);
                    need(consumedJobKeys.emplace(obj,frame.scene,frame.image,bank->arm,tid).second,"Fixed job consumed more than once");
                    const auto& tp=bank->detector.getTemplates(classForObject(obj),tid);need(tp.size()==2 && tp[0].features.size()==int(job["fine_features"]) && tp[1].features.size()==int(job["coarse_features"]),"Serialized feature count differs from fixed plan");
                    for(const auto& target:job["targets"]){std::ostringstream row;row<<std::setprecision(17)<<jobId<<','<<obj<<','<<frame.scene<<','<<frame.image<<','<<bank->arm<<','<<tid<<','<<meta.image<<','<<meta.angle<<','<<meta.scale<<','<<tp[0].features.size()<<','<<tp[1].features.size()<<','<<int(target["gt_id"])<<','<<int(target["physical_anchor"][0])<<','<<int(target["physical_anchor"][1]);jobFile.line(row.str());++jobTargetRows;}
                    const auto map=coarse(maps.memories[1][0],tp[1],maps.sizes[1],8,jobId,&vectors,&cells);
                    std::map<PointKey,Parent> parents;std::map<PointKey,std::vector<PointKey>> pointParents;
                    for(const auto& pointPlan:job["point_plan"]){const PointKey point{int(pointPlan["point"][0]),int(pointPlan["point"][1])};need((point.first-1)%4==0 && (point.second-1)%4==0,"Planned point off native grid");++pointCount;
                        std::set<PointKey> expected,declared;
                        for(int row=0;row<map.rows;++row)for(int col=0;col<map.cols;++col){Parent p;p.row=row;p.col=col;p.center={std::min(std::max(2*(col*8+3)+1,32),maps.sizes[0].width-tp[0].width-32),std::min(std::max(2*(row*8+3)+1,32),maps.sizes[0].height-tp[0].height-32)};p.base={(p.center.x/4-8)*4,(p.center.y/4-8)*4};
                            if(point.first>=p.base.x+1 && point.first<=p.base.x+61 && point.second>=p.base.y+1 && point.second<=p.base.y+61){const PointKey parent{row,col};expected.insert(parent);parents.emplace(parent,p);}}
                        for(const auto& node:pointPlan["parents"]){const PointKey pk{int(node["row"]),int(node["col"])};need(declared.insert(pk).second,"Duplicate planned parent");const auto& p=parents.at(pk);need(p.center.x==int(node["start"][0]) && p.center.y==int(node["start"][1]) && p.base.x==int(node["base"][0]) && p.base.y==int(node["base"][1]),"Planned/native parent clamp differs");pointParents[point].push_back(pk);++parentLinks;}
                        need(expected==declared,"Complete reachable-parent domain differs");
                    }
                    std::map<PointKey,Local> windows;std::map<PointKey,int> windowIds;
                    for(auto& item:parents){auto& p=item.second;const PointKey base{p.base.x,p.base.y};if(!windows.count(base)){const int id=windowNumber++;windows.emplace(base,local(maps.memories[0][0],tp[0],maps.sizes[0],4,p.center,id,&vectors,&cells,&maxima));windowIds[base]=id;}p.window=windowIds.at(base);}
                    std::map<RecordKey,int> predicted,actualPre;
                    for(const auto& row:full.pre)if(row.template_id==tid)++actualPre[recordKey(row)];
                    for(const auto& item:parents){const auto& p=item.second;const auto& best=windows.at({p.base.x,p.base.y}).best;const unsigned raw=map.type()==CV_8U?map.at<unsigned char>(p.row,p.col):map.at<unsigned short>(p.row,p.col);
                        if(normalize(raw,tp[1].features.size())>85.f && best.score>=85.f)++predicted[{p.base.x+4*best.col+1,p.base.y+4*best.row+1,scoreBits(best.score)}];}
                    for(const auto& item:actualPre)if(item.second>0 && pointParents.count({std::get<0>(item.first),std::get<1>(item.first)}))need(predicted.count(item.first)>0,"Actual probed-point occurrence contradicts complete parent coverage");
                    for(const auto& item:predicted){need(actualPre[item.first]>=item.second,"Traced occurrence exceeds complete same-template pre multiplicity");
                        int postRank=-1,selectedRank=-1;for(int rank=0;rank<int(full.post.size());++rank)if(recordKey(full.post[rank])==item.first){need(postRank<0,"Nonunique post equality key");postRank=rank;}
                        need(postRank>=0,"Predicted occurrence has no complete post representative");for(int rank=0;rank<int(full.keptRank.size());++rank)if(full.keptRank[rank]==postRank)selectedRank=rank;
                        const auto preBox=boxAtMatch(std::get<0>(item.first),std::get<1>(item.first),64,meta.silhouette,meta.tl_x,meta.tl_y),repBox=full.post[postRank].box;
                        for(const auto& target:job["targets"]){const int gtId=int(target["gt_id"]);const auto truth=std::find_if(ground.begin(),ground.end(),[&](const auto& gt){return gt.id==gtId;});need(truth!=ground.end(),"Occurrence target GT missing");
                            std::ostringstream row;row<<std::setprecision(17)<<jobId<<','<<gtId<<','<<std::get<0>(item.first)<<','<<std::get<1>(item.first)<<','<<std::get<2>(item.first)<<','<<item.second<<','<<actualPre.at(item.first)<<','<<full.post[postRank].template_id<<','<<postRank<<','<<selectedRank<<','<<full.blocker[postRank]<<','<<preBox.x<<','<<preBox.y<<','<<preBox.w<<','<<preBox.h<<','<<repBox.x<<','<<repBox.y<<','<<repBox.w<<','<<repBox.h<<','<<iou(preBox,truth->box)<<','<<iou(repBox,truth->box);occurrences.line(row.str());}}
                    for(const auto& target:job["targets"]){const int gtId=int(target["gt_id"]);const auto truth=std::find_if(ground.begin(),ground.end(),[&](const auto& gt){return gt.id==gtId;});need(truth!=ground.end(),"Target GT missing");
                        const auto priorTarget=std::find_if(frameNode["targets"].begin(),frameNode["targets"].end(),[&](const cv::FileNode& n){return int(n["gt_id"])==gtId;});need(priorTarget!=frameNode["targets"].end(),"Original RGB anchor missing");
                        const auto pose=(*priorTarget)["rgb_tp_pose"];need(meta.image==int(pose[0]) && meta.angle==float(pose[1]) && meta.scale==float(pose[2]),"Arm pose identity differs");
                        const auto box=boxNode((*priorTarget)["rgb_tp_box"]);const int ax=integer(box.x+64-meta.silhouette.x+meta.tl_x),ay=integer(box.y+64-meta.silhouette.y+meta.tl_y);
                        need(ax==int(target["physical_anchor"][0]) && ay==int(target["physical_anchor"][1]),"Physical anchor plan differs");
                        const bool onGrid=(ax-1)%4==0 && (ay-1)%4==0;bool physicalDomain=true;unsigned physicalRaw=0;std::vector<int> physicalContributions;
                        for(const auto& feature:tp[0].features){const int x=feature.x+ax-1,y=feature.y+ay-1;if(x<0 || y<0 || x>=maps.sizes[0].width || y>=maps.sizes[0].height){physicalDomain=false;physicalContributions.push_back(-1);}else{const unsigned value=read(stream(maps.memories[0][0],x,y,feature.label,maps.sizes[0],4,0),0);physicalRaw+=value;physicalContributions.push_back(int(value));}}
                        for(int fi=0;fi<int(physicalContributions.size());++fi){std::ostringstream row;row<<jobId<<','<<gtId<<','<<ax<<','<<ay<<','<<onGrid<<','<<physicalDomain<<','<<(physicalDomain?std::to_string(physicalRaw):"")<<','<<(physicalDomain?std::to_string(scoreBits(normalize(physicalRaw,tp[0].features.size()))):"")<<','<<fi<<','<<physicalContributions[fi];anchors.line(row.str());++physicalFeatureProbes;}
                        bool rgbControl=false;
                        for(const auto& pointNode:target["points"]){const PointKey point{int(pointNode[0]),int(pointNode[1])};need(pointParents.count(point),"Target grid point missing");
                            for(const auto& pk:pointParents.at(point)){const auto& p=parents.at(pk);const auto& window=windows.at({p.base.x,p.base.y});const unsigned coarseRaw=map.type()==CV_8U?map.at<unsigned char>(p.row,p.col):map.at<unsigned short>(p.row,p.col);const auto coarseScore=normalize(coarseRaw,tp[1].features.size());const int row=(point.second-1-p.base.y)/4,col=(point.first-1-p.base.x)/4;
                                const unsigned pointRaw=window.scalar[row*16+col];const auto pointScore=normalize(pointRaw,tp[0].features.size());const int wx=p.base.x+4*window.best.col+1,wy=p.base.y+4*window.best.row+1;const bool same=wx==point.first && wy==point.second,emitted=coarseScore>85.f && window.best.score>=85.f;
                                if(bank->arm=="rgb" && point==PointKey{ax,ay} && same && emitted && scoreBits(window.best.score)==std::uint32_t(double((*priorTarget)["rgb_tp_score_bits"])))rgbControl=true;
                                const auto official=boxAtMatch(point.first,point.second,64,meta.silhouette,meta.tl_x,meta.tl_y);
                                std::ostringstream line;line<<std::setprecision(17)<<jobId<<','<<gtId<<','<<point.first<<','<<point.second<<','<<p.row<<','<<p.col<<','<<coarseRaw<<','<<scoreBits(coarseScore)<<','<<(coarseScore>85.f)<<','<<p.window<<','<<pointRaw<<','<<scoreBits(pointScore)<<','<<(pointScore>=85.f)<<','<<wx<<','<<wy<<','<<window.best.raw<<','<<scoreBits(window.best.score)<<','<<same<<','<<emitted<<','<<iou(official,truth->box);links.line(line.str());
                            }}
                        if(bank->arm=="rgb"){need(onGrid && rgbControl,"Original RGB positive-control path missing");++controls;}
                    }
                    for(auto* file:files)file->flush();resources(output,began);
                }
            }std::cout<<"PHASE2 object "<<obj<<" scene "<<frame.scene<<" image "<<frame.image<<" jobs "<<jobNumber<<'\n';
        }
    }
    need(jobNumber==430 && jobTargetRows==430 && consumedJobKeys==plannedJobKeys && physicalFeatureProbes==13534 && controls==215 && frameScope.size()==213 && imageScope.size()==175 && decodes==213 && nmsFrames==426 && pointCount==751 && parentLinks==12016 && coarseCalls==430 && localCalls==7185 && fusedCalls==7185 && coarseCells==1185080 && localCells==1839360 && digitsWritten==73337912,"Complete fixed Phase2 budget/scope differs");
    for(auto* file:files)file->close();resources(output,began);
    cv::FileStorage summary((output/"stage_summary.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
    summary<<"passed"<<1<<"stage"<<"phase2"<<"coarse_similarity_calls"<<double(coarseCalls)<<"local_map_calls"<<double(localCalls)<<"local_fused_maximum_calls"<<double(fusedCalls)<<"coarse_cells"<<double(coarseCells)<<"local_cells"<<double(localCells)<<"feature_response_digits"<<double(digitsWritten)<<"job_identity_rows"<<jobTargetRows<<"unique_job_keys"<<int(consumedJobKeys.size())<<"physical_feature_probes"<<physicalFeatureProbes<<"fullclass_nms_frames"<<nmsFrames<<"native_grid_points"<<pointCount<<"point_parent_links"<<parentLinks<<"rgb_positive_controls"<<double(controls)<<"decoded_operations"<<double(decodes)<<"unique_image_files"<<175<<"full_class_search_replays"<<0<<"public_detector_match_calls"<<0<<"all_oracles_exact"<<1<<"all_occurrence_gates_exact"<<1<<"all_fullclass_nms_assignment_exact"<<1<<"numeric_output_bytes"<<double(outputBytes(output))<<"peak_rss_bytes"<<double(empty_quality::peakRss())<<"accuracy_improvement_claim"<<0;
}
}
int main(int argc,char** argv){fs::path output;bool created=false;try{
    std::map<std::string,std::string> args;for(int i=1;i<argc;i+=2){empty_quality::need(i+1<argc,"Missing argument value");empty_quality::need(args.emplace(argv[i],argv[i+1]).second,"Duplicate argument");}
    for(const auto& item:args)empty_quality::need(item.first=="--mode" || item.first=="--fault" || item.first=="--output" || item.first=="--plan","Unknown Phase2 argument");
    const auto mode=args.at("--mode");probe_v2::fault=args.at("--fault");empty_quality::need(mode=="selftest" || mode=="phase2","Unknown Phase2 mode");
#ifdef SCORE_PATH_RED_CONTROLS
    empty_quality::need(mode=="selftest" && (probe_v2::fault=="coarse" || probe_v2::fault=="local" || probe_v2::fault=="winner"),"RED build is synthetic-fault-only");
#else
    empty_quality::need(probe_v2::fault=="none","GREEN build has no injected fault");
#endif
    output=fs::absolute(args.at("--output"));empty_quality::need(!fs::exists(output),"Fresh native Phase2 output required");fs::create_directories(output);created=true;std::ofstream(output/".gitignore")<<"*\n";
    cv::setNumThreads(1);
#ifdef _OPENMP
    omp_set_num_threads(4);omp_set_dynamic(0);
#endif
    if(mode=="selftest")probe_v2::selftest(output);else probe_v2::phase2(args.at("--plan"),output);return 0;
}catch(const std::exception& error){std::cerr<<"PHASE2 FAILED: "<<error.what()<<'\n';if(created)try{
    cv::FileStorage failure((output/"failure.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
    failure<<"passed"<<0<<"reason"<<error.what()<<"coarse_similarity_calls_started"<<double(probe_v2::coarseCalls)<<"local_map_calls_started"<<double(probe_v2::localCalls)<<"local_fused_maximum_calls_started"<<double(probe_v2::fusedCalls)<<"decoded_operations_started"<<double(probe_v2::decodes)<<"full_class_search_replays"<<0<<"public_detector_match_calls"<<0<<"partial_results_are_not_negatives"<<1;
}catch(...){}return 1;}}

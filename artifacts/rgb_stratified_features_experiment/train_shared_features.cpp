// Isolated V31 orchestration. Exact V11 core remains a separate translation unit.
#define main frozen_public_evaluator_entry
#include "frozen_helpers/tless_eval.cpp"
#undef main
#include "collector/candidate_collector.cpp"
#include "integration/shared_training.hpp"
#include "packing/numeric_pack.hpp"
#include <psapi.h>
#include <tuple>

namespace pack=rgb_stratified::packing;
namespace integ=rgb_stratified::integration;
namespace sample=industrial_stratified;
static const std::vector<int> OBJECTS{1,2,5,8,12,17};
static const std::array<std::string,2> ARMS{{"rgb_pooled_features","rgb_stratified_features"}};
static void need(bool v,const std::string& message){if(!v)throw std::runtime_error(message);}
static std::uint32_t bits(float v){std::uint32_t b;std::memcpy(&b,&v,4);return b;}
static std::uint64_t peak_rss() {
 PROCESS_MEMORY_COUNTERS c{};c.cb=sizeof(c);need(GetProcessMemoryInfo(GetCurrentProcess(),&c,sizeof(c))!=0,"RSS query failed");return c.PeakWorkingSetSize;
}
struct Counters {std::uint64_t rgb=0,masks=0,poses=0,pools=0,layer_rows=0,attempt_rows=0,pyramids=0,downs=0,collector_calls=0,sampler_calls=0;};
struct Live {Counters count;std::string phase="preflight";std::uint64_t pose=0;unsigned level=0,arm=0;};
static Live live;
static std::string progress_json(const pack::Output& out,const char* reason=nullptr) {
 const auto& c=live.count;std::ostringstream s;
 s<<"{\"phase\":\""<<live.phase<<"\",\"pose_id\":"<<live.pose<<",\"level\":"<<live.level<<",\"arm\":"<<live.arm<<",\"completed_poses\":"<<c.poses<<",\"written_pools\":"<<c.pools<<",\"written_layer_rows\":"<<c.layer_rows<<",\"written_attempt_rows\":"<<c.attempt_rows<<",\"rgb_decodes\":"<<c.rgb<<",\"mask_decodes\":"<<c.masks<<",\"collector_calls_started\":"<<c.collector_calls<<",\"sampler_calls_started\":"<<c.sampler_calls<<",\"reserved_logical_bytes\":"<<out.logical()<<",\"reserved_physical_bytes\":"<<out.physical()<<",\"incomplete\":"<<(reason?"true":"false");
 if(reason){cv::FileStorage q("reason.json",cv::FileStorage::WRITE|cv::FileStorage::MEMORY|cv::FileStorage::FORMAT_JSON);q<<"reason"<<std::string(reason);const auto text=q.releaseAndGetString();s<<",\"error\":"<<text;}
 s<<"}\n";return s.str();
}
static void progress(pack::Output& out,const std::string& phase) {live.phase=phase;out.append("progress.jsonl",progress_json(out));}
static void checkpoint(const std::chrono::steady_clock::time_point& start) {
 need(peak_rss()<=1610612736ULL,"Training 1.5 GiB peak RSS ceiling");
 need(std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count()<=5400.,"Training 90-minute wall ceiling");
}
static const char* region(sample::Stratum s){return s==sample::Stratum::contour?"S":"I";}
static std::string selection_json(const sample::Result& r) {
 const auto& d=r.diagnostics;std::ostringstream s;s<<std::boolalpha;
 s<<"{\"status\":\""<<(r.status==sample::Status::ok?"ok":"insufficient_features")<<"\",\"diagnostics\":{";
 bool first=true;
 auto field=[&](const char* key,auto value){if(!first)s<<',';first=false;s<<'"'<<key<<"\":"<<value;};
 field("input_candidates",d.input_candidates);field("requested_budget",d.requested_budget);field("target",d.target);
 field("contour_candidates",d.contour_candidates);field("interior_candidates",d.interior_candidates);field("empty_contour",d.empty_contour);field("empty_interior",d.empty_interior);field("quotas_apply",d.quotas_apply);
 field("initial_contour_quota",d.initial_contour_quota);field("initial_interior_quota",d.initial_interior_quota);field("final_contour_quota",d.final_contour_quota);field("final_interior_quota",d.final_interior_quota);
 field("borrowed_into_contour",d.borrowed_into_contour);field("borrowed_into_interior",d.borrowed_into_interior);field("selected_contour",d.selected_contour);field("selected_interior",d.selected_interior);
 s<<"},\"selected_indices\":[";for(std::size_t i=0;i<r.selected_indices.size();++i){if(i)s<<',';s<<r.selected_indices[i];}
 s<<"],\"selected\":[";
 for(std::size_t i=0;i<r.selected.size();++i){if(i)s<<',';const auto& c=r.selected[i];s<<"{\"ordinal\":"<<c.ordinal<<",\"x\":"<<c.x<<",\"y\":"<<c.y<<",\"label\":"<<unsigned(c.label)<<",\"magnitude_bits\":"<<c.magnitude_bits<<",\"theta_bits\":"<<c.theta_bits<<",\"stratum\":\""<<region(c.stratum)<<"\"}";}
 s<<"],\"trace\":[";
 for(std::size_t i=0;i<r.trace.size();++i){if(i)s<<',';const auto& t=r.trace[i];s<<"{\"ordinal\":"<<t.ordinal<<",\"stratum\":\""<<region(t.stratum)<<"\",\"has_distance\":"<<t.has_distance<<",\"minimum_squared_distance\":"<<t.minimum_squared_distance<<'}';}
 s<<"]}";return s.str();
}
static std::string metadata_json(const std::vector<TemplateMeta>& meta) {
 cv::FileStorage out("metadata.json",cv::FileStorage::WRITE|cv::FileStorage::MEMORY|cv::FileStorage::FORMAT_JSON);out<<"templates"<<"[";
 for(const auto& m:meta){out<<"{"<<"class_id"<<m.class_id<<"template_id"<<m.id<<"training_image_id"<<m.image<<"angle"<<m.angle<<"scale"<<m.scale<<"tl_x"<<m.tl_x<<"tl_y"<<m.tl_y;writeBox(out,"warped_mask_bbox",m.silhouette);out<<"}";}out<<"]";return out.releaseAndGetString();
}
static void save_bank(pack::Output& out,const integ::SharedDetector& detector,const std::string& prefix,int obj,const std::vector<TemplateMeta>& meta) {
 need(!meta.empty() && detector.numTemplates()==int(meta.size()),"Zero/inconsistent successful object bank");
 const auto cls=classForObject(obj);cv::FileStorage storage("templates.yml",cv::FileStorage::WRITE|cv::FileStorage::MEMORY|cv::FileStorage::FORMAT_YAML);
 detector.writeClass(cls,storage);const auto text=storage.releaseAndGetString();
 out.consume_logical(text.size());const auto compressed=pack::gzip(pack::Bytes(text.begin(),text.end()),out.remaining_physical());const auto path=prefix+"/templates_"+cls+".yml.gz";
 out.append(path,compressed.data(),compressed.size());out.write(prefix+"/template_metadata.json",metadata_json(meta));
 cv::FileStorage config("config.json",cv::FileStorage::WRITE|cv::FileStorage::MEMORY|cv::FileStorage::FORMAT_JSON);writeConfig(config,Config{});
 config<<"target_objects"<<std::vector<int>{obj}<<"template_count"<<int(meta.size())<<"shared_candidate_pool"<<1<<"exact_feature_budgets"<<std::vector<int>{32,16};
 out.write(prefix+"/training_config.json",config.releaseAndGetString());
}
struct Pose {
 int object=0,image=0,angle=0;double scale=1;cv::Rect roi,box;int canvas=0;
};
static integ::PoseResult train_one(pack::Output& out,pack::Writer& writer,const cv::Mat& source,const cv::Mat& mask,const Pose& pose,Counters& count,
                                const std::chrono::steady_clock::time_point& start) {
 const auto pose_id=count.poses;
 live.pose=pose_id;live.level=0;live.arm=0;progress(out,"begin_pose");
 const auto hook=[&](std::uint64_t id,unsigned level,const auto& observed,const std::vector<sample::Candidate>& candidates,const sample::Result& pooled,const sample::Result& balanced) {
  live.level=level;progress(out,"write_complete_pool");
  need(id==pose_id && level<2 && count.pools==2*pose_id+level,"Shared pose/pool sequence differs");
  need(pooled.status==balanced.status,"P/B layer success mismatch");
  const auto& actual=observed.actual_mask;need(actual.type()==CV_8UC1 && !actual.empty(),"Actual layer mask missing");
  pack::Pool pool;pool.id=std::uint32_t(count.pools);pool.object=pose.object;pool.image=pose.image;pool.angle=pose.angle;pool.scale_bits=bits(float(pose.scale));pool.level=level;
  pool.width=actual.cols;pool.height=actual.rows;pool.budget=level?16:32;
  // Complete mask bytes, never encoded image files or selected-only observations.
  const auto mask_size=std::uint64_t(actual.cols)*actual.rows;
  need(mask_size<=out.cap().logical_bytes && candidates.size()<=out.cap().candidates,"Pool allocation limit");
  out.preflight_logical(64+mask_size+21ULL*candidates.size());pool.mask.reserve(std::size_t(mask_size));
  for(int y=0;y<actual.rows;++y)pool.mask.insert(pool.mask.end(),actual.template ptr<unsigned char>(y),actual.template ptr<unsigned char>(y)+actual.cols);
  pool.candidates.reserve(candidates.size());
  for(const auto& c:candidates){need(c.ordinal<=std::numeric_limits<std::uint32_t>::max(),"Canonical ordinal uint32 overflow");pool.candidates.push_back({std::uint32_t(c.ordinal),c.x,c.y,c.label,c.magnitude_bits,c.theta_bits});}
  const auto member=writer.append(pool);
  pack::Bytes dilated;dilated.reserve(std::size_t(mask_size));
  for(int y=0;y<observed.domain.rows;++y)dilated.insert(dilated.end(),observed.domain.template ptr<unsigned char>(y),observed.domain.template ptr<unsigned char>(y)+observed.domain.cols);
  for(std::size_t i=0;i<candidates.size();++i){const auto& c=candidates[i];need(c.x>=2 && c.y>=2 && c.x<actual.cols-2 && c.y<actual.rows-2 && observed.domain.template at<unsigned char>(c.y,c.x)!=0,"Candidate outside actual dilated scan domain");need(observed.candidates.at(i).ordinal==c.ordinal,"Candidate source order changed");}
  std::ostringstream observation;observation<<"{\"pool_id\":"<<pool.id<<",\"target\":"<<std::min<std::size_t>(pool.budget,candidates.size())<<",\"dilated_mask_sha256\":\""<<pack::sha256(dilated)<<"\",\"nms_maxima\":"<<observed.nms_maxima<<",\"validation\":{\"dense_ordinals\":true,\"unique_rowmajor_coords\":true,\"finite_magnitudes\":true,\"labels_0_to_7\":true,\"inside_scan_domain\":true,\"source_order_preserved\":true}}\n";out.append("pool_observations.jsonl",observation.str());
  for(unsigned arm=0;arm<2;++arm){std::ostringstream row;row<<"{\"pose_id\":"<<pose_id<<",\"pool_id\":"<<pool.id<<",\"arm\":\""<<(arm?"B":"P")<<"\",\"candidate_sha256\":\""<<member.candidate_sha256<<"\",\"result\":"<<selection_json(arm?balanced:pooled)<<"}\n";out.append("layer_selections.jsonl",row.str());++count.layer_rows;}
  ++count.pools;checkpoint(start);
 };
 const auto collect=[&](const cv::Mat& magnitude,const cv::Mat& angle,const cv::Mat& theta,const cv::Mat& actual_mask){
  live.level=unsigned(count.collector_calls%2);progress(out,"collector_call");++count.collector_calls;
  return rgb_stratified::collector::collect(magnitude,angle,theta,actual_mask);
 };
 const auto select=[&](const std::vector<sample::Candidate>& pool,std::size_t budget,sample::Mode mode){
  live.arm=mode==sample::Mode::balanced?1:0;progress(out,"sampler_call");++count.sampler_calls;return sample::sample(pool,budget,mode);
 };
 auto result=integ::train_pose_with(source,mask,pose_id,collect,select,hook);
 need(result.counts.gradient_pyramids==1 && result.counts.pyramid_downs==1 && result.counts.collector_calls[0]==1 && result.counts.collector_calls[1]==1,"Shared generator count changed");
 count.pyramids+=result.counts.gradient_pyramids;count.downs+=result.counts.pyramid_downs;++count.poses;progress(out,"pose_complete");return result;
}
static void attempt(pack::Output& out,const Pose& pose,std::uint64_t pose_id,unsigned arm,int id,const integ::ArmResult& result,Counters& count) {
 std::ostringstream row;row<<"{\"pose_id\":"<<pose_id<<",\"object_id\":"<<pose.object<<",\"image_id\":"<<pose.image<<",\"angle_degrees\":"<<pose.angle<<",\"scale\":"<<std::setprecision(17)<<pose.scale<<",\"arm\":\""<<(arm?"B":"P")<<"\",\"success\":"<<(result.success?"true":"false")<<",\"template_id\":"<<id<<",\"source_roi\":["<<pose.roi.x<<','<<pose.roi.y<<','<<pose.roi.width<<','<<pose.roi.height<<"],\"canvas\":"<<pose.canvas<<",\"warped_mask_bbox\":["<<pose.box.x<<','<<pose.box.y<<','<<pose.box.width<<','<<pose.box.height<<"],\"pool_ids\":["<<2*pose_id<<','<<2*pose_id+1<<"],\"crop_xywh\":["<<result.crop.x<<','<<result.crop.y<<','<<result.crop.width<<','<<result.crop.height<<"]}\n";
 out.append("attempts.jsonl",row.str());++count.attempt_rows;
}
static void save_summary(pack::Output& out,const Counters& c,const std::array<std::vector<int>,2>& counts,bool literal) {
 std::array<HMODULE,1024> modules{};DWORD needed=0;
 need(EnumProcessModules(GetCurrentProcess(),modules.data(),DWORD(sizeof(modules)),&needed)!=0 && needed<=sizeof(modules),"Loaded module inventory failed");
 std::vector<std::string> paths;
 for(std::size_t i=0;i<needed/sizeof(HMODULE);++i){std::array<wchar_t,32768> path{};const auto n=GetModuleFileNameExW(GetCurrentProcess(),modules[i],path.data(),DWORD(path.size()));need(n>0 && n<path.size(),"Loaded module path failed");paths.push_back(fs::path(path.data()).u8string());}
 cv::FileStorage inventory("modules.json",cv::FileStorage::WRITE|cv::FileStorage::MEMORY|cv::FileStorage::FORMAT_JSON);inventory<<"loaded_modules"<<paths;out.write("loaded_modules.json",inventory.releaseAndGetString());
 std::ostringstream s;s<<"{\"schema\":\"rgb_stratified_training_observation_v1\",\"complete\":true,\"literal_only\":"<<(literal?"true":"false")<<",\"shared_poses\":"<<c.poses<<",\"shared_pools\":"<<c.pools<<",\"arm_attempts\":"<<c.attempt_rows<<",\"arm_layer_rows\":"<<c.layer_rows<<",\"gradient_pyramids\":"<<c.pyramids<<",\"pyramid_downs\":"<<c.downs<<",\"rgb_decodes\":"<<c.rgb<<",\"mask_decodes\":"<<c.masks<<",\"total_imread_calls\":"<<c.rgb+c.masks<<",\"matcher_calls\":0,\"peak_rss_bytes\":"<<peak_rss()<<",\"logical_payload_bytes\":"<<out.logical()<<",\"physical_bytes_before_summary\":"<<out.physical()<<",\"successful_templates\":{";
 for(unsigned arm=0;arm<2;++arm){if(arm)s<<',';s<<'"'<<(arm?"B":"P")<<"\":[";for(std::size_t i=0;i<counts[arm].size();++i){if(i)s<<',';s<<counts[arm][i];}s<<']';}s<<"}}\n";out.write("training_summary.json",s.str());
}
static std::vector<std::string> split(const std::string& line) {std::vector<std::string> values;std::istringstream s(line);std::string v;while(std::getline(s,v,','))values.push_back(v);return values;}
using GeometryKey=std::tuple<int,int,double>;
static std::map<GeometryKey,std::array<int,9>> read_original(const fs::path& path,int obj) {
 std::ifstream stream(path);need(stream.good(),"Original attempt geometry missing");std::string line;std::getline(stream,line);
 need(line=="class_id,training_image,angle,scale,success,template_id,source_crop_x,source_crop_y,source_crop_w,source_crop_h,canvas,mask_x,mask_y,mask_w,mask_h,templ_tl_x,templ_tl_y,features_l0,features_l1,error","Original geometry schema changed");
 std::map<GeometryKey,std::array<int,9>> result;
 while(std::getline(stream,line)){if(!line.empty() && line.back()=='\r')line.pop_back();const auto row=split(line);need(row.size()==19 || row.size()==20,"Original geometry row invalid");need(row[0]==classForObject(obj),"Original geometry object differs");std::array<int,9> g{};for(int i=0;i<9;++i)g[i]=std::stoi(row[i+6]);need(result.emplace(GeometryKey{std::stoi(row[1]),std::stoi(row[2]),std::stod(row[3])},g).second,"Duplicate original pose");}
 need(result.size()==3456,"Original geometry coverage changed");return result;
}
static void train_all(pack::Output& out,pack::Writer& writer,const cv::FileStorage& inputs,Counters& counter,const std::chrono::steady_clock::time_point& start) {
 need(str(inputs["schema"])=="rgb_stratified_training_inputs_v1" && readObjectIds(inputs["objects"])==OBJECTS,"Wrong training input freeze");
 const fs::path dataset=str(inputs["dataset_root"]);std::array<std::vector<int>,2> successes;
 for(int obj:OBJECTS) {
  std::map<GeometryKey,std::array<int,9>> originals;for(const auto& row:inputs["original_attempts"])if(int(row["object_id"])==obj)originals=read_original(str(row["pin"]["path"]),obj);
  need(originals.size()==3456,"Missing original object attempts");std::set<GeometryKey> visited;
  std::array<integ::SharedDetector,2> detectors;std::array<std::vector<TemplateMeta>,2> metadata;int views=0;
  for(const auto& row:inputs["training"]) {
   if(int(row["object_id"])!=obj)continue;
   const int image_id=int(row["image_id"]);++views;
   ++counter.rgb;const auto image=cv::imread((dataset/str(row["rgb"])).string(),cv::IMREAD_GRAYSCALE);
   ++counter.masks;const auto mask=cv::imread((dataset/str(row["mask"])).string(),cv::IMREAD_GRAYSCALE);
   need(!image.empty() && !mask.empty() && image.type()==CV_8UC1 && mask.type()==CV_8UC1 && image.size()==mask.size(),"Training image/mask invalid");
   need(cv::countNonZero((mask!=0)&(mask!=255))==0,"Inherited training mask binary validation failed");
   const auto roi=maskBox(mask);const auto crop=image(roi),crop_mask=mask(roi);
   for(double scale:Config{}.scales)for(int angle=0;angle<360;angle+=30) {
    int side=int(std::ceil(std::hypot(roi.width,roi.height)*scale))+32;side=(side+15)/16*16;
    need(side>0 && side<=2048 && std::uint64_t(side)*side<=2097152ULL,"Training canvas allocation exceeds numeric-pack guard");
    auto affine=cv::getRotationMatrix2D({roi.width/2.f,roi.height/2.f},angle,scale);affine.at<double>(0,2)+=side/2.-roi.width/2.;affine.at<double>(1,2)+=side/2.-roi.height/2.;
    cv::Mat source,warped_mask;cv::warpAffine(crop,source,affine,{side,side},cv::INTER_LINEAR,cv::BORDER_CONSTANT,cv::Scalar(0));cv::warpAffine(crop_mask,warped_mask,affine,{side,side},cv::INTER_NEAREST,cv::BORDER_CONSTANT,cv::Scalar(0));
    const auto box=maskBox(warped_mask);const GeometryKey key{image_id,angle,scale};const auto original=originals.find(key);
    need(original!=originals.end() && visited.insert(key).second,"Unexpected/duplicate training pose");
    need(original->second==std::array<int,9>{{roi.x,roi.y,roi.width,roi.height,side,box.x,box.y,box.width,box.height}},"Pose geometry differs from C0");
    const Pose pose{obj,image_id,angle,scale,roi,box,side};const auto pose_id=counter.poses;
    const auto result=train_one(out,writer,source,warped_mask,pose,counter,start);need(result.arms[0].success==result.arms[1].success,"P/B template status mismatch");
    for(unsigned arm=0;arm<2;++arm){const int id=detectors[arm].inject(classForObject(obj),result.arms[arm]);attempt(out,pose,pose_id,arm,id,result.arms[arm],counter);
     if(id>=0){need(id==int(metadata[arm].size()),"Non-dense new bank ID");const auto& t=result.arms[arm].cropped[0];metadata[arm].push_back({id,image_id,t.tl_x,t.tl_y,float(angle),float(scale),{double(box.x),double(box.y),double(box.width),double(box.height)},classForObject(obj)});}}
    checkpoint(start);
   }
   std::cout<<"SHARED_TRAIN object "<<obj<<" image "<<image_id<<" cumulative_poses "<<counter.poses<<" successful "<<metadata[0].size()<<'/'<<metadata[1].size()<<std::endl;
  }
  need(views==72 && visited.size()==3456,"Incomplete object training views/poses");
  for(unsigned arm=0;arm<2;++arm){save_bank(out,detectors[arm],ARMS[arm]+"/obj"+std::to_string(obj),obj,metadata[arm]);successes[arm].push_back(int(metadata[arm].size()));}
 }
 need(counter.poses==20736 && counter.pools==41472 && counter.attempt_rows==41472 && counter.layer_rows==82944 && counter.rgb==432 && counter.masks==432 && counter.collector_calls==41472 && counter.sampler_calls==82944,"Incomplete shared training coverage");writer.close();save_summary(out,counter,successes,false);
}
static void literal(pack::Output& out,pack::Writer& writer,Counters& count,const std::chrono::steady_clock::time_point& start) {
 cv::Mat source(256,256,CV_8UC1,cv::Scalar(0)),mask(256,256,CV_8UC1,cv::Scalar(0));cv::rectangle(mask,{16,16,224,224},cv::Scalar(255),cv::FILLED);
 for(int y=0;y<256;++y)for(int x=0;x<256;++x)source.at<unsigned char>(y,x)=((x/32+y/32)%2)?220:25;
 const Pose pose{1,0,0,1,{0,0,256,256},maskBox(mask),256};const auto result=train_one(out,writer,source,mask,pose,count,start);
 std::array<std::vector<int>,2> successes;
 for(unsigned arm=0;arm<2;++arm){integ::SharedDetector d;int id=d.inject(classForObject(1),result.arms[arm]);need(id==0,"Literal complete pose must succeed");attempt(out,pose,0,arm,id,result.arms[arm],count);const auto& t=result.arms[arm].cropped[0];
  std::vector<TemplateMeta> m{{id,0,t.tl_x,t.tl_y,0,1,{double(pose.box.x),double(pose.box.y),double(pose.box.width),double(pose.box.height)},classForObject(1)}};save_bank(out,d,ARMS[arm]+"/obj1",1,m);successes[arm].push_back(1);}
 writer.close();save_summary(out,count,successes,true);
}
int main(int argc,char** argv) {
 fs::path output;std::unique_ptr<pack::Output> owned;
 try {
  std::map<std::string,std::string> args;for(int i=1;i<argc;i+=2){need(i+1<argc,"Arguments need values");need(args.emplace(argv[i],argv[i+1]).second,"Duplicate argument");}
  for(const auto& arg:args)need(arg.first=="--mode" || arg.first=="--output" || arg.first=="--inputs","Unknown argument");
  const auto mode=args.at("--mode");need(mode=="literal" || mode=="train","Unsupported stage");output=fs::absolute(args.at("--output"));
  cv::setNumThreads(1);
#ifdef _OPENMP
  omp_set_num_threads(4);omp_set_dynamic(0);
#endif
  // Reserve 64MiB for execution logs and 64KiB for native failure evidence.
  pack::Limits limits;limits.physical_bytes-=67108864ULL+65536ULL;limits.logical_bytes-=65536ULL;
  owned=std::make_unique<pack::Output>(output,limits);auto& out=*owned;pack::Writer writer(out);auto& count=live.count;const auto start=std::chrono::steady_clock::now();
  if(mode=="literal"){need(args.count("--inputs")==0,"Literal mode cannot open input declarations");literal(out,writer,count,start);}
  else {cv::FileStorage input(args.at("--inputs"),cv::FileStorage::READ);need(input.isOpened(),"Training inputs unavailable");train_all(out,writer,input,count,start);}
  return 0;
 } catch(const std::exception& error){
  if(owned)try{const auto evidence=progress_json(*owned,error.what());need(evidence.size()<=65536,"Failure evidence reserve exhausted");std::ofstream file(output/"native_failure.json",std::ios::binary);file<<evidence;file.close();}catch(...){}
  std::cerr<<"SHARED TRAINING FAILED: "<<error.what()<<std::endl;return 1;
 }
}

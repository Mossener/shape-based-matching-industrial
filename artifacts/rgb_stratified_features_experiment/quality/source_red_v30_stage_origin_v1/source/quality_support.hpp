#ifndef RGB_STRATIFIED_QUALITY_SUPPORT_HPP
#define RGB_STRATIFIED_QUALITY_SUPPORT_HPP
// V31 support adapted from V30; native compilation/selftests remain pending.
// Public dataset/metadata/box/NMS/raw helpers are
// included unchanged by quality_eval.cpp from the existing frozen helpers.
// The exact/raw/pipeline conventions derive from the retained obj8 adapter;
// this file is a separately source-pinned implementation, not an unchanged copy.
#include <cstring>
#include <cstdint>
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

namespace rgb_stratified_quality {
using Clock=std::chrono::steady_clock;
static const std::vector<int> OBJECTS{1,2,5,8,12,17};
static const std::array<std::string,3> ARMS{{"rgb_control","rgb_pooled_features","rgb_stratified_features"}};
static const std::array<std::string,2> PATHS{{"fallback","fused"}};
static void need(bool value,const std::string& reason){if(!value)throw std::runtime_error(reason);}
static std::uint64_t calls=0,lastNativeRaw=0,rawBytes=0,maximumCalls=0;
static double milliseconds(Clock::duration duration){return std::chrono::duration<double,std::milli>(duration).count();}
static std::uint64_t peakRss(){PROCESS_MEMORY_COUNTERS c{};c.cb=sizeof(c);need(GetProcessMemoryInfo(GetCurrentProcess(),&c,sizeof(c))!=0,"Cannot query peak RSS");return c.PeakWorkingSetSize;}
static void checkpoint(const Clock::time_point& start,int minutes){need(peakRss()<=1610612736ULL,"Peak RSS exceeds 1.5 GiB");need(milliseconds(Clock::now()-start)<=minutes*60000.,"Stage soft checkpoint exceeded");}
static std::uint32_t scoreBits(float score){std::uint32_t bits;std::memcpy(&bits,&score,sizeof bits);return bits;}
static bool exact(const Detection& a,const Detection& b){return a.class_id==b.class_id && a.template_id==b.template_id && a.match_x==b.match_x && a.match_y==b.match_y && scoreBits(a.score)==scoreBits(b.score) && a.box.x==b.box.x && a.box.y==b.box.y && a.box.w==b.box.w && a.box.h==b.box.h;}
static bool exactRows(const std::vector<Detection>& a,const std::vector<Detection>& b){if(a.size()!=b.size())return false;for(std::size_t i=0;i<a.size();++i)if(!exact(a[i],b[i]))return false;return true;}
static std::vector<std::string> fields(const std::string& line){std::stringstream stream(line);std::vector<std::string> cells;std::string cell;while(std::getline(stream,cell,','))cells.push_back(cell);return cells;}
static std::vector<Detection> readRaw(const fs::path& file,const Frame& frame,const std::string& path,const std::vector<TemplateMeta>& meta){
    gzFile input=gzopen(file.string().c_str(),"rb");need(input!=nullptr,"Missing raw reference");std::string text;char block[65536];int count=0;
    while((count=gzread(input,block,sizeof block))>0){text.append(block,std::size_t(count));if(text.size()>1073741824ULL){gzclose(input);throw std::runtime_error("Raw reference exceeds one GiB decoded safety bound");}}
    const int closed=gzclose(input);need(count>=0 && closed==Z_OK,"Raw reference gzip CRC/read failure");
    std::stringstream lines(text);std::string row;std::getline(lines,row);
    need(row=="scene,image,variant,class_id,rank,score,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h","Raw schema changed");
    std::vector<Detection> result;
    while(std::getline(lines,row)){
        const auto c=fields(row);need(c.size()==16,"Raw CSV width changed");
        need(std::stoi(c[0])==frame.scene && std::stoi(c[1])==frame.image && c[2]==path && std::stoull(c[4])==result.size(),"Raw frame/path/rank changed");
        Detection d;d.class_id=c[3];d.score=std::stof(c[5]);d.template_id=std::stoi(c[6]);d.match_x=std::stoi(c[10]);d.match_y=std::stoi(c[11]);d.box={std::stod(c[12]),std::stod(c[13]),std::stod(c[14]),std::stod(c[15])};
        const auto& m=findMeta(meta,d.class_id,d.template_id);const auto expected=boxAtMatch(d.match_x,d.match_y,64,m.silhouette,m.tl_x,m.tl_y);
        need(std::isfinite(d.score) && d.score>=85 && std::stoi(c[7])==m.image && std::stof(c[8])==m.angle && std::stof(c[9])==m.scale && d.box.x==expected.x && d.box.y==expected.y && d.box.w==expected.w && d.box.h==expected.h,"Raw pose/official-box mapping changed");
        need(result.empty() || !canonicalLess(d,result.back()),"Raw canonical ordering changed");result.push_back(d);need(result.size()<=1000000,"Raw reference candidate ceiling exceeded");
    }return result;
}
struct Padding{int width=0,height=0;std::array<int,4> ltrb{};};
static Padding padding(const cv::FileStorage& input){Padding p;p.width=int(input["width"]);p.height=int(input["height"]);const auto a=input["padding_ltrb"];need(a.size()==4,"Padding vector changed");for(int i=0;i<4;++i)p.ltrb[i]=int(a[i]);need(p.ltrb[0]==64 && p.ltrb[1]==64 && p.ltrb[2]>=64 && p.ltrb[3]>=228 && p.width>=848 && p.height>=832 && p.width==720+p.ltrb[0]+p.ltrb[2] && p.height==540+p.ltrb[1]+p.ltrb[3] && p.width%16==0 && p.height%16==0 && p.width<=2048 && p.height<=2048 && std::uint64_t(p.width)*p.height<=2097152 && std::uint64_t(p.width)*p.height*512<=1073741824ULL,"Common padding/resource identity changed");return p;}
struct Bank{int object=0;std::string arm;fs::path directory;std::vector<TemplateMeta> meta;std::unique_ptr<line2Dup::Detector> detector;double metadataMs=0,bankMs=0;};
static Bank loadBank(const fs::path& directory,int object,int expected,const std::string& arm){
    Bank b;b.directory=directory;b.object=object;b.arm=arm;const auto begin=Clock::now();b.meta=readMeta(directory/"template_metadata.json");const auto middle=Clock::now();b.metadataMs=milliseconds(middle-begin);
    b.detector=std::make_unique<line2Dup::Detector>(32,std::vector<int>{4,8},20,40);const auto cls=classForObject(object);b.detector->readClasses({cls},(directory/"templates_%s.yml.gz").string());b.bankMs=milliseconds(Clock::now()-middle);
    need(expected>0 && int(b.meta.size())==expected && b.detector->numTemplates()==expected && b.detector->numTemplates(cls)==expected && b.detector->classIds()==std::vector<std::string>{cls},"Loaded bank object/count identity changed");
    for(int id=0;id<expected;++id){const auto& m=b.meta.at(id);const auto& layers=b.detector->getTemplates(cls,id);need(m.id==id && m.class_id==cls && layers.size()==2 && layers[0].tl_x==m.tl_x && layers[0].tl_y==m.tl_y && !layers[0].features.empty() && !layers[1].features.empty(),"Loaded bank metadata/origin mismatch");}
    return b;
}
struct Pipeline{std::vector<Detection> raw,selected;double matchMs=0,totalMs=0;};
static Pipeline call(Bank& bank,const cv::Mat& image,const Padding& pad,line2Dup::MatchWorkspace& workspace,bool fused){
    const auto begin=Clock::now();cv::Mat padded;cv::copyMakeBorder(image,padded,pad.ltrb[1],pad.ltrb[3],pad.ltrb[0],pad.ltrb[2],cv::BORDER_CONSTANT,cv::Scalar(0));need(padded.cols==pad.width && padded.rows==pad.height,"Actual padding changed");
    line2Dup::MatchOptions options;options.fused_local_search=fused;const auto matchBegin=Clock::now();need(calls<maximumCalls,"Fixed matcher budget exhausted before call");++calls;
    const auto matches=bank.detector->match(padded,85.f,workspace,options,nullptr,{classForObject(bank.object)});const auto matchEnd=Clock::now();lastNativeRaw=matches.size();need(matches.size()<=1000000,"Native raw ceiling exceeded; archive incomplete, no quality metrics valid");
    Pipeline result;result.raw=convert(matches,bank.meta,64);result.selected=postprocess(result.raw,Config{},85);const auto end=Clock::now();result.matchMs=milliseconds(matchEnd-matchBegin);result.totalMs=milliseconds(end-begin);return result;
}
static void archive(const fs::path& directory,const Frame& frame,const std::string& path,const Pipeline& result,const Bank& bank){
    fs::create_directories(directory);writeRaw(directory,frame,path,result.raw,bank.meta);const auto key=frameKey(frame)+"_"+path;
    rawBytes+=fs::file_size(directory/(key+"_raw.csv.gz"))+fs::file_size(directory/(key+"_raw_manifest.json"));need(rawBytes<=1073741824ULL,"New complete raw output exceeds one GiB; stage incomplete");
}
struct Totals{Counts all{},eligible{};std::uint64_t raw=0;int negativeFrames=0,negativeWithFP=0,negativeFP=0;};
static void append(Totals& total,const Counts& all,const Counts& eligible,bool negative,std::size_t raw){add(total.all,all);add(total.eligible,eligible);total.raw+=raw;total.negativeFrames+=negative;total.negativeWithFP+=negative && all.fp>0;total.negativeFP+=negative?all.fp:0;}
static void writeTotals(cv::FileStorage& out,const std::string& name,const Totals& total){out<<name<<"{";writeCounts(out,"allGT",total.all);writeCounts(out,"visibility_ge_0_5",total.eligible);out<<"raw_candidates"<<double(total.raw)<<"negative_frames"<<total.negativeFrames<<"negative_frames_with_fp"<<total.negativeWithFP<<"negative_fp"<<total.negativeFP<<"}";}
static double percentile(std::vector<double> values,double q){need(!values.empty(),"Empty timing sample");std::sort(values.begin(),values.end());return values[std::max<std::size_t>(1,std::size_t(std::ceil(q*values.size())))-1];}
static void selftest(const fs::path& output){
    Detection zero;zero.score=0.f;Detection negative=zero;negative.score=-0.f;need(!exact(zero,negative),"Exact comparison lost float32 sign bit");
    std::vector<Detection> ordered(2);ordered[1].match_x=1;auto reversed=ordered;std::reverse(reversed.begin(),reversed.end());need(!exactRows(ordered,reversed),"Exact comparison lost ordered identity");
    Frame f;f.rgb="synthetic/no-dataset-image";std::vector<TemplateMeta> meta{{0,7,11,13,30,1.5,{17,19,23,29},classForObject(1)}};std::vector<Detection> raw;
    for(int i=0;i<2048;++i){Detection d;d.class_id=classForObject(1);d.template_id=0;d.match_x=i;d.match_y=-i;d.score=std::nextafter(85.f+float(i%10),100.f);d.box=boxAtMatch(d.match_x,d.match_y,64,meta[0].silhouette,meta[0].tl_x,meta[0].tl_y);raw.push_back(d);}std::sort(raw.begin(),raw.end(),canonicalLess);
    writeRaw(output,f,"fallback",raw,meta);need(exactRows(raw,readRaw(output/"s0_i0_fallback_raw.csv.gz",f,"fallback",meta)),"Full-field score-bit raw roundtrip failed");writeRaw(output,f,"fused",{},meta);need(readRaw(output/"s0_i0_fused_raw.csv.gz",f,"fused",meta).empty(),"Empty raw roundtrip failed");
    const auto other=boxAtMatch(100,200,64,{17,19,23,29},31,37);need(other.x==22 && other.y==118 && other.w==23 && other.h==29,"Actual arm-origin official box conversion differs");
    cv::Mat image(540,720,CV_8U,cv::Scalar(37)),padded;cv::copyMakeBorder(image,padded,64,228,64,64,cv::BORDER_CONSTANT,cv::Scalar(0));need(padded.cols==848 && padded.rows==832 && padded.at<unsigned char>(64,64)==37 && padded.at<unsigned char>(63,64)==0,"Shared source origin differs");
    cv::FileStorage out((output/"selftest_result.json").string(),cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);out<<"passed"<<1<<"exact_raw_rows"<<2048<<"score_bits_and_order_oracles"<<1<<"actual_arm_origin_box_oracle"<<1<<"dataset_image_reads"<<0<<"matcher_calls"<<0;
}
}
#endif

// Read-only serialized-feature geometry observer; no matcher linkage.
#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <zlib.h>
#define NOMINMAX
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <psapi.h>
#include <bcrypt.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
namespace fs=std::filesystem;
static void need(bool v,const std::string& s){if(!v)throw std::runtime_error(s);}
static std::string text(const cv::FileNode& n){std::string s;n>>s;return s;}
static std::uint32_t bits(float v){std::uint32_t b;std::memcpy(&b,&v,4);return b;}
class SHA{
 BCRYPT_ALG_HANDLE a=nullptr;BCRYPT_HASH_HANDLE h=nullptr;std::vector<unsigned char> storage;
 public:
 SHA(){need(BCryptOpenAlgorithmProvider(&a,BCRYPT_SHA256_ALGORITHM,nullptr,0)>=0,"SHA provider");DWORD n=0,size=0;need(BCryptGetProperty(a,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&size),sizeof size,&n,0)>=0,"SHA size");storage.resize(size);need(BCryptCreateHash(a,&h,storage.data(),size,nullptr,0,0)>=0,"SHA create");}
 void update(const void*p,std::size_t n){need(n<=0xffffffffULL,"SHA chunk");need(BCryptHashData(h,reinterpret_cast<PUCHAR>(const_cast<void*>(p)),ULONG(n),0)>=0,"SHA update");}
 std::string finish(){std::array<unsigned char,32>b{};need(BCryptFinishHash(h,b.data(),b.size(),0)>=0,"SHA finish");std::ostringstream s;s<<std::hex<<std::setfill('0');for(auto v:b)s<<std::setw(2)<<int(v);return s.str();}
 ~SHA(){if(h)BCryptDestroyHash(h);if(a)BCryptCloseAlgorithmProvider(a,0);}
};
static std::pair<std::string,std::uint64_t> hashFile(const fs::path&p){std::ifstream in(p,std::ios::binary);need(in.good(),"Allowed-file hash open");SHA s;std::array<char,65536>b{};std::uint64_t n=0;while(in){in.read(b.data(),b.size());auto got=in.gcount();if(got){s.update(b.data(),std::size_t(got));n+=got;}}need(in.eof(),"Allowed-file hash read");return{s.finish(),n};}
static std::uint64_t peak(){PROCESS_MEMORY_COUNTERS c{};c.cb=sizeof c;need(GetProcessMemoryInfo(GetCurrentProcess(),&c,sizeof c)!=0,"RSS query");return c.PeakWorkingSetSize;}
static void checkpoint(const fs::path& p){need(peak()<=1610612736ULL,"RSS ceiling");std::uint64_t n=0;for(auto& f:fs::directory_iterator(p))if(f.is_regular_file())n+=f.file_size();need(n<=2147483648ULL,"Numeric-output ceiling");}
class Gzip{
 gzFile f=nullptr;
 public:
 explicit Gzip(const fs::path&p){need(!fs::exists(p),"Gzip output exists");f=gzopen(p.string().c_str(),"wb6");need(f!=nullptr,"Gzip open");}
 void write(const std::string&s){need(s.size()<=0x7fffffff,"Gzip chunk");need(gzwrite(f,s.data(),unsigned(s.size()))==int(s.size()),"Gzip write");}
 void close(){if(f){auto old=f;f=nullptr;need(gzclose(old)==Z_OK,"Gzip close");}}
 ~Gzip(){if(f)gzclose(f);}
};
struct Feature{int x,y,label;};struct Layer{int x=0,y=0;std::vector<Feature> f;};struct Bank{std::string family;int object=0;std::vector<std::array<Layer,2>> templates;};
static Bank loadBank(const cv::FileNode& n){Bank b;b.family=text(n["family"]);b.object=int(n["object_id"]);cv::FileStorage in(text(n["bank_path"]),cv::FileStorage::READ);need(in.isOpened(),"Bank unavailable");need(text(in["class_id"])==text(n["class_id"])&&int(in["pyramid_levels"])==2,"Bank class/pyramid");int id=0;for(auto root:in["template_pyramids"]){need(int(root["template_id"])==id++,"Bank dense ID");need(root["templates"].size()==2,"Bank layer count");std::array<Layer,2> layers;int lev=0;for(auto node:root["templates"]){Layer l;l.x=int(node["tl_x"]);l.y=int(node["tl_y"]);need(int(node["pyramid_level"])==lev,"Bank level order");for(auto f:node["features"]){need(f.size()==3,"Feature tuple");Feature q{int(f[0]),int(f[1]),int(f[2])};need(q.label>=0&&q.label<8,"Feature label");l.f.push_back(q);}need(!l.f.empty(),"Empty successful layer");layers[lev++]=std::move(l);}b.templates.push_back(std::move(layers));}need(int(b.templates.size())==int(n["expected_templates"]),"Bank count");return b;}
static cv::Rect box(const cv::Mat&m){std::vector<cv::Point>p;cv::findNonZero(m,p);need(!p.empty(),"Empty official mask");return cv::boundingRect(p);}
static std::string prefix(int o,int i,int a,double s){std::ostringstream q;q<<"\"object_id\":"<<o<<",\"image\":"<<i<<",\"angle\":"<<a<<",\"scale\":"<<std::setprecision(17)<<s;return q.str();}
static void saveMap(Gzip&out,const cv::Mat&m,const std::string&name,const std::string&key,bool alpha){SHA sha;std::ostringstream s;s<<"{"<<key<<",\"name\":\""<<name<<"\",\"map\":{\"width\":"<<m.cols<<",\"height\":"<<m.rows<<",\"dtype\":\""<<(alpha?"f32bits":"u8")<<"\",\"rows\":[";for(int y=0;y<m.rows;++y){if(y)s<<",";s<<"[";std::vector<unsigned char> hashRow(alpha?std::size_t(m.cols)*4:0);std::uint32_t old=0;int run=0;bool first=true;auto emit=[&](){if(!first)s<<",";first=false;s<<"["<<old<<","<<run<<"]";};for(int x=0;x<m.cols;++x){std::uint32_t v=alpha?bits(m.at<float>(y,x)):m.at<unsigned char>(y,x);if(alpha){float a=m.at<float>(y,x);need(std::isfinite(a)&&a>=0&&a<=1,"Alpha range");hashRow[x*4]=static_cast<unsigned char>(v);hashRow[x*4+1]=static_cast<unsigned char>(v>>8);hashRow[x*4+2]=static_cast<unsigned char>(v>>16);hashRow[x*4+3]=static_cast<unsigned char>(v>>24);}if(run&&v!=old){emit();run=0;}old=v;++run;}if(run)emit();if(alpha)sha.update(hashRow.data(),hashRow.size());else sha.update(m.ptr<unsigned char>(y),m.cols);s<<"]";}s<<"],\"sha256\":\""<<sha.finish()<<"\"}}\n";out.write(s.str());}
struct Geometry{cv::Mat m0,m1,b1,a0,a1;};
static Geometry geometry(const cv::Mat& crop,int angle,double scale,int side){
 Geometry g;cv::Mat affine=cv::getRotationMatrix2D({crop.cols/2.f,crop.rows/2.f},angle,scale);
 affine.at<double>(0,2)+=side/2.-crop.cols/2.;affine.at<double>(1,2)+=side/2.-crop.rows/2.;
 cv::warpAffine(crop,g.m0,affine,{side,side},cv::INTER_NEAREST,cv::BORDER_CONSTANT,cv::Scalar(0));
 cv::resize(g.m0,g.m1,{side/2,side/2},0,0,cv::INTER_NEAREST);cv::pyrDown(g.m0,g.b1,{side/2,side/2});
 cv::Mat one(crop.rows,crop.cols,CV_32F,cv::Scalar(1));cv::warpAffine(one,g.a0,affine,{side,side},cv::INTER_LINEAR,cv::BORDER_CONSTANT,cv::Scalar(0));cv::pyrDown(g.a0,g.a1,{side/2,side/2});return g;
}
static void selftest(const fs::path& output){
 need(!fs::exists(output),"Synthetic output must be fresh");fs::create_directories(output);SHA sha;sha.update("abc",3);need(sha.finish()=="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad","SHA literal");
 Gzip pack(output/"fixtures.jsonl.gz");
 for(int fixture=0;fixture<7;++fixture){cv::Mat crop(fixture==4?3:4,fixture==4?5:4,CV_8U,cv::Scalar(255));if(fixture==1||fixture==5)crop.at<unsigned char>(1,1)=0;if(fixture==2){crop.setTo(0);for(int i=0;i<4;++i)crop.at<unsigned char>(i,i)=255;}if(fixture==3){crop.setTo(0);crop.row(0).setTo(255);crop.col(0).setTo(255);}int angle=fixture==5?90:0;double scale=fixture==6?2.:1.;auto g=geometry(crop,angle,scale,16);need(g.m0.rows==16&&g.m1.rows==8,"Synthetic dimensions");if(fixture<4)for(int y=0;y<16;++y)for(int x=0;x<16;++x){int expected=(x>=6&&x<10&&y>=6&&y<10)?crop.at<unsigned char>(y-6,x-6):0;need(g.m0.at<unsigned char>(y,x)==expected,"Synthetic affine literal");}for(int y=0;y<8;++y)for(int x=0;x<8;++x)need(g.m1.at<unsigned char>(y,x)==g.m0.at<unsigned char>(2*y,2*x),"Synthetic nearest half");
 if(fixture==0){need(g.b1.at<unsigned char>(3,3)==121&&g.b1.at<unsigned char>(4,4)==224,"Synthetic gray pyrDown");need(g.a1.at<float>(3,3)==121.f/256&&g.a1.at<float>(4,4)==225.f/256,"Synthetic alpha pyrDown");}
 auto key=prefix(0,fixture,angle,scale);saveMap(pack,g.m0,"M0",key,false);saveMap(pack,g.m1,"M1",key,false);saveMap(pack,g.b1,"B1",key,false);saveMap(pack,g.a0,"A0",key,true);saveMap(pack,g.a1,"A1",key,true);
 }pack.close();std::ofstream summary(output/"selftest.json");summary<<"{\"passed\":true,\"fixtures\":7,\"image_decodes\":0,\"matcher_calls\":0}\n";
}
static void observe(const fs::path& inputs,const fs::path& output){
 cv::FileStorage in(inputs.string(),cv::FileStorage::READ|cv::FileStorage::FORMAT_JSON);need(in.isOpened(),"Observer input unavailable");need(text(in["schema"])=="template_feature_observer_inputs_v1","Input schema");need(in["masks"].size()==432&&in["banks"].size()==18&&in["poses"].size()==20736,"Input coverage");std::vector<std::string> families;for(auto f:in["families"])families.push_back(text(f));need(families==std::vector<std::string>{"rgb_official_mask","binary_empty_mask","rgb_empty_mask"},"Family order");need(!fs::exists(output),"Native output must be fresh");fs::create_directories(output);std::vector<Bank> banks;for(auto b:in["banks"])banks.push_back(loadBank(b));
 std::map<std::pair<int,int>,cv::FileNode> masks;std::set<int> allowed{1,2,5,8,12,17};for(auto m:in["masks"]){int o=int(m["object_id"]),i=int(m["image_id"]);need(allowed.count(o),"Forbidden object");fs::path p=text(m["path"]);std::ostringstream fn,on;fn<<std::setw(6)<<std::setfill('0')<<i<<"_000000.png";on<<std::setw(6)<<std::setfill('0')<<o;need(p.filename()==fn.str()&&p.parent_path().filename()=="mask"&&p.parent_path().parent_path().filename()==on.str()&&p.parent_path().parent_path().parent_path().filename()=="train_primesense","Forbidden mask path");need(masks.emplace(std::make_pair(o,i),m).second,"Duplicate mask");}
 std::map<std::pair<int,int>,std::vector<cv::FileNode>> poses;for(auto p:in["poses"]){std::pair<int,int>k{int(p["object_id"]),int(p["image"])};need(masks.count(k),"Pose mask missing");poses[k].push_back(p);}
 Gzip features(output/"feature_observations.csv.gz");features.write("family,object_id,image,angle,scale,template_id,level,feature_ordinal,local_x,local_y,tl_x,tl_y,absolute_x,absolute_y,label,official_value,binary_value,alpha_bits,bbox_x,bbox_y,bbox_w,bbox_h\n");std::ofstream reads(output/"mask_reads.csv");reads<<"object_id,image,bytes,sha256,decoded_width,decoded_height\n";std::uint64_t decodes=0,pc=0,fc=0;
 for(auto&entry:masks){auto k=entry.first;auto m=entry.second;fs::path path=text(m["path"]);auto before=hashFile(path);need(before.first==text(m["sha256"])&&before.second==std::uint64_t(double(m["bytes"])),"Mask before pin");++decodes;cv::Mat full=cv::imread(path.string(),cv::IMREAD_GRAYSCALE);need(!full.empty()&&full.type()==CV_8UC1,"Mask decode");for(int y=0;y<full.rows;++y)for(int x=0;x<full.cols;++x)need(full.at<unsigned char>(y,x)==0||full.at<unsigned char>(y,x)==255,"Nonbinary mask");cv::Rect roi=box(full);std::ostringstream name;name<<"maps_o"<<k.first<<"_i"<<k.second<<".jsonl.gz";Gzip maps(output/name.str());need(poses[k].size()==48,"Per-view pose coverage");
  for(auto p:poses[k]){std::vector<int>g;for(auto v:p["geometry"])g.push_back(int(v));need(g.size()==9&&roi==cv::Rect(g[0],g[1],g[2],g[3]),"Mask ROI mismatch");int angle=int(p["angle"]);double scale=double(p["scale"]);int side=int(std::ceil(std::hypot(g[2],g[3])*scale))+32;side=(side+15)/16*16;need(side==g[4],"Canvas formula");auto gm=geometry(full(roi),angle,scale,side);auto& m0=gm.m0;auto& m1=gm.m1;auto& b1=gm.b1;auto& a0=gm.a0;auto& a1=gm.a1;need(box(m0)==cv::Rect(g[5],g[6],g[7],g[8]),"Official warped bbox");auto key=prefix(k.first,k.second,angle,scale);saveMap(maps,m0,"M0",key,false);saveMap(maps,m1,"M1",key,false);saveMap(maps,b1,"B1",key,false);saveMap(maps,a0,"A0",key,true);saveMap(maps,a1,"A1",key,true);
   std::vector<int>ids;for(auto id:p["template_ids"])ids.push_back(int(id));need(ids.size()==3,"Pose IDs");int familyIndex=0;for(const auto&family:families){auto b=std::find_if(banks.begin(),banks.end(),[&](const Bank&q){return q.object==k.first&&q.family==family;});need(b!=banks.end(),"Missing family bank");int id=ids[familyIndex];auto counts=p["expected_counts"][familyIndex++];need(counts.size()==2,"Layer counts");if(id<0){need(int(counts[0])==-1&&int(counts[1])==-1,"Failed placeholder");continue;}need(std::size_t(id)<b->templates.size(),"Template ID outside bank");for(int lev=0;lev<2;++lev){const Layer& l=b->templates[id][lev];const cv::Mat& mm=lev?m1:m0;const cv::Mat& bb=lev?b1:m0;const cv::Mat& aa=lev?a1:a0;auto bbox=box(mm);need(l.f.size()==std::size_t(int(counts[lev])),"Serialized feature count");int ordinal=0;std::ostringstream rows;for(auto f:l.f){int x=f.x+l.x,y=f.y+l.y;need(x>=0&&y>=0&&x<mm.cols&&y<mm.rows,"Feature outside canvas");rows<<family<<","<<k.first<<","<<k.second<<","<<angle<<","<<std::setprecision(17)<<scale<<","<<id<<","<<lev<<","<<ordinal++<<","<<f.x<<","<<f.y<<","<<l.x<<","<<l.y<<","<<x<<","<<y<<","<<f.label<<","<<int(mm.at<unsigned char>(y,x))<<","<<int(bb.at<unsigned char>(y,x))<<","<<bits(aa.at<float>(y,x))<<","<<bbox.x<<","<<bbox.y<<","<<bbox.width<<","<<bbox.height<<"\n";++fc;}features.write(rows.str());}}
   ++pc;
  }
  maps.close();need(hashFile(path)==before,"Mask after pin");reads<<k.first<<","<<k.second<<","<<before.second<<","<<before.first<<","<<full.cols<<","<<full.rows<<"\n";need(reads.good(),"Mask receipt write");checkpoint(output);
 }
 features.close();reads.close();need(decodes==432&&pc==20736,"Executed coverage");std::ofstream summary(output/"execution_summary.json");summary<<"{\"passed\":true,\"training_mask_imread_calls\":"<<decodes<<",\"poses\":"<<pc<<",\"class_bank_loads\":18,\"feature_rows\":"<<fc<<",\"peak_rss_bytes\":"<<peak()<<",\"matcher_calls\":0,\"addTemplate_calls\":0,\"gradient_extraction_calls\":0,\"rgb_image_decodes\":0,\"development_image_decodes\":0,\"heldout_image_decodes\":0}\n";summary.close();checkpoint(output);
}
int main(int argc,char**argv){try{need(argc==3,"Usage: observer INPUT_JSON FRESH_OUTPUT or --selftest FRESH_OUTPUT");if(std::string(argv[1])=="--selftest")selftest(argv[2]);else observe(argv[1],argv[2]);return 0;}catch(const std::exception&e){std::cerr<<"OBSERVER_FAILURE "<<e.what()<<"\n";return 1;}}

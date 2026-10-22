#ifndef RGB_STRATIFIED_NUMERIC_PACK_HPP
#define RGB_STRATIFIED_NUMERIC_PACK_HPP
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <bcrypt.h>
#include <zlib.h>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

namespace rgb_stratified { namespace packing {
using Bytes=std::vector<unsigned char>;
namespace fs=std::filesystem;
inline void need(bool v,const std::string& message) {if(!v)throw std::runtime_error(message);}
class SHA {
 BCRYPT_ALG_HANDLE algorithm=nullptr; BCRYPT_HASH_HANDLE hash=nullptr; Bytes storage;
 public:
 SHA() {
  need(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)>=0,"SHA provider");
  DWORD bytes=0,returned=0;
  need(BCryptGetProperty(algorithm,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&bytes),sizeof(bytes),&returned,0)>=0,"SHA object length");
  storage.resize(bytes);need(BCryptCreateHash(algorithm,&hash,storage.data(),bytes,nullptr,0,0)>=0,"SHA create");
 }
 SHA(const SHA&)=delete; SHA& operator=(const SHA&)=delete;
 void update(const void* p,std::size_t n) {
  need(n<=std::numeric_limits<ULONG>::max(),"SHA input chunk limit");
  need(BCryptHashData(hash,reinterpret_cast<PUCHAR>(const_cast<void*>(p)),ULONG(n),0)>=0,"SHA update");
 }
 std::string finish() {
  std::array<unsigned char,32> result{};need(BCryptFinishHash(hash,result.data(),ULONG(result.size()),0)>=0,"SHA finish");
  std::ostringstream out;out<<std::hex<<std::setfill('0');for(auto b:result)out<<std::setw(2)<<unsigned(b);return out.str();
 }
 ~SHA(){if(hash)BCryptDestroyHash(hash);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);}
};
inline std::string sha256(const Bytes& data){SHA h;if(!data.empty())h.update(data.data(),data.size());return h.finish();}
inline std::string file_sha256(const fs::path& path) {
 std::ifstream in(path,std::ios::binary);need(in.good(),"Cannot open output for hash");SHA h;std::array<char,65536> data{};
 while(in){in.read(data.data(),data.size());if(in.gcount())h.update(data.data(),std::size_t(in.gcount()));}
 need(in.eof(),"Cannot read complete output for hash");return h.finish();
}
struct Record {std::uint32_t ordinal;std::int32_t x,y;std::uint8_t label;std::uint32_t magnitude_bits,theta_bits;};
struct Pool {
 std::uint32_t id=0,object=0,image=0;std::int32_t angle=0;
 std::uint32_t scale_bits=0,level=0,width=0,height=0,budget=0;
 Bytes mask;std::vector<Record> candidates;
};
inline void u32(Bytes& out,std::uint32_t n){for(int i=0;i<4;++i)out.push_back(static_cast<unsigned char>(n>>(8*i)));}
inline void u64(Bytes& out,std::uint64_t n){for(int i=0;i<8;++i)out.push_back(static_cast<unsigned char>(n>>(8*i)));}
inline std::uint64_t payload_size(const Pool& p) {
 need(p.width>0 && p.height>0 && std::uint64_t(p.width)*p.height==p.mask.size(),"Complete mask shape required");
 need(p.level<2 && p.budget==(p.level==0?32u:16u),"Frozen layer/budget required");
 need(p.candidates.size()<=2097152,"Candidate pool cap exceeded");
 return 64ULL+p.mask.size()+21ULL*p.candidates.size();
}
inline Bytes encode_candidates(const Pool& p) {
 Bytes out;out.reserve(21*p.candidates.size());std::tuple<std::int32_t,std::int32_t> previous{};bool first=true;
 for(std::size_t i=0;i<p.candidates.size();++i) {
  const auto& c=p.candidates[i];float magnitude=0;std::memcpy(&magnitude,&c.magnitude_bits,4);
  const auto position=std::make_tuple(c.y,c.x);
  need(c.ordinal==i && (first || previous<position),"Dense unique row-major pool required");
  need(c.x>=0 && c.y>=0 && std::uint32_t(c.x)<p.width && std::uint32_t(c.y)<p.height,"Pool coordinate outside canvas");
  need(c.label<8 && std::isfinite(magnitude),"Invalid candidate label/magnitude");
  first=false;previous=position;
  u32(out,c.ordinal);u32(out,std::uint32_t(c.x));u32(out,std::uint32_t(c.y));out.push_back(c.label);u32(out,c.magnitude_bits);u32(out,c.theta_bits);
 }
 return out;
}
inline Bytes encode(const Pool& p) {
 const auto size=payload_size(p);const auto candidates=encode_candidates(p);Bytes out;out.reserve(std::size_t(size));
 const char magic[]="RGBPOOL1";out.insert(out.end(),magic,magic+8);
 u32(out,p.id);u32(out,p.object);u32(out,p.image);u32(out,std::uint32_t(p.angle));u32(out,p.scale_bits);
 u32(out,p.level);u32(out,p.width);u32(out,p.height);u32(out,p.budget);u32(out,std::uint32_t(p.candidates.size()));
 u64(out,p.mask.size());u64(out,candidates.size());need(out.size()==64,"Pack header width differs");
 out.insert(out.end(),p.mask.begin(),p.mask.end());out.insert(out.end(),candidates.begin(),candidates.end());return out;
}
inline Bytes gzip(const Bytes& data,std::uint64_t maximum_allocation=67108864ULL) {
 need(data.size()<=std::numeric_limits<uInt>::max(),"Gzip input too large");z_stream z{};
 need(deflateInit2(&z,6,Z_DEFLATED,31,8,Z_DEFAULT_STRATEGY)==Z_OK,"Gzip initialize");
 try {
  const auto bound=deflateBound(&z,uLong(data.size()));
  need(maximum_allocation>0 && bound<=std::numeric_limits<uInt>::max(),"Gzip output allocation limit");
  // Allocate at most the remaining ceiling even when zlib's worst-case bound
  // is larger. A compressible member that fits exactly remains valid.
  Bytes out(std::size_t(std::min<std::uint64_t>(bound,maximum_allocation)));
  z.next_in=const_cast<Bytef*>(data.data());z.avail_in=uInt(data.size());z.next_out=out.data();z.avail_out=uInt(out.size());
  need(deflate(&z,Z_FINISH)==Z_STREAM_END && z.avail_in==0,"Compressed member exceeds allocation/output ceiling");out.resize(z.total_out);
  need(deflateEnd(&z)==Z_OK,"Gzip finalize");return out;
 } catch(...) {deflateEnd(&z);throw;}
}
struct Limits {
 std::uint64_t shard_bytes=67108864ULL,physical_bytes=4294967296ULL,logical_bytes=34359738368ULL,candidates=2097152ULL;
};
class Output {
 fs::path directory;Limits limits;std::uint64_t physical_bytes=0,logical_bytes=0;
 fs::path target(const std::string& name) const {
  const fs::path relative(name);need(!relative.empty() && !relative.has_root_path(),"Relative output path required");
  for(const auto& part:relative)need(part!=".." && part!=".","Output path traversal");
  const auto full=directory/relative;
  for(auto p=full;p!=directory;p=p.parent_path())need(!fs::is_symlink(p),"Output symlink forbidden");
  return full;
 }
 public:
 Output(fs::path path,Limits cap=Limits{}):directory(std::move(path)),limits(cap) {
  need(!fs::exists(directory),"Fresh numeric-output directory required");fs::create_directories(directory);
 }
 const fs::path& root()const{return directory;}
 const Limits& cap()const{return limits;}
 std::uint64_t physical()const{return physical_bytes;}
 std::uint64_t logical()const{return logical_bytes;}
 std::uint64_t remaining_physical()const{return limits.physical_bytes-physical_bytes;}
 void preflight_logical(std::uint64_t bytes)const{need(bytes<=limits.logical_bytes && logical_bytes<=limits.logical_bytes-bytes,"Logical payload limit exceeded");}
 void consume_logical(std::uint64_t bytes){preflight_logical(bytes);logical_bytes+=bytes;}
 void append(const std::string& name,const void* data,std::size_t bytes) {
  need(bytes<=limits.physical_bytes && physical_bytes<=limits.physical_bytes-bytes,"Physical output limit exceeded");
  const auto path=target(name);fs::create_directories(path.parent_path());
  // Reserve before opening. On I/O failure the failed run retains its files and reservation.
  physical_bytes+=bytes;std::ofstream out(path,std::ios::binary|std::ios::app);need(out.good(),"Output open failed");
  out.write(static_cast<const char*>(data),std::streamsize(bytes));out.close();need(!out.fail(),"Output write/close failed");
 }
 // Text is its own uncompressed payload. Encoded binary callers reserve their
 // original uncompressed payload with consume_logical before appending bytes.
 void append(const std::string& name,const std::string& data){consume_logical(data.size());append(name,data.data(),data.size());}
 void write(const std::string& name,const std::string& data){need(!fs::exists(target(name)),"Output overwrite forbidden");append(name,data);}
};
struct Member {
 std::uint32_t shard=0;std::uint64_t offset=0,compressed_bytes=0,logical_bytes=0;
 std::string candidate_sha256,mask_sha256,payload_sha256,compressed_sha256;
};
class Writer {
 Output& output;std::uint32_t shard=0,next_pool=0;std::uint64_t shard_bytes=0,shard_logical=0;
 std::vector<std::uint32_t> pool_ids;bool closed=false;
 std::string name()const{std::ostringstream s;s<<"pools_"<<std::setfill('0')<<std::setw(6)<<shard<<".bin.gz";return s.str();}
 void close_shard() {
  if(pool_ids.empty())return;
  std::ostringstream s;s<<"{\"shard\":"<<shard<<",\"path\":\""<<name()<<"\",\"compressed_bytes\":"<<shard_bytes<<",\"logical_bytes\":"<<shard_logical<<",\"sha256\":\""<<file_sha256(output.root()/name())<<"\",\"pool_ids\":[";
  for(std::size_t i=0;i<pool_ids.size();++i){if(i)s<<',';s<<pool_ids[i];}s<<"]}\n";output.append("shards.jsonl",s.str());
  ++shard;shard_bytes=0;shard_logical=0;pool_ids.clear();
 }
 public:
 explicit Writer(Output& out):output(out){}
 Member append(const Pool& p) {
  need(!closed && p.id==next_pool,"Pool sequence/closed writer differs");need(p.candidates.size()<=output.cap().candidates,"Candidate cap exceeded");
  const auto logical=payload_size(p);output.preflight_logical(logical);
  const auto raw=encode(p);const auto compressed=gzip(raw,std::min(output.cap().shard_bytes,output.remaining_physical()));need(compressed.size()<=output.cap().shard_bytes,"Single pool exceeds compressed shard limit");
  if(shard_bytes>output.cap().shard_bytes-compressed.size())close_shard();
  Member m;m.shard=shard;m.offset=shard_bytes;m.compressed_bytes=compressed.size();m.logical_bytes=raw.size();
  const auto candidates=encode_candidates(p);m.candidate_sha256=sha256(candidates);m.mask_sha256=sha256(p.mask);m.payload_sha256=sha256(raw);m.compressed_sha256=sha256(compressed);
  output.consume_logical(logical);output.append(name(),compressed.data(),compressed.size());shard_bytes+=compressed.size();shard_logical+=logical;pool_ids.push_back(p.id);++next_pool;
  std::ostringstream s;s<<"{\"pool_id\":"<<p.id<<",\"object_id\":"<<p.object<<",\"image_id\":"<<p.image<<",\"angle_degrees\":"<<p.angle<<",\"scale_float32_bits\":"<<p.scale_bits<<",\"level\":"<<p.level<<",\"width\":"<<p.width<<",\"height\":"<<p.height<<",\"K\":"<<p.budget<<",\"N\":"<<p.candidates.size()<<",\"shard\":"<<m.shard<<",\"offset\":"<<m.offset<<",\"compressed_bytes\":"<<m.compressed_bytes<<",\"logical_bytes\":"<<m.logical_bytes<<",\"mask_sha256\":\""<<m.mask_sha256<<"\",\"candidate_sha256\":\""<<m.candidate_sha256<<"\",\"payload_sha256\":\""<<m.payload_sha256<<"\",\"compressed_sha256\":\""<<m.compressed_sha256<<"\"}\n";
  output.append("pools.jsonl",s.str());return m;
 }
 void close(){need(!closed,"Writer already closed");close_shard();closed=true;}
};
}} // namespace rgb_stratified::packing
#endif

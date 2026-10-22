#include "numeric_pack.hpp"
#include <iostream>
#include <stdexcept>
#include <filesystem>
using namespace rgb_stratified::packing;
static void check(bool value, const char* message) { if(!value) throw std::runtime_error(message); }
template<class F> static void rejects(F f) { bool failed=false; try { f(); } catch(const std::exception&) {failed=true;} check(failed,"expected resource/format rejection"); }
int main(int argc,char** argv) {
 try {
  check(argc==2,"output argument required"); const std::filesystem::path root=argv[1];
  check(!std::filesystem::exists(root),"output must be new"); std::filesystem::create_directories(root);
  check(sha256(std::vector<unsigned char>{'a','b','c'})=="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad","SHA256 literal");
  Pool p; p.id=0; p.object=1; p.image=7; p.angle=30; p.scale_bits=0x3f800000; p.level=0; p.width=7; p.height=5; p.budget=32;
  p.mask.assign(35,0); p.mask[17]=7;
  p.candidates={Record{0,2,2,3,0x44c80000,0x7fc00001}};
  auto raw=encode(p); check(raw.size()==120,"64-byte header and complete payload");
  check(raw[0]=='R' && raw[7]=='1' && raw[8]==0 && raw[12]==1 && raw[16]==7 && raw[20]==30,"header literal offsets");
  check(raw[32]==7 && raw[36]==5 && raw[40]==32 && raw[44]==1 && raw[48]==35 && raw[56]==21,"header sizes");
  check(raw[81]==7 && raw[99]==0 && raw[103]==2 && raw[107]==2 && raw[111]==3 && raw[116]==1 && raw[119]==0x7f,"mask and canonical 21-byte candidate");
  const auto member=gzip(raw); check(member.size()>18 && member[0]==31 && member[1]==139,"standard gzip member");
  rejects([&]{gzip(raw,16);});
  Limits l; l.shard_bytes=member.size(); l.physical_bytes=100000; l.logical_bytes=100000;
  Output output(root/"ok",l); Writer writer(output);
  const auto a=writer.append(p); p.id=1; const auto b=writer.append(p); writer.close();
  check(a.shard==0 && b.shard==1 && a.offset==0 && b.offset==0,"rotate only at pool boundaries");
  check(output.physical()>=2*member.size() && output.logical()>=240,"logical pool accounting");
  check(output.logical()>240,"logical accounting must include JSONL evidence");
  check(std::filesystem::file_size(root/"ok"/"pools_000000.bin.gz")==member.size(),"full compressed member persisted");
  Output insufficient(root/"small",Limits{member.size()-1,100000,100000,2097152}); Writer too_big(insufficient);
  rejects([&]{p.id=0;too_big.append(p);}); check(insufficient.physical()==0,"oversized member cannot be partially appended");
  Output logical(root/"logical",Limits{100000,100000,119,2097152}); Writer logical_writer(logical);
  rejects([&]{logical_writer.append(p);}); check(logical.physical()==0,"logical limit checked before output");
  Output physical(root/"physical",Limits{100000,3,100000,2097152});
  rejects([&]{physical.append("partial.txt","1234");}); check(!std::filesystem::exists(root/"physical"/"partial.txt"),"physical preflight before create");
  physical.append("partial.txt","12"); rejects([&]{physical.append("partial.txt","34");});
  check(std::filesystem::file_size(root/"physical"/"partial.txt")==2,"prior partial evidence preserved");
  rejects([&]{physical.append("../escape.txt","1");});
  Pool invalid=p; invalid.mask.pop_back(); rejects([&]{encode(invalid);});
  invalid=p; invalid.candidates[0].ordinal=1; rejects([&]{encode(invalid);});
  invalid=p; invalid.candidates[0].x=7; rejects([&]{encode(invalid);});
  invalid=p; invalid.candidates[0].magnitude_bits=0x7f800000; rejects([&]{encode(invalid);});
  std::cout<<"PASS packing: canonical payload, gzip boundaries, SHA256, hard byte limits, partial preservation and malformed input\n";
  return 0;
 } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}

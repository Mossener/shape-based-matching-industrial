// Prepared before the encoder; not compiled/run. No OpenCV or Matcher include.
#include "../output_binary.hpp"
#include <algorithm>
#include <iostream>
#include <stdexcept>

void require(bool value,const char* message) {
    if(!value)throw std::runtime_error(message);
}
int main() {
    try {
        const postprocess_api::Records values={{-1,2,-3,0x80000000U,std::string("A\0B",3)}};
        const auto encoded=postprocess_api::encodeOutput(0x0102030405060708ULL,values);
        const std::vector<unsigned char> expected={
            'H','M','O','U','T','0','0','1', 8,7,6,5,4,3,2,1, 1,0,0,0,0,0,0,0,
            255,255,255,255, 2,0,0,0, 253,255,255,255, 0,0,0,128,
            3,0,0,0,0,0,0,0, 'A',0,'B'};
        require(encoded==expected,"Literal little-endian fields/zero bits/NUL class differ");
        const auto empty=postprocess_api::encodeOutput(0,{});
        const std::vector<unsigned char> expected_empty={
            'H','M','O','U','T','0','0','1', 0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0};
        require(empty==expected_empty,"Empty output archive differs");
        auto changed=values;
        changed.push_back(values.front());
        const auto duplicates=postprocess_api::encodeOutput(7,changed);
        require(duplicates.size()==78 && duplicates[16]==2,"Duplicate multiplicity was lost");
        changed[1].score_bits=0;
        require(postprocess_api::encodeOutput(7,changed)!=duplicates,"Signed-zero score bits were lost");
        std::swap(changed[0],changed[1]);
        require(postprocess_api::encodeOutput(7,changed)!=postprocess_api::encodeOutput(
                    7,postprocess_api::Records{{-1,2,-3,0x80000000U,std::string("A\0B",3)},
                                              {-1,2,-3,0,std::string("A\0B",3)}}),
                "Output order was lost");
        require(postprocess_api::encodeOutput(8,values)!=postprocess_api::encodeOutput(7,values),
                "Call identity was lost");
        std::cout<<"PASS output_binary literal contract; matcher_calls=0 image_decodes=0\n";
        return 0;
    } catch(const std::exception& error) {
        std::cerr<<"FAIL output_binary literal contract: "<<error.what()<<'\n';
        return 1;
    }
}

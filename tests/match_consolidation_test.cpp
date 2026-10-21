#include "line2Dup.h"
#include "line2Dup_matches.hpp"
#include <algorithm>
#include <iostream>
#include <random>
#include <stdexcept>
#include <tuple>

namespace {
using Match=line2Dup::Match;
using Key=std::tuple<float,int,std::string,int,int>;
std::vector<Key> keys(const std::vector<Match>& values) {
    std::vector<Key> result;
    for(const auto& m:values) result.emplace_back(m.similarity,m.template_id,m.class_id,m.y,m.x);
    return result;
}
void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
}
int main() {
    try {
        // Different positions at the same score/template separate duplicates
        // in the old sort's equivalence class. Cross-template duplicates must
        // choose the lowest ID regardless of parallel merge order.
        const std::vector<Match> input={
            {20,10,90,"A",9},{30,10,90,"A",2},{20,10,90,"A",3},
            {20,10,90,"A",9},{20,10,90,"A",3},{20,10,90,"B",0},
            {20,10,89,"A",0},{10,20,90,"A",2},{5,10,90,"A",2},
            {30,10,90,"A",7},{4,4,100,"A",8}
        };
        const std::vector<Key> expected={
            {100,8,"A",4,4},{90,0,"B",10,20},{90,2,"A",10,5},
            {90,2,"A",10,30},{90,2,"A",20,10},{90,3,"A",10,20},
            {89,0,"A",10,20}
        };
        std::mt19937 rng(4347);
        for(int i=0;i<300;++i) {
            auto values=input;std::shuffle(values.begin(),values.end(),rng);
            line2Dup::detail::consolidateMatches(values);
            require(keys(values)==expected,"duplicate membership, lowest template ID or deterministic order changed");
            line2Dup::detail::consolidateMatches(values);
            require(keys(values)==expected,"consolidation is not idempotent");
        }
        std::vector<Match> empty;line2Dup::detail::consolidateMatches(empty);
        require(empty.empty(),"empty matches gained an entry");
        std::vector<Match> singleton={{1,2,75,"LED",4}};
        line2Dup::detail::consolidateMatches(singleton);
        require(keys(singleton)==std::vector<Key>{{75,4,"LED",2,1}},"singleton match changed");
        const float next=std::nextafter(75.f,100.f);
        std::vector<Match> scores={{1,2,75,"LED",2},{1,2,next,"LED",8}};
        line2Dup::detail::consolidateMatches(scores);
        require(scores.size()==2&&scores[0].similarity==next&&scores[1].similarity==75,
                "nearby unequal scores were merged or rounded");
        std::cout<<"PASS match consolidation: 300 shuffled orders, lowest ID, class/score separation, stable order and idempotence\n";
        return 0;
    }catch(const std::exception& e){std::cerr<<"FAIL match consolidation: "<<e.what()<<'\n';return 1;}
}

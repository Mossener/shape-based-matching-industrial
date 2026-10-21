#include "eval_metrics.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>

using namespace public_eval;
static void require(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(message);
}
static Detection detection(double x, double y, double w, double h, float score, int id) {
    Detection d; d.box={x,y,w,h}; d.score=score; d.template_id=id;
    d.match_x=int(x); d.match_y=int(y); return d;
}
int main() {
    try {
        // Break caught: forgetting template crop origin or input padding.
        const auto box=boxAtMatch(200,100,64,{4,6,16,18},10,20);
        require(box.x==130 && box.y==22 && box.w==16 && box.h==18,"bbox origin/padding contract");
        // Break caught: inclusive-pixel '+1' area or failure on empty rectangles.
        require(std::abs(iou({0,0,10,10},{5,0,10,10})-1.0/3.0)<1e-12,"IoU must use continuous xywh geometry");
        require(iou({0,0,0,10},{0,0,10,10})==0,"empty box IoU");
        auto first=detection(0,0,10,10,90,2), duplicate=detection(0,0,10,10,80,1);
        auto second=detection(20,0,10,10,70,0);
        // Break caught: unstable ties or suppressing a different instance.
        auto tie=detection(0,0,10,10,90,1);
        auto kept=nms({first,second,tie,duplicate},0.3);
        require(kept.size()==2 && kept[0].template_id==1 && kept[1].template_id==0,"NMS order and per-instance preservation");
        auto boundary=nms({first,detection(5,0,10,10,80,3)},1.0/3.0);
        require(boundary.size()==2,"NMS suppresses only IoU strictly greater than its limit");
        std::vector<GroundTruth> gt={{0,{0,0,10,10},1.0},{1,{20,0,10,10},1.0}};
        // Break caught: allowing two detections to match the same object.
        auto all=evaluate({duplicate,second,first},gt,0.5,false,0.5);
        require(all.tp==2 && all.fp==1 && all.fn==0 && all.gt==2 && all.ignored==0,"one-to-one allGT counts");
        require(all.labels.size()==3 && all.labels[0]=="TP" && all.labels[1]=="FP" && all.labels[2]=="TP","score-sorted greedy labels");
        // Break caught: a low-visibility box swallowing unlimited duplicate FP.
        std::vector<GroundTruth> low={{0,{0,0,10,10},0.2}};
        auto ignored=evaluate({duplicate,first},low,0.5,true,0.5);
        require(ignored.tp==0 && ignored.fp==1 && ignored.fn==0 && ignored.gt==0 && ignored.ignored==1,"one detection per ignored GT");
        // Break caught: matching ignore before an overlapping eligible target.
        std::vector<GroundTruth> overlap={{0,{0,0,10,10},0.2},{1,{0,0,10,10},0.9}};
        auto eligible=evaluate({first},overlap,0.5,true,0.5);
        require(eligible.tp==1 && eligible.fn==0 && eligible.ignored==0,"eligible target takes priority over ignore");
        auto negative=evaluate({first},{},0.5,false,0.5);
        require(negative.fp==1 && negative.tp==0 && negative.fn==0,"negative images count detections as FP");
        // Break caught: candidate equality ignoring template identity or score.
        require(equalCandidates({first,second},{second,first}),"candidate multiset order independence");
        auto changed=first; changed.template_id=99;
        require(!equalCandidates({first},{changed}),"candidate equality must include template ID");
        changed=first; changed.score=std::nextafter(first.score,100.f);
        require(!equalCandidates({first},{changed}),"candidate equality must include exact score");
        require(!equalCandidates({first,first},{first}),"candidate equality must include multiplicity");
        auto otherClass=first;first.class_id="tless_object_1";otherClass.class_id="tless_object_2";
        require(nms({first,otherClass},0.3).size()==2,"different classes must survive overlapping NMS");
        require(!equalCandidates({first},{otherClass}),"candidate equality must include class identity");
        auto wrong=evaluate({otherClass},{{0,{0,0,10,10},1.0,"tless_object_1"}},0.5,false,0.5);
        require(wrong.tp==0 && wrong.fp==1 && wrong.fn==1,"wrong class cannot consume GT");
        auto right=evaluate({first},{{0,{5,0,10,10},1.0,"tless_object_1"}},0.3,false,0.5);
        require(right.tp==1 && std::abs(right.matched_iou_sum-1.0/3.0)<1e-12,"TP IoU must retain actual overlap");
        std::cout << "PASS bbox/IoU/NMS/one-to-one/ignore/negative/equality/class/TP-IoU literal cases\n";
        return 0;
    } catch(const std::exception& e) { std::cerr << "FAIL " << e.what() << '\n'; return 1; }
}

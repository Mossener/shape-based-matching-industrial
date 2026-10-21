#ifndef PUBLIC_EVALUATION_METRICS_HPP
#define PUBLIC_EVALUATION_METRICS_HPP
#include <algorithm>
#include <cmath>
#include <string>
#include <vector>
namespace public_eval {
struct Box { double x=0,y=0,w=0,h=0; };
struct Detection { Box box; float score=0; int template_id=-1,match_x=0,match_y=0; std::string class_id; };
struct GroundTruth { int id=-1; Box box; double visibility=0; std::string class_id; };
struct Counts {
    int tp=0,fp=0,fn=0,gt=0,ignored=0;
    double matched_iou_sum=0;
    std::vector<std::string> labels;
    std::vector<int> gt_ids;
};
inline Box boxAtMatch(int x,int y,int padding,Box silhouette,int tl_x,int tl_y) {
    return {x-padding+silhouette.x-tl_x,y-padding+silhouette.y-tl_y,silhouette.w,silhouette.h};
}
inline double iou(Box a,Box b) {
    if(a.w<=0 || a.h<=0 || b.w<=0 || b.h<=0) return 0;
    const double w=std::max(0.0,std::min(a.x+a.w,b.x+b.w)-std::max(a.x,b.x));
    const double h=std::max(0.0,std::min(a.y+a.h,b.y+b.h)-std::max(a.y,b.y));
    const double intersection=w*h, total=a.w*a.h+b.w*b.h-intersection;
    return total>0 ? intersection/total : 0;
}
inline bool canonicalLess(const Detection& a,const Detection& b) {
    if(a.score!=b.score) return a.score>b.score;
    if(a.class_id!=b.class_id) return a.class_id<b.class_id;
    if(a.template_id!=b.template_id) return a.template_id<b.template_id;
    if(a.match_y!=b.match_y) return a.match_y<b.match_y;
    if(a.match_x!=b.match_x) return a.match_x<b.match_x;
    if(a.box.y!=b.box.y) return a.box.y<b.box.y;
    if(a.box.x!=b.box.x) return a.box.x<b.box.x;
    if(a.box.w!=b.box.w) return a.box.w<b.box.w;
    return a.box.h<b.box.h;
}
inline std::vector<Detection> nms(std::vector<Detection> input,double limit) {
    std::sort(input.begin(),input.end(),canonicalLess);
    std::vector<Detection> kept;
    for(const auto& item:input) {
        bool suppressed=false;
        for(const auto& previous:kept)
            if((item.class_id.empty() || previous.class_id.empty() || item.class_id==previous.class_id) &&
               iou(item.box,previous.box)>limit) { suppressed=true; break; }
        if(!suppressed) kept.push_back(item);
    }
    return kept;
}
inline Counts evaluate(std::vector<Detection> detections,const std::vector<GroundTruth>& gt,
                       double overlap,bool eligible_only,double minimum_visibility) {
    std::sort(detections.begin(),detections.end(),canonicalLess);
    Counts result; result.labels.assign(detections.size(),"FP"); result.gt_ids.assign(detections.size(),-1);
    std::vector<bool> used(gt.size(),false);
    for(const auto& item:gt) if(!eligible_only || item.visibility>=minimum_visibility) ++result.gt;
    // Every eligible target is considered before any low-visibility ignore.
    for(size_t p=0;p<detections.size();++p) {
        int best=-1; double best_iou=-1;
        for(size_t g=0;g<gt.size();++g) {
            if(used[g] || (eligible_only && gt[g].visibility<minimum_visibility) ||
               (!detections[p].class_id.empty() && !gt[g].class_id.empty() && detections[p].class_id!=gt[g].class_id)) continue;
            const double value=iou(detections[p].box,gt[g].box);
            if(value>=overlap && (value>best_iou || (value==best_iou && (best<0 || gt[g].id<gt[best].id)))) {
                best=int(g);best_iou=value;
            }
        }
        if(best>=0) { used[best]=true;result.labels[p]="TP";result.gt_ids[p]=gt[best].id;++result.tp;result.matched_iou_sum+=best_iou; }
    }
    if(eligible_only) for(size_t p=0;p<detections.size();++p) {
        if(result.labels[p]!="FP") continue;
        int best=-1;double best_iou=-1;
        for(size_t g=0;g<gt.size();++g) {
            if(used[g] || gt[g].visibility>=minimum_visibility ||
               (!detections[p].class_id.empty() && !gt[g].class_id.empty() && detections[p].class_id!=gt[g].class_id)) continue;
            const double value=iou(detections[p].box,gt[g].box);
            if(value>=overlap && (value>best_iou || (value==best_iou && (best<0 || gt[g].id<gt[best].id)))) {
                best=int(g);best_iou=value;
            }
        }
        // Each ignore instance consumes at most one remaining detection.
        if(best>=0) { used[best]=true;result.labels[p]="IGNORE";result.gt_ids[p]=gt[best].id;++result.ignored; }
    }
    result.fp=int(detections.size())-result.tp-result.ignored;
    result.fn=result.gt-result.tp;
    return result;
}
inline bool equalCandidates(std::vector<Detection> a,std::vector<Detection> b) {
    if(a.size()!=b.size()) return false;
    std::sort(a.begin(),a.end(),canonicalLess);std::sort(b.begin(),b.end(),canonicalLess);
    for(size_t i=0;i<a.size();++i) if(a[i].score!=b[i].score || a[i].class_id!=b[i].class_id || a[i].template_id!=b[i].template_id ||
        a[i].match_x!=b[i].match_x || a[i].match_y!=b[i].match_y ||
        a[i].box.x!=b[i].box.x || a[i].box.y!=b[i].box.y || a[i].box.w!=b[i].box.w || a[i].box.h!=b[i].box.h) return false;
    return true;
}
}
#endif

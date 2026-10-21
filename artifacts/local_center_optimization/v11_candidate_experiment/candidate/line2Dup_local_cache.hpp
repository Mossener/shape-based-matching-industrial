#ifndef LINE2DUP_LOCAL_CACHE_HPP
#define LINE2DUP_LOCAL_CACHE_HPP
#include "line2Dup_search.hpp"
#include <array>

namespace line2Dup {
namespace detail {
// Worker-owned, template/level-scoped copies of complete local winners.
// Capacity bounds saved work only; callers still compute every lookup miss.
class LocalCenterCache {
public:
    void reset() { count_=0; }
    bool find(int cell_x,int cell_y,LocalMaximum& result) const {
        for(unsigned i=0;i<count_;++i) {
            const auto& entry=entries_[i];
            if(entry.x==cell_x && entry.y==cell_y) {
                result=entry.value;return true;
            }
        }
        return false;
    }
    // Called after a miss in this scope. Full storage never replaces an old
    // key and never prevents the caller's complete fallback calculation.
    void insert(int cell_x,int cell_y,const LocalMaximum& result) {
        if(count_<entries_.size())entries_[count_++]={cell_x,cell_y,result};
    }
private:
    struct Entry {int x,y;LocalMaximum value;};
    std::array<Entry,16> entries_;
    unsigned count_=0;
};
}
}
#endif

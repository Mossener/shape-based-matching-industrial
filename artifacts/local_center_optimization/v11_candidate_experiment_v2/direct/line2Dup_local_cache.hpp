#ifndef LINE2DUP_LOCAL_CACHE_HPP
#define LINE2DUP_LOCAL_CACHE_HPP
#include "line2Dup_search.hpp"
#include <array>
#include <climits>
#include <cstdint>
#include <limits>

namespace line2Dup {
namespace detail {
// Worker-owned, template/level-scoped copies of complete local winners.
// A colliding key is always a miss; callers compute it before replacement.
class LocalCenterCache {
public:
    void reset() { for(auto& entry:entries_)entry.valid=false; }
    bool find(int cell_x,int cell_y,LocalMaximum& result) const {
        const auto& entry=entries_[slot(cell_x,cell_y)];
        if(!entry.valid || entry.x!=cell_x || entry.y!=cell_y)return false;
        result=entry.value;return true;
    }
    void insert(int cell_x,int cell_y,const LocalMaximum& result) {
        auto& entry=entries_[slot(cell_x,cell_y)];
        entry.x=cell_x;entry.y=cell_y;entry.value=result;entry.valid=true;
    }
private:
    static_assert(CHAR_BIT==8,"Eight-bit bytes required");
    static_assert(sizeof(int)==4 && sizeof(unsigned int)==4 && sizeof(std::uint32_t)==4,
                  "Fixed unsigned32 hash requires32-bit int/unsigned int/uint32_t");
    static_assert(std::numeric_limits<std::uint32_t>::digits==32 &&
                  std::numeric_limits<unsigned int>::digits==32,"Unsigned32 arithmetic required");
    static unsigned slot(int cell_x,int cell_y) {
        const std::uint32_t ux=static_cast<std::uint32_t>(cell_x);
        const std::uint32_t uy=static_cast<std::uint32_t>(cell_y);
        std::uint32_t h=ux+0x9e3779b9U;
        h^=uy+0x9e3779b9U+(h<<6)+(h>>2);
        h^=h>>16;h*=0x85ebca6bU;
        h^=h>>13;h*=0xc2b2ae35U;
        h^=h>>16;return h&15U;
    }
    struct Entry {int x=0,y=0;LocalMaximum value;bool valid=false;};
    std::array<Entry,16> entries_;
};
}
}
#endif

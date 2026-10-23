#ifndef ORDERED_CONTOUR_NATIVE_CANDIDATE_COMPILED_SCENE_V2_HPP
#define ORDERED_CONTOUR_NATIVE_CANDIDATE_COMPILED_SCENE_V2_HPP

// RED-only factory/score stubs. Coordinator must retain actual assertion RED
// before replacing these stubs. Frozen v1 headers remain unchanged.
#include "native_candidate_compatibility.hpp"

#include <memory>

namespace ordered_contour_native::candidate_v2 {

using Coordinate = candidate::Coordinate;
using Point = candidate::Point;
using Padding = candidate::Padding;
using CandidateScore = candidate::CandidateScore;

struct SceneIndexWork {
    Id index_builds = 0;
    Id membership_rows_indexed = 0;
    Id members_indexed = 0;
    Id chains_indexed = 0;
};

namespace detail {
struct SceneStorage {
    candidate::SceneEvidence scene;
    std::map<Id, std::size_t> membership_index_by_pixel;
    std::map<Id, std::size_t> chain_index_by_id;
    SceneIndexWork work;
};
} // namespace detail

class CompiledScene {
public:
    CompiledScene(const CompiledScene&) = default;
    CompiledScene(CompiledScene&&) noexcept = default;
    CompiledScene& operator=(const CompiledScene&) = default;
    CompiledScene& operator=(CompiledScene&&) noexcept = default;

    bool valid() const noexcept { return static_cast<bool>(storage_); }
    bool shares_storage_with(const CompiledScene& other) const noexcept {
        return storage_ && storage_ == other.storage_;
    }
    const candidate::SceneEvidence& evidence() const {
        require_storage();
        return storage_->scene;
    }
    const SceneIndexWork& index_work() const {
        require_storage();
        return storage_->work;
    }

private:
    explicit CompiledScene(std::shared_ptr<const detail::SceneStorage> storage)
        : storage_(std::move(storage)) {}
    void require_storage() const {
        if (!storage_) throw std::invalid_argument("moved-from compiled scene");
    }
    std::shared_ptr<const detail::SceneStorage> storage_;

    friend CompiledScene prepare_scene(const edge::LabelGrid&);
    friend CandidateScore score_candidate(const edge::TemplateEvidence&, const CompiledScene&,
                                         const Point&, const Point&, const Padding&);
};

// Own an immutable scene snapshot and both complete scene lookup indexes once.
// Copy/move preserve shared storage; accessing a moved-from handle is invalid.
inline CompiledScene prepare_scene(const edge::LabelGrid&) {
    return CompiledScene(std::make_shared<const detail::SceneStorage>());
}

// Full frozen v1 CandidateScore observables, including every solver work field.
// Per-score candidate-local maps are allowed; no scene-wide scan/map build.
inline CandidateScore score_candidate(const edge::TemplateEvidence&, const CompiledScene&,
                                      const Point&, const Point&,
                                      const Padding& = {0, 0, 0, 0}) {
    return {};
}

} // namespace ordered_contour_native::candidate_v2

#endif // ORDERED_CONTOUR_NATIVE_CANDIDATE_COMPILED_SCENE_V2_HPP

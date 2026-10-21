"""Generate a namespaced diagnostic snapshot; never edits production sources."""
from pathlib import Path
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SOURCES = ('line2Dup.cpp', 'line2Dup.h', 'line2Dup_spread.hpp',
           'line2Dup_response.hpp', 'line2Dup_search.hpp')

def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f'Expected one occurrence, got {text.count(old)}: {old[:90]!r}')
    return text.replace(old, new, 1)

def generate():
    target = HERE / 'source'
    target.mkdir(exist_ok=True)
    manifest = {'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'source_sha256': {}, 'generated_sha256': {}}
    for name in SOURCES:
        raw = (ROOT/name).read_bytes()
        manifest['source_sha256'][name] = hashlib.sha256(raw).hexdigest()
        text = raw.decode('utf-8').replace('\r\n', '\n')
        text = text.replace('namespace line2Dup', 'namespace profiledLine2Dup')
        text = text.replace('namespace shape_based_matching', 'namespace profiledShapeBasedMatching')
        for guard in ('CXXLINEMOD_H', 'LINE2DUP_SPREAD_HPP', 'LINE2DUP_RESPONSE_HPP', 'LINE2DUP_SEARCH_HPP'):
            text = text.replace(guard, 'SEARCH_PROFILE_' + guard)
        if name == 'line2Dup.h':
            text = replace_once(text, '#include <memory>', '#include <memory>\n#include "../profile.hpp"')
            text = replace_once(text, 'struct MatchTimings\n{', 'struct MatchTimings\n{\n    search_profile::Call profile;')
        if name == 'line2Dup.cpp':
            text = replace_once(text, '    std::vector<SearchScratch> search_workers;',
                                '    std::vector<SearchScratch> search_workers;\n    search_profile::Call *profile = nullptr;')
            text = replace_once(text, '    state.levels.resize(pyramid_levels);',
                                '    state.profile = &measured.profile;\n    state.levels.resize(pyramid_levels);')
            text = replace_once(text,
                '    std::sort(matches.begin(), matches.end());\n    std::vector<Match>::iterator new_end = std::unique(matches.begin(), matches.end());\n    matches.erase(new_end, matches.end());',
                '    measured.profile.matches_before_sort = matches.size();\n'
                '    const auto profile_sort_start = search_profile::Clock::now();\n'
                '    std::sort(matches.begin(), matches.end());\n'
                '    measured.profile.final_sort_ms = search_profile::elapsedMs(profile_sort_start);\n'
                '    const auto profile_unique_start = search_profile::Clock::now();\n'
                '    std::vector<Match>::iterator new_end = std::unique(matches.begin(), matches.end());\n'
                '    matches.erase(new_end, matches.end());\n'
                '    measured.profile.final_unique_ms = search_profile::elapsedMs(profile_unique_start);\n'
                '    measured.profile.matches_after_unique = matches.size();')
            text = replace_once(text,
                '#pragma omp declare reduction \\\n    (omp_insert: std::vector<Match>: omp_out.insert(omp_out.end(), omp_in.begin(), omp_in.end()))',
                '    const size_t profile_base = workspace.profile->templates.size();\n'
                '    workspace.profile->templates.resize(profile_base + template_pyramids.size());\n\n'
                '#pragma omp declare reduction \\\n    (omp_insert: std::vector<Match>: omp_out.insert(omp_out.end(), omp_in.begin(), omp_in.end()))')
            text = replace_once(text,
                '        SearchScratch &scratch = options.reuse_search_buffers ? workspace.search_workers[worker] : transient;',
                '        auto &profile = workspace.profile->templates[profile_base + template_id];\n'
                '        profile.class_id = class_id; profile.template_id = int(template_id); profile.worker = worker;\n'
                '        profile.coarse_level = pyramid_levels - 1; profile.levels.resize(pyramid_levels);\n'
                '        SearchScratch &scratch = options.reuse_search_buffers ? workspace.search_workers[worker] : transient;')
            text = replace_once(text,
                '            {\n                const Template &templ = tp[lowest_start];',
                '            const auto profile_coarse_start = search_profile::Clock::now();\n'
                '            {\n                const Template &templ = tp[lowest_start];')
            text = replace_once(text,
                '            // Find initial matches\n',
                '            profile.coarse_similarity_ms = search_profile::elapsedMs(profile_coarse_start);\n'
                '            const auto profile_collect_start = search_profile::Clock::now();\n'
                '            // Find initial matches\n')
            text = replace_once(text,
                '                                          class_id, int(template_id), candidates);\n        }',
                '                                          class_id, int(template_id), candidates);\n'
                '            profile.coarse_collect_ms = search_profile::elapsedMs(profile_collect_start);\n'
                '            profile.coarse_feature_count = num_features; profile.coarse_candidates = candidates.size();\n'
                '            const int W = similarities.cols, H = similarities.rows;\n'
                '            const int span_x = W - ((tp[lowest_start].width - 1) / lowest_T + 1);\n'
                '            const int span_y = H - ((tp[lowest_start].height - 1) / lowest_T + 1);\n'
                '            CV_Assert(span_x >= 0 && span_y >= 0);\n'
                '            profile.map_positions = std::uint64_t(W) * H;\n'
                '            profile.accumulated_prefix = std::uint64_t(span_y) * W + span_x + 1;\n'
                '            profile.geometrically_valid = std::uint64_t(span_x + 1) * (span_y + 1);\n'
                '            profile.zero_tail_scanned = profile.map_positions - profile.accumulated_prefix;\n'
                '            profile.wrapped_prefix_scanned = profile.accumulated_prefix - profile.geometrically_valid;\n'
                '            const int coarse_offset = lowest_T / 2 + (lowest_T % 2 - 1);\n'
                '            for (const auto &candidate : candidates) {\n'
                '                const int c = (candidate.x - coarse_offset) / lowest_T;\n'
                '                const int r = (candidate.y - coarse_offset) / lowest_T;\n'
                '                const auto index = std::uint64_t(r) * W + c;\n'
                '                profile.zero_tail_candidates += index >= profile.accumulated_prefix;\n'
                '                profile.wrapped_candidates += index < profile.accumulated_prefix && c > span_x;\n'
                '            }\n        }')
            text = replace_once(text,
                '            Mat &similarities2 = scratch.local_similarities;\n            for (int m',
                '            auto &level_profile = profile.levels[l];\n'
                '            level_profile.feature_count = int(tp[start].features.size());\n'
                '            level_profile.candidates_in = candidates.size();\n'
                '            Mat &similarities2 = scratch.local_similarities;\n            for (int m')
            text = replace_once(text,
                '                int y = match2.y * 2 + 1;',
                '                int y = match2.y * 2 + 1;\n'
                '                const int profile_x = x, profile_y = y;')
            text = replace_once(text,
                '                // Compute local similarity maps for each ColorGradient',
                '                level_profile.x_clamped += x != profile_x;\n'
                '                level_profile.y_clamped += y != profile_y;\n'
                '                ++level_profile.local_calls;\n'
                '                const auto profile_local_start = search_profile::Clock::now();\n'
                '                // Compute local similarity maps for each ColorGradient')
            text = replace_once(text,
                '                // Find best local adjustment',
                '                level_profile.similarity_ms += search_profile::elapsedMs(profile_local_start);\n'
                '                const auto profile_argmax_start = search_profile::Clock::now();\n'
                '                // Find best local adjustment')
            text = replace_once(text,
                '                // Update current match',
                '                level_profile.argmax_ms += search_profile::elapsedMs(profile_argmax_start);\n'
                '                // Update current match')
            text = replace_once(text,
                '            // Filter out any matches that drop below the similarity threshold',
                '            const auto profile_filter_start = search_profile::Clock::now();\n'
                '            // Filter out any matches that drop below the similarity threshold')
            text = replace_once(text,
                '            candidates.erase(new_end, candidates.end());\n        }',
                '            candidates.erase(new_end, candidates.end());\n'
                '            level_profile.filter_ms = search_profile::elapsedMs(profile_filter_start);\n'
                '            level_profile.candidates_out = candidates.size();\n        }')
            # The unused protected convenience overload still needs a valid profile sink.
            text = replace_once(text,
                '    workspace.impl_->search_workers.resize(workers);\n    matchClass(',
                '    workspace.impl_->search_workers.resize(workers);\n'
                '    search_profile::Call profile; workspace.impl_->profile = &profile;\n    matchClass(')
        out = target/name
        out.write_text(text, encoding='utf-8', newline='\n')
        manifest['generated_sha256'][str(out.relative_to(HERE)).replace('\\', '/')] = hashlib.sha256(out.read_bytes()).hexdigest()
    (HERE/'source_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')

if __name__ == '__main__':
    generate()

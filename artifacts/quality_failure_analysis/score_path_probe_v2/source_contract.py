"""Exact source transformation and synthetic-tested native receipt gates."""
EXPECTED_PHASE2 = dict(coarse_similarity_calls=430, local_map_calls=7185, local_fused_maximum_calls=7185,
                       coarse_cells=1185080, local_cells=1839360, feature_response_digits=73337912,
                       rgb_positive_controls=215, decoded_operations=213, unique_image_files=175,
                       job_identity_rows=430, unique_job_keys=430, physical_feature_probes=13534,
                       fullclass_nms_frames=426, native_grid_points=751, point_parent_links=12016,
                       full_class_search_replays=0, public_detector_match_calls=0, all_oracles_exact=1,
                       all_occurrence_gates_exact=1, all_fullclass_nms_assignment_exact=1, accuracy_improvement_claim=0)


def need(value, message):
    if not value:
        raise ValueError(message)


def extract(source):
    markers = (b'using Memories = ', b'struct Maps { ', b'static Maps preprocess(', b'// Independent oracle:')
    need(all(source.count(marker) == 1 for marker in markers), 'Source extraction markers must occur exactly once')
    alias_start, maps_start, start, end = (source.index(marker) for marker in markers)
    need(alias_start < maps_start < start < end, 'Source extraction order differs')
    alias = source[alias_start:source.index(b'\n', alias_start)+1]
    maps = source[maps_start:source.index(b'\n', maps_start)+1]
    block = source[start:end]
    need(b'main' not in alias+maps+block and block.rstrip().endswith(b'}'), 'Unexpected extracted source boundary')
    components = [alias, maps, block]
    header = b'#pragma once\nnamespace probe_v2 {\n'+b''.join(components)+b'\n}\n'
    return dict(components=components, header=header)


def equivalent_build_inputs(red, green):
    """Only the separately generated, byte-identical header may change path."""
    normalized = []
    header_digests = []
    for build in (red, green):
        units = build['dependency_units']
        need(len(units) == 1, 'Phase2 must use exactly one translation unit')
        header = units[0]['generated_preprocess_header']
        sources = build['project_sources']
        need(sum(value == header for value in sources) == 1 and
             sum(value['path'] == header['path'] for value in sources) == 1,
             'Generated preprocessing header must occur exactly once in source closure')
        normalized.append([value for value in sources if value['path'] != header['path']])
        header_digests.append((header['bytes'], header['sha256']))
    need(normalized[0] == normalized[1] and header_digests[0] == header_digests[1] and
         red['compiler_tools_and_link_libraries'] == green['compiler_tools_and_link_libraries'],
         'RED/GREEN source/tool/library closures differ')
    return True


def native_gate(mode, fault, exit_code, summary, failure):
    need(mode in ('selftest', 'phase2'), 'Unknown Phase2 receipt mode')
    if fault != 'none':
        need(mode == 'selftest' and fault in ('coarse', 'local', 'winner') and exit_code != 0 and
             summary is None and failure is not None, 'RED is a failed synthetic stage only')
        need(failure.get('reason') == 'Independent '+fault+' oracle mismatch' and
             failure.get('decoded_operations_started') == 0 and failure.get('full_class_search_replays') == 0 and
             failure.get('public_detector_match_calls') == 0, 'RED failed for an unintended reason or opened images')
        return True
    need(exit_code == 0 and failure is None and summary and summary.get('passed') == 1 and
         summary.get('stage') == mode, 'Native stage did not complete')
    if mode == 'selftest':
        expected = dict(coarse_cells=12, local_cells=256, scalar_native_oracles=1, dataset_image_reads=0,
                        full_class_search_replays=0, public_detector_match_calls=0)
    else:
        expected = EXPECTED_PHASE2
        need(0 < summary.get('peak_rss_bytes', -1) <= 1610612736 and
             0 <= summary.get('numeric_output_bytes', -1) <= 1073741824, 'Native Phase2 resource limit differs')
    need(all(summary.get(key) == value for key, value in expected.items()), 'Native exact scope/oracle/control budget differs')
    return True

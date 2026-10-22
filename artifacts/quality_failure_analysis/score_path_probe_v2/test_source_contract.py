"""Exact extraction and native result gates; all fixtures are synthetic bytes."""
import unittest
import source_contract as c


class SourceTests(unittest.TestCase):
    SOURCE = (b'using Memories = native_vectors;\nstruct Maps { Memories memories; };\n'
              b'class Irrelevant {};\nstatic Maps preprocess(const cv::Mat& padded) {\nreturn {};\n}\n'
              b'// Independent oracle: ignored\nint main(){}\n')

    def test_extraction_preserves_exact_preprocessing_bytes_without_any_main(self):
        result = c.extract(self.SOURCE)
        self.assertEqual(result['components'][2], b'static Maps preprocess(const cv::Mat& padded) {\nreturn {};\n}\n')
        self.assertIn(result['components'][2], result['header'])
        self.assertNotIn(b'main', result['header'])
        self.assertNotIn(b'Irrelevant', result['header'])
        self.assertEqual(c.extract(self.SOURCE), result)

    def test_ambiguous_or_missing_markers_fail_closed(self):
        for data in [self.SOURCE.replace(b'// Independent oracle:', b'// lost:'),
                     self.SOURCE+self.SOURCE, self.SOURCE.replace(b'using Memories =', b'using Wrong =')]:
            with self.assertRaises(ValueError):
                c.extract(data)

    def test_only_the_requested_red_fault_is_an_expected_failure(self):
        failure = dict(reason='Independent local oracle mismatch', decoded_operations_started=0,
                       public_detector_match_calls=0, full_class_search_replays=0)
        self.assertTrue(c.native_gate('selftest', 'local', 1, None, failure))
        for mode, fault, exit_code in [('selftest', 'coarse', 1), ('phase2', 'local', 1), ('selftest', 'local', 0)]:
            with self.assertRaises(ValueError):
                c.native_gate(mode, fault, exit_code, None, failure)

    def test_phase2_success_requires_exact_kernel_digit_and_control_budget(self):
        summary = dict(c.EXPECTED_PHASE2, passed=1, stage='phase2', peak_rss_bytes=100000, numeric_output_bytes=4000)
        self.assertTrue(c.native_gate('phase2', 'none', 0, summary, None))
        for field in ['coarse_similarity_calls', 'feature_response_digits', 'rgb_positive_controls', 'all_oracles_exact']:
            with self.assertRaises(ValueError):
                c.native_gate('phase2', 'none', 0, dict(summary, **{field: summary[field]-1}), None)

    def test_red_green_sources_allow_only_the_identical_generated_header_to_move(self):
        def fixture(prefix):
            header = dict(path=prefix+'/generated_preprocess.hpp', bytes=64, sha256='same-header')
            return dict(project_sources=[dict(path='phase2.cpp', bytes=42, sha256='same-source'), header],
                        dependency_units=[dict(generated_preprocess_header=header)],
                        compiler_tools_and_link_libraries=[dict(path='compiler', sha256='same-tool')])
        red, green = fixture('red'), fixture('green')
        self.assertTrue(c.equivalent_build_inputs(red, green))
        for key in ['sha256', 'bytes']:
            changed = fixture('green')
            changed['dependency_units'][0]['generated_preprocess_header'][key] = 'different'
            with self.assertRaises(ValueError):
                c.equivalent_build_inputs(red, changed)
        changed = fixture('green')
        changed['project_sources'][0]['sha256'] = 'different-source'
        with self.assertRaises(ValueError):
            c.equivalent_build_inputs(red, changed)
        changed = fixture('green')
        changed['project_sources'].append(dict(changed['dependency_units'][0]['generated_preprocess_header']))
        with self.assertRaises(ValueError):
            c.equivalent_build_inputs(red, changed)


if __name__ == '__main__':
    unittest.main()

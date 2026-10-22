import unittest

from bank_reader import geometry, parse_bank


def literal():
    header = '%YAML:1.0\n---\nclass_id: tless_object_1\npyramid_levels: 2\ntemplate_pyramids:\n'
    result = header+'   -\n      template_id: 0\n      templates:\n'
    for level in (0, 1):
        result += ('         -\n            width: 8\n            height: 9\n'
                   '            tl_x: 2\n            tl_y: 3\n            pyramid_level: '+str(level)+
                   '\n            features:\n               - [ 0, 1, 0 ]\n               - [ 8, 9, 7 ]\n')
    return result


class BankReader(unittest.TestCase):
    def test_literal_bank_and_odd_canvas(self):
        bank = parse_bank(literal(), 'tless_object_1')
        self.assertEqual(len(bank), 1)
        self.assertEqual(bank[0][0]['features'], [(0, 1, 0), (8, 9, 7)])
        expected = dict(level=1, canvas_width=32, canvas_height=32, tl_x=2, tl_y=3,
                        width=8, height=9, actual_features=2, min_x=0, min_y=1, max_x=8, max_y=9,
                        min_absolute_x=2, min_absolute_y=4, max_absolute_x=10, max_absolute_y=12,
                        min_canvas_edge_distance=2)
        self.assertEqual(geometry(bank[0][1], 65), expected)

    def test_requested_count_is_not_an_actual_cap(self):
        text = literal().replace('               - [ 0, 1, 0 ]\n',
                                 '               - [ 0, 1, 0 ]\n'*44)
        bank = parse_bank(text, 'tless_object_1')
        self.assertEqual([len(layer['features']) for layer in bank[0]], [45, 45])

    def test_explicit_floor_half_rejects_round_up_edge(self):
        layer = parse_bank(literal(), 'tless_object_1')[0][1]
        layer['tl_x'] = 24  # max x=32: outside explicit 65//2 output.
        with self.assertRaises(ValueError):
            geometry(layer, 65)

    def test_list_structure_and_integer_range_are_required(self):
        corruptions = [
            literal().replace('      templates:\n', ''),
            literal().replace('      templates:\n', '      templates:\n      templates:\n'),
            literal().replace('         -\n', ''),
            literal().replace('            width:', '           width:'),
            literal().replace('tl_x: 2', 'tl_x: 2147483648'),
            literal().replace('[ 8, 9, 7 ]', '[ -2147483649, 9, 7 ]'),
        ]
        for text in corruptions:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_bank(text, 'tless_object_1')

    def test_semantic_corruptions(self):
        for old, new in [('class_id: tless_object_1', 'class_id: tless_object_25'),
                         ('template_id: 0', 'template_id: 2'), ('pyramid_levels: 2', 'pyramid_levels: 3'),
                         ('pyramid_level: 1', 'pyramid_level: 0'), ('[ 8, 9, 7 ]', '[ 8, 9, 8 ]'),
                         ('tl_y: 3', 'other: 3'), ('width: 8', 'width: 8.0')]:
            with self.subTest(old=old), self.assertRaises(ValueError):
                parse_bank(literal().replace(old, new), 'tless_object_1')

    def test_edge_is_not_a_feature_filter(self):
        layer = parse_bank(literal(), 'tless_object_1')[0][1]
        layer['tl_x'] = -1
        with self.assertRaises(ValueError):
            geometry(layer, 64)


if __name__ == '__main__':
    unittest.main()

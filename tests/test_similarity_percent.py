import unittest

from core.similarity import _BKTree, image_similarity_percent


class SimilarityPercentTest(unittest.TestCase):
    def test_identical_hashes_are_100_percent(self):
        import imagehash

        h1 = imagehash.hex_to_hash('0000000000000000')
        h2 = imagehash.hex_to_hash('0000000000000000')

        self.assertEqual(image_similarity_percent(h1, h2), 100.0)

    def test_one_bit_difference_is_about_98_percent(self):
        import imagehash

        h1 = imagehash.hex_to_hash('0000000000000000')
        h2 = imagehash.hex_to_hash('0000000000000001')

        self.assertAlmostEqual(image_similarity_percent(h1, h2), 98.4375, places=4)

    def test_bk_tree_returns_only_hashes_within_distance(self):
        import imagehash

        tree = _BKTree()
        tree.add(imagehash.hex_to_hash('0000000000000000'), 0)
        tree.add(imagehash.hex_to_hash('0000000000000001'), 1)
        tree.add(imagehash.hex_to_hash('ffffffffffffffff'), 2)

        matches = tree.query(imagehash.hex_to_hash('0000000000000000'), 1)

        self.assertIn(0, matches)
        self.assertIn(1, matches)
        self.assertNotIn(2, matches)


if __name__ == '__main__':
    unittest.main()

import unittest

from core.similarity import image_similarity_percent


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


if __name__ == '__main__':
    unittest.main()

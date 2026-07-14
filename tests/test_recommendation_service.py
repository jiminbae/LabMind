import unittest

from backend.recommendation_service import AlternativeRepository, find_alternatives


class RecommendationServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository = AlternativeRepository()

    def test_find_reviewed_alternatives_case_insensitively(self) -> None:
        recommendations = self.repository.find_by_catalog_number(" hs4323k ")

        self.assertEqual(len(recommendations), 2)
        self.assertEqual(recommendations[0].catalog_number, "HS4325")
        self.assertIn("verify", recommendations[0].compatibility_note.lower())

    def test_recommendation_contains_product_price_and_url(self) -> None:
        recommendation = find_alternatives("EP022363514")[0]

        self.assertIsNotNone(recommendation.product)
        self.assertTrue(recommendation.product.found)
        self.assertEqual(recommendation.product.catalog_number, "05-408-129")
        self.assertEqual(recommendation.product.price_usd, 148.4)
        self.assertTrue(recommendation.product.url.startswith("https://"))

    def test_unknown_product_has_no_alternatives(self) -> None:
        self.assertEqual(self.repository.find_by_catalog_number("UNKNOWN-001"), [])

    def test_out_of_stock_demo_item_has_alternatives(self) -> None:
        recommendations = self.repository.find_by_catalog_number("HS4325")

        self.assertGreaterEqual(len(recommendations), 1)
        self.assertNotEqual(recommendations[0].catalog_number, "HS4325")


if __name__ == "__main__":
    unittest.main()

import unittest

from backend.product_service import ProductRepository, enrich_product_information


class ProductServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository = ProductRepository()

    def test_find_product_and_parse_numeric_fields(self) -> None:
        product = self.repository.find_by_catalog_number(" hs4323k ")

        self.assertTrue(product.found)
        self.assertEqual(product.catalog_number, "HS4323K")
        self.assertEqual(product.brand, "Sigma-Aldrich")
        self.assertEqual(product.volume_ml, 1.5)
        self.assertEqual(product.pack_size, 500)
        self.assertAlmostEqual(product.unit_price_usd or 0, 0.0424)

    def test_empty_numeric_fields_become_none(self) -> None:
        product = self.repository.find_by_catalog_number("Z688312")

        self.assertTrue(product.found)
        self.assertIsNone(product.diameter_mm)
        self.assertIsNone(product.height_mm)

    def test_missing_product_has_stable_shape(self) -> None:
        product = enrich_product_information("UNKNOWN-001")

        self.assertFalse(product.found)
        self.assertEqual(product.catalog_number, "UNKNOWN-001")
        self.assertIsNone(product.price_usd)


if __name__ == "__main__":
    unittest.main()

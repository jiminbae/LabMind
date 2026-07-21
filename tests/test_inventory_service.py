import unittest

from backend.inventory_service import InventoryRepository, find_inventory_item


class InventoryServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository = InventoryRepository()

    def test_find_existing_item_case_insensitively(self) -> None:
        item = self.repository.find_by_catalog_number("  hs4323k ")

        self.assertTrue(item.found)
        self.assertEqual(item.catalog_number, "HS4323K")
        self.assertEqual(item.expiry_date, "2027-10-31")
        self.assertEqual(item.quantity, 94)
        self.assertEqual(item.location, "Shelf A1")

    def test_missing_item_has_stable_shape(self) -> None:
        item = self.repository.find_by_catalog_number("UNKNOWN-001")

        self.assertFalse(item.found)
        self.assertEqual(item.catalog_number, "UNKNOWN-001")
        self.assertIsNone(item.quantity)

    def test_convenience_function_uses_default_inventory(self) -> None:
        item = find_inventory_item("HS4325")

        self.assertTrue(item.found)
        self.assertEqual(item.quantity, 20)


if __name__ == "__main__":
    unittest.main()

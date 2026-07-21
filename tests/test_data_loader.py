import os
import tempfile
import unittest
from pathlib import Path

from data_loader import load_alternatives, load_inventory, load_products


class DataLoaderTests(unittest.TestCase):
    def test_inventory_sku_is_standardized_to_catalog_number(self) -> None:
        frame = load_inventory()

        self.assertIn("catalog_number", frame.columns)
        self.assertNotIn("sku", frame.columns)
        self.assertEqual(len(frame), 20)
        self.assertEqual(frame.iloc[0]["catalog_number"], "HS4323K")

    def test_all_repository_tables_load(self) -> None:
        products = load_products()
        alternatives = load_alternatives()

        self.assertGreater(len(products), 0)
        self.assertGreater(len(alternatives), 0)
        self.assertIn("so verify rack and rotor fit.", alternatives.iloc[1]["compatibility_note"])

    def test_explicit_path_works_outside_repository_directory(self) -> None:
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".csv",
            delete=False,
        )
        handle.write("sku,brand,expiry_date,quantity,location\nTEST-1,Brand,2027-10,3,A1\n")
        handle.close()
        inventory_path = Path(handle.name)
        original_directory = Path.cwd()

        try:
            os.chdir(inventory_path.parent)
            frame = load_inventory(inventory_path)
        finally:
            os.chdir(original_directory)
            inventory_path.unlink(missing_ok=True)

        self.assertEqual(frame.iloc[0]["catalog_number"], "TEST-1")
        self.assertEqual(frame.iloc[0]["quantity"], "3")


if __name__ == "__main__":
    unittest.main()

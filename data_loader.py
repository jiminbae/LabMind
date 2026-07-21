"""Shared pandas loaders for the repository CSV data files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
PRODUCTS_PATH = PROJECT_ROOT / "products.csv"
INVENTORY_PATH = PROJECT_ROOT / "inventory.csv"
ALTERNATIVES_PATH = PROJECT_ROOT / "alternatives.csv"


def _load_csv(path: str | Path) -> pd.DataFrame:
    """Load CSV values as strings so identifiers and empty cells stay stable."""

    return pd.read_csv(
        Path(path),
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
    )


def load_products(path: str | Path = PRODUCTS_PATH) -> pd.DataFrame:
    """Load the product reference data."""

    return _load_csv(path)


def load_inventory(path: str | Path = INVENTORY_PATH) -> pd.DataFrame:
    """Load inventory and standardize ``sku`` to ``catalog_number``."""

    frame = _load_csv(path)
    if "catalog_number" not in frame.columns and "sku" in frame.columns:
        frame = frame.rename(columns={"sku": "catalog_number"})
    return frame


def load_alternatives(path: str | Path = ALTERNATIVES_PATH) -> pd.DataFrame:
    """Load the reviewed alternative-product mappings."""

    return _load_csv(path)


def check_files_exist() -> bool:
    """Return whether all three repository data files are available."""

    paths = (PRODUCTS_PATH, INVENTORY_PATH, ALTERNATIVES_PATH)
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        print(f"Missing files: {missing}")
        return False
    print("All data files are ready.")
    return True


def show_summary() -> None:
    """Print the row and column counts for the repository data files."""

    if not check_files_exist():
        return

    dataframes = {
        "products.csv": load_products(),
        "inventory.csv": load_inventory(),
        "alternatives.csv": load_alternatives(),
    }
    for filename, frame in dataframes.items():
        print(f"{filename}: {len(frame)} rows, {len(frame.columns)} columns")


if __name__ == "__main__":
    show_summary()

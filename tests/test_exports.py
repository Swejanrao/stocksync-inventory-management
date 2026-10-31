
import json
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).parent.parent
JSON_DIR = BASE_DIR / "exports" / "generated" / "json"
DB_PATH = BASE_DIR / "exports" / "generated" / "sql" / "stocksync_export.db"


def test_products_json_exists():
    path = JSON_DIR / "products.json"
    assert path.exists()

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    assert isinstance(data, list)
    assert len(data) > 0


def test_sqlite_export_exists():
    assert DB_PATH.exists()


def test_sqlite_export_contains_products():
    connection = sqlite3.connect(DB_PATH)

    try:
        count = connection.execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0]

        assert count > 0
    finally:
        connection.close()


def test_sqlite_export_contains_movements():
    connection = sqlite3.connect(DB_PATH)

    try:
        count = connection.execute(
            "SELECT COUNT(*) FROM inventory_movements"
        ).fetchone()[0]

        assert count > 0
    finally:
        connection.close()

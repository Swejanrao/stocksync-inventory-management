
import csv
import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "generated"

JSON_DIR = BASE_DIR / "exports" / "generated" / "json"
SQL_DIR = BASE_DIR / "exports" / "generated" / "sql"

# CSV filename -> SQL table name
TABLES = {
    "products.csv": "products",
    "skus.csv": "skus",
    "locations.csv": "locations",
    "inventory_balances.csv": "inventory_balances",
    "inventory_movements.csv": "inventory_movements",
    "orders.csv": "orders",
    "order_lines.csv": "order_lines",
    "reservations.csv": "reservations",
    "replenishment_rules.csv": "replenishment_rules",
    "anomaly_scenarios.csv": "anomaly_scenarios",
    "ground_truth.csv": "ground_truth",
}

# Primary key definitions
PRIMARY_KEYS = {
    "products": "product_id",
    "skus": "sku_id",
    "locations": "location_id",
    "inventory_balances": "balance_id",
    "inventory_movements": "movement_id",
    "orders": "order_id",
    "order_lines": "order_line_id",
    "reservations": "reservation_id",
    "replenishment_rules": "rule_id",
    "anomaly_scenarios": "scenario_id",
    "ground_truth": "scenario_id",
}


def get_csv_files():
    files = []

    for filename, table_name in TABLES.items():
        path = DATA_DIR / filename

        if path.exists():
            files.append((path, table_name))

    return files


def export_json(csv_path, table_name):
    output_path = JSON_DIR / f"{table_name}.json"

    with csv_path.open("r", newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)

        with output_path.open("w", encoding="utf-8") as target:
            target.write("[\n")

            first = True

            for row in reader:
                if not first:
                    target.write(",\n")

                json.dump(row, target, ensure_ascii=False)
                first = False

            target.write("\n]\n")

    return output_path


def quote_identifier(identifier):
    # Identifiers come only from the fixed table/CSV schema.
    return '"' + identifier.replace('"', '""') + '"'


def export_sql(csv_files):
    SQL_DIR.mkdir(parents=True, exist_ok=True)

    output_path = SQL_DIR / "stocksync_export.sql"

    # Build a fresh, standalone SQLite database file.
    database_path = SQL_DIR / "stocksync_export.db"

    if database_path.exists():
        database_path.unlink()

    connection = sqlite3.connect(database_path)

    try:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        with output_path.open("w", encoding="utf-8") as sql_file:
            sql_file.write("-- StockSync generated SQL export\n")
            sql_file.write("-- Generated from synthetic CSV data\n\n")
            sql_file.write("PRAGMA foreign_keys = ON;\n\n")

            for csv_path, table_name in csv_files:
                with csv_path.open(
                    "r", newline="", encoding="utf-8"
                ) as source:
                    reader = csv.DictReader(source)
                    columns = reader.fieldnames

                    if not columns:
                        continue

                    quoted_columns = [
                        quote_identifier(column) for column in columns
                    ]

                    primary_key = PRIMARY_KEYS.get(table_name)

                    definitions = []

                    for column in columns:
                        definition = f"{quote_identifier(column)} TEXT"

                        if column == primary_key:
                            definition += " PRIMARY KEY"

                        definitions.append(definition)

                    create_sql = (
                        f"CREATE TABLE {quote_identifier(table_name)} "
                        f"({', '.join(definitions)});"
                    )

                    cursor.execute(create_sql)
                    sql_file.write(create_sql + "\n\n")

                    placeholders = ", ".join("?" for _ in columns)

                    insert_sql = (
                        f"INSERT INTO {quote_identifier(table_name)} "
                        f"({', '.join(quoted_columns)}) "
                        f"VALUES ({placeholders})"
                    )

                    sql_file.write(
                        f"-- Records for {table_name}\n"
                    )

                    for row in reader:
                        values = [row.get(column) for column in columns]

                        cursor.execute(insert_sql, values)

                        sql_values = []

                        for value in values:
                            if value is None:
                                sql_values.append("NULL")
                            else:
                                escaped = value.replace("'", "''")
                                sql_values.append(f"'{escaped}'")

                        sql_file.write(
                            f"INSERT INTO {quote_identifier(table_name)} "
                            f"({', '.join(quoted_columns)}) "
                            f"VALUES ({', '.join(sql_values)});\n"
                        )

                    sql_file.write("\n")

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return output_path, database_path


def main():
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    SQL_DIR.mkdir(parents=True, exist_ok=True)

    csv_files = get_csv_files()

    if not csv_files:
        raise FileNotFoundError(
            f"No supported CSV files found in {DATA_DIR}"
        )

    print("\nSTOCKSYNC DATA EXPORT")
    print("-" * 45)

    for csv_path, table_name in csv_files:
        output_path = export_json(csv_path, table_name)
        print(f"JSON created: {output_path}")

    sql_path, database_path = export_sql(csv_files)

    print(f"\nSQL file created: {sql_path}")
    print(f"SQLite database created: {database_path}")

    print("\nExport completed successfully.")


if __name__ == "__main__":
    main()

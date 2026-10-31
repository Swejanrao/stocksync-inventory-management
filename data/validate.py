
import csv
import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent / "generated"


def read_csv(filename):
    path = DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def check_unique(rows, field, label, errors):
    values = [row[field] for row in rows]

    if len(values) != len(set(values)):
        errors.append(f"{label}: duplicate values found in {field}")


def validate_dataset():
    errors = []
    checks = {}

    products = read_csv("products.csv")
    skus = read_csv("skus.csv")
    locations = read_csv("locations.csv")
    balances = read_csv("inventory_balances.csv")
    movements = read_csv("inventory_movements.csv")
    orders = read_csv("orders.csv")
    order_lines = read_csv("order_lines.csv")
    reservations = read_csv("reservations.csv")
    rules = read_csv("replenishment_rules.csv")

    # 1. Primary key uniqueness
    check_unique(products, "product_id", "Products", errors)
    check_unique(skus, "sku_id", "SKUs", errors)
    check_unique(locations, "location_id", "Locations", errors)
    check_unique(balances, "balance_id", "Balances", errors)
    check_unique(movements, "movement_id", "Movements", errors)
    check_unique(orders, "order_id", "Orders", errors)
    check_unique(order_lines, "order_line_id", "Order lines", errors)
    check_unique(reservations, "reservation_id", "Reservations", errors)

    # 2. Foreign key integrity
    product_ids = {row["product_id"] for row in products}
    sku_ids = {row["sku_id"] for row in skus}
    location_ids = {row["location_id"] for row in locations}
    order_ids = {row["order_id"] for row in orders}

    for row in skus:
        if row["product_id"] not in product_ids:
            errors.append(f"SKU {row['sku_id']} has an invalid product_id")

    for row in balances:
        if row["sku_id"] not in sku_ids:
            errors.append(f"Balance {row['balance_id']} has an invalid SKU")

        if row["location_id"] not in location_ids:
            errors.append(f"Balance {row['balance_id']} has an invalid location")

    for row in movements:
        if row["sku_id"] not in sku_ids:
            errors.append(f"Movement {row['movement_id']} has an invalid SKU")

        for field in ("from_location_id", "to_location_id"):
            value = row.get(field)

            if value and value not in location_ids:
                errors.append(
                    f"Movement {row['movement_id']} has an invalid {field}"
                )

    for row in order_lines:
        if row["order_id"] not in order_ids:
            errors.append(f"Order line {row['order_line_id']} has an invalid order")

        if row["sku_id"] not in sku_ids:
            errors.append(f"Order line {row['order_line_id']} has an invalid SKU")

    for row in reservations:
        if row["order_id"] not in order_ids:
            errors.append(
                f"Reservation {row['reservation_id']} has an invalid order"
            )

        if row["sku_id"] not in sku_ids:
            errors.append(
                f"Reservation {row['reservation_id']} has an invalid SKU"
            )

        if row["location_id"] not in location_ids:
            errors.append(
                f"Reservation {row['reservation_id']} has an invalid location"
            )

    for row in rules:
        if row["sku_id"] not in sku_ids:
            errors.append(f"Rule {row['rule_id']} has an invalid SKU")

        if row["location_id"] not in location_ids:
            errors.append(f"Rule {row['rule_id']} has an invalid location")

    # 3. Numeric and arithmetic checks
    for row in balances:
        on_hand = int(row["on_hand"])
        reserved = int(row["reserved"])
        blocked = int(row["blocked"])
        in_transit = int(row["in_transit"])
        safety_stock = int(row["safety_stock"])

        if min(on_hand, reserved, blocked, in_transit, safety_stock) < 0:
            errors.append(
                f"Balance {row['balance_id']} contains a negative quantity"
            )

        if reserved > on_hand:
            errors.append(
                f"Balance {row['balance_id']} has reserved stock above on-hand"
            )

    for row in order_lines:
        if int(row["quantity"]) <= 0:
            errors.append(f"Order line {row['order_line_id']} has invalid quantity")

    for row in movements:
        if int(row["quantity"]) <= 0:
            errors.append(f"Movement {row['movement_id']} has invalid quantity")

    # 4. Reconcile on-hand stock from movements
    movement_totals = defaultdict(int)

    for row in movements:
        sku_id = row["sku_id"]
        location_id = row["location_id"]
        movement_type = row["movement_type"].lower()
        quantity = int(row["quantity"])

        if movement_type in (
            "opening",
            "receipt",
            "return",
            "adjustment_in",
            "transfer_in",
        ):
            movement_totals[(sku_id, location_id)] += quantity

        elif movement_type in (
            "sale",
            "adjustment_out",
            "transfer_out",
        ):
            movement_totals[(sku_id, location_id)] -= quantity

        elif movement_type == "damage":
            pass

    reconciliation_errors = 0

    for row in balances:
        key = (row["sku_id"], row["location_id"])
        expected = movement_totals[key]
        actual = int(row["on_hand"])

        if expected != actual:
            reconciliation_errors += 1
            errors.append(
                f"Balance {row['balance_id']} mismatch: "
                f"expected {expected}, actual {actual}"
            )

    # 5. Report counts
    checks = {
        "products": len(products),
        "skus": len(skus),
        "locations": len(locations),
        "inventory_balances": len(balances),
        "inventory_movements": len(movements),
        "orders": len(orders),
        "order_lines": len(order_lines),
        "reservations": len(reservations),
        "replenishment_rules": len(rules),
        "reconciliation_errors": reconciliation_errors,
    }

    report = {
        "status": "PASS" if not errors else "FAIL",
        "checks": checks,
        "error_count": len(errors),
        "errors": errors[:200],
    }

    report_path = DATA_DIR / "validation_summary.json"

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    print("\nSTOCKSYNC DATA VALIDATION")
    print("-" * 40)

    for name, count in checks.items():
        print(f"{name}: {count:,}")

    print("-" * 40)
    print(f"Status: {report['status']}")
    print(f"Errors: {len(errors)}")
    print(f"Report saved: {report_path}")

    if errors:
        print("\nFirst validation errors:")
        for error in errors[:20]:
            print("-", error)
        return report


if __name__ == "__main__":
    validate_dataset()

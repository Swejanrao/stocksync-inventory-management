"""
StockSync - Synthetic Inventory Data Generator

Default dataset:
    Products:       5,000
    SKUs:           5,000
    Locations:      100
    Movements:      1,000,000 (before order fulfillment movements)
    Orders:         50,000
    Random seed:    20261022

Run:
    python data/generator.py

Small test:
    python data/generator.py --products 50 --locations 10 --movements 1000 --orders 100
"""

import argparse
import csv
import hashlib
import json
import random

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


# =========================================================
# CONFIGURATION
# =========================================================

DEFAULT_SEED = 20261022
DEFAULT_PRODUCTS = 5000
DEFAULT_LOCATIONS = 100
DEFAULT_MOVEMENTS = 1_000_000
DEFAULT_ORDERS = 50_000

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "generated"

START_DATE = datetime(2025, 1, 1)
END_DATE = datetime(2026, 10, 22)

CHANNELS = ["ONLINE", "STORE", "MARKETPLACE"]

PRODUCT_CATEGORIES = [
    "Electronics",
    "Clothing",
    "Home and Kitchen",
    "Books",
    "Furniture",
    "Sports",
    "Beauty",
    "Grocery",
    "Toys",
    "Accessories",
]

LOCATION_TYPES = [
    "WAREHOUSE",
    "STORE",
    "DISTRIBUTION_CENTER",
]


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def make_id(prefix, number, width=6):
    return f"{prefix}-{number:0{width}d}"


def random_datetime(rng):
    total_seconds = int(
        (END_DATE - START_DATE).total_seconds()
    )

    seconds = rng.randint(0, total_seconds)

    return (
        START_DATE + timedelta(seconds=seconds)
    ).strftime("%Y-%m-%d %H:%M:%S")


def write_csv(file_path, fieldnames, rows):
    file_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0

    with file_path.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(row)
            count += 1

    return count


def sha256_file(file_path):
    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b""
        ):
            digest.update(chunk)

    return digest.hexdigest()


def count_csv_rows(file_path):
    with file_path.open(
        "r",
        newline="",
        encoding="utf-8"
    ) as file:

        return max(0, sum(1 for _ in file) - 1)


# =========================================================
# PRODUCTS
# =========================================================

def generate_products(rng, product_count):

    rows = []

    for number in range(1, product_count + 1):

        unit_cost = round(rng.uniform(5, 500), 2)
        unit_price = round(
            unit_cost * rng.uniform(1.2, 2.5),
            2
        )

        rows.append({
            "product_id": make_id("PRD", number),
            "product_name": f"StockSync Product {number:06d}",
            "category": rng.choice(PRODUCT_CATEGORIES),
            "brand": f"Brand-{rng.randint(1, 100):03d}",
            "unit_cost": unit_cost,
            "unit_price": unit_price,
            "is_active": True,
            "created_at": random_datetime(rng),
        })

    return rows


# =========================================================
# SKUS
# =========================================================

def generate_skus(rng, products):

    rows = []

    for number, product in enumerate(products, start=1):

        rows.append({
            "sku_id": make_id("SKU", number),
            "product_id": product["product_id"],
            "sku_code": f"STK-{number:06d}",
            "sku_name": f"{product['product_name']} - Standard",
            "barcode": f"890{number:010d}",
            "unit_of_measure": "EACH",
            "weight_kg": round(rng.uniform(0.1, 25), 2),
            "is_active": True,
            "created_at": product["created_at"],
        })

    return rows


# =========================================================
# LOCATIONS
# =========================================================

def generate_locations(location_count):

    rows = []

    for number in range(1, location_count + 1):

        location_type = LOCATION_TYPES[
            (number - 1) % len(LOCATION_TYPES)
        ]

        rows.append({
            "location_id": make_id("LOC", number),
            "location_name": f"{location_type.title()} {number:03d}",
            "location_type": location_type,
            "city": f"City-{((number - 1) % 25) + 1:02d}",
            "state": f"State-{((number - 1) % 10) + 1:02d}",
            "country": "India",
            "is_active": True,
            "created_at": "2025-01-01 00:00:00",
        })

    return rows


# =========================================================
# INVENTORY BALANCES
# =========================================================


def write_inventory_balances(balances, file_path):

    fields = [
        "balance_id",
        "sku_id",
        "location_id",
        "on_hand",
        "reserved",
        "blocked",
        "safety_stock",
        "in_transit",
        "available_stock",
        "last_updated",
    ]

    def rows():

        for number, balance in enumerate(
            balances.values(),
            start=1
        ):

            available = max(
                0,
                balance["on_hand"]
                - balance["reserved"]
                - balance["blocked"]
                - balance["safety_stock"]
            )

            yield {
                "balance_id": f"BAL-{number:08d}",
                "sku_id": balance["sku_id"],
                "location_id": balance["location_id"],
                "on_hand": balance["on_hand"],
                "reserved": balance["reserved"],
                "blocked": balance["blocked"],
                "safety_stock": balance["safety_stock"],
                "in_transit": balance["in_transit"],
                "available_stock": available,
                "last_updated": "2026-10-22 00:00:00",
            }

    return write_csv(file_path, fields, rows())



# =========================================================
# INVENTORY MOVEMENTS
# =========================================================

MOVEMENT_FIELDS = [
    "movement_id",
    "sku_id",
    "location_id",
    "movement_type",
    "quantity",
    "reference_id",
    "reason",
    "created_at",
]


def generate_inventory(
    rng,
    skus,
    locations,
    movement_count,
    output_dir
):
    balances = {}
    balance_keys = []

    opening_count = len(skus) * len(locations)

    if movement_count < opening_count:
        raise ValueError(
            f"Movements must be at least {opening_count}. "
            "Every SKU-location pair requires an opening movement."
        )

    movement_number = 0
    movement_path = output_dir / "inventory_movements.csv"

    with movement_path.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as movement_file:

        writer = csv.DictWriter(
            movement_file,
            fieldnames=MOVEMENT_FIELDS
        )
        writer.writeheader()

        # Opening inventory
        for sku in skus:
            for location in locations:
                sku_id = sku["sku_id"]
                location_id = location["location_id"]

                on_hand = rng.randint(20, 500)
                blocked = rng.randint(0, min(5, on_hand // 10))
                safety_stock = rng.randint(2, 20)

                key = (sku_id, location_id)

                balances[key] = {
                    "sku_id": sku_id,
                    "location_id": location_id,
                    "on_hand": on_hand,
                    "reserved": 0,
                    "blocked": blocked,
                    "safety_stock": safety_stock,
                    "in_transit": 0,
                }

                balance_keys.append(key)
                movement_number += 1

                writer.writerow({
                    "movement_id": (
                        f"MOV-{END_DATE.year}-{movement_number:08d}"
                    ),
                    "sku_id": sku_id,
                    "location_id": location_id,
                    "movement_type": "opening",
                    "quantity": on_hand,
                    "reference_id": f"OPEN-{movement_number:08d}",
                    "reason": "Initial inventory balance",
                    "created_at": "2025-01-01 00:00:00",
                })

        # Additional movements
        additional_count = movement_count - opening_count

        for _ in range(additional_count):
            key = rng.choice(balance_keys)
            balance = balances[key]

            available = (
                balance["on_hand"]
                - balance["blocked"]
                - balance["safety_stock"]
            )

            movement_types = [
                "receipt",
                "return",
                "adjustment_in",
            ]

            if available > 0:
                movement_types.extend([
                    "sale",
                    "damage",
                    "adjustment_out",
                ])

            movement_type = rng.choice(movement_types)

            if movement_type in (
                "receipt",
                "return",
                "adjustment_in",
            ):
                quantity = rng.randint(1, 50)
                balance["on_hand"] += quantity

            elif movement_type == "damage":
                quantity = rng.randint(
                    1,
                    min(available, 20)
                )
                balance["blocked"] += quantity

            else:
                quantity = rng.randint(
                    1,
                    min(available, 20)
                )
                balance["on_hand"] -= quantity

            movement_number += 1

            writer.writerow({
                "movement_id": (
                    f"MOV-{END_DATE.year}-{movement_number:08d}"
                ),
                "sku_id": balance["sku_id"],
                "location_id": balance["location_id"],
                "movement_type": movement_type,
                "quantity": quantity,
                "reference_id": f"REF-{movement_number:08d}",
                "reason": movement_type.replace("_", " ").title(),
                "created_at": random_datetime(rng),
            })

    write_inventory_balances(
        balances,
        output_dir / "inventory_balances.csv"
    )

    return balances, movement_number


# =========================================================
# ORDERS, ORDER LINES, RESERVATIONS AND SHIPMENTS
# =========================================================

def generate_orders(
    rng,
    skus,
    balances,
    order_count,
    output_dir,
    movement_count,
):

    order_fields = [
        "order_id",
        "customer_id",
        "channel",
        "order_status",
        "fulfillment_location_id",
        "order_total",
        "created_at",
        "updated_at",
    ]

    line_fields = [
        "order_line_id",
        "order_id",
        "sku_id",
        "quantity",
        "unit_price",
        "line_total",
    ]

    reservation_fields = [
        "reservation_id",
        "order_id",
        "sku_id",
        "location_id",
        "quantity",
        "reservation_status",
        "reserved_at",
        "expires_at",
        "released_at",
    ]

    shipment_fields = [
        "shipment_id",
        "order_id",
        "location_id",
        "shipment_status",
        "carrier",
        "tracking_number",
        "shipped_at",
        "delivered_at",
    ]

    sku_price_map = {
        sku["sku_id"]: sku.get("unit_price", 100.0)
        for sku in skus
    }

    eligible_keys = [
        key
        for key, balance in balances.items()
        if (
            balance["on_hand"]
            - balance["reserved"]
            - balance["blocked"]
            - balance["safety_stock"]
        ) > 0
    ]

    if not eligible_keys:
        raise ValueError("No available inventory for order generation.")

    order_path = output_dir / "orders.csv"
    line_path = output_dir / "order_lines.csv"
    reservation_path = output_dir / "reservations.csv"
    shipment_path = output_dir / "shipments.csv"
    movement_path = output_dir / "inventory_movements.csv"

    shipment_number = 0
    reservation_number = 0

    status_counts = defaultdict(int)

    with (
        order_path.open("w", newline="", encoding="utf-8") as order_file,
        line_path.open("w", newline="", encoding="utf-8") as line_file,
        reservation_path.open(
            "w", newline="", encoding="utf-8"
        ) as reservation_file,
        shipment_path.open(
            "w", newline="", encoding="utf-8"
        ) as shipment_file,
        movement_path.open(
            "a", newline="", encoding="utf-8"
        ) as movement_file,
    ):

        order_writer = csv.DictWriter(
            order_file,
            fieldnames=order_fields
        )

        line_writer = csv.DictWriter(
            line_file,
            fieldnames=line_fields
        )

        reservation_writer = csv.DictWriter(
            reservation_file,
            fieldnames=reservation_fields
        )

        shipment_writer = csv.DictWriter(
            shipment_file,
            fieldnames=shipment_fields
        )

        movement_writer = csv.DictWriter(
            movement_file,
            fieldnames=MOVEMENT_FIELDS
        )

        order_writer.writeheader()
        line_writer.writeheader()
        reservation_writer.writeheader()
        shipment_writer.writeheader()

        for number in range(1, order_count + 1):

            order_id = (
                f"ORD-{END_DATE.year}-{number:06d}"
            )

            selected_key = None

            # Find a location with sufficient available stock.
            for _ in range(20):

                candidate = rng.choice(eligible_keys)
                candidate_balance = balances[candidate]

                available = (
                    candidate_balance["on_hand"]
                    - candidate_balance["reserved"]
                    - candidate_balance["blocked"]
                    - candidate_balance["safety_stock"]
                )

                if available >= 1:
                    selected_key = candidate
                    break

            if selected_key is None:
                selected_key = rng.choice(eligible_keys)

            sku_id, location_id = selected_key
            balance = balances[selected_key]

            available = (
                balance["on_hand"]
                - balance["reserved"]
                - balance["blocked"]
                - balance["safety_stock"]
            )

            created_at = random_datetime(rng)
            channel = rng.choice(CHANNELS)

            quantity = 0
            reservation_status = None

            order_status = "PENDING"

            if available >= 1:

                quantity = rng.randint(
                    1,
                    min(3, available)
                )

                order_status = rng.choices(
                    [
                        "RESERVED",
                        "FULFILLED",
                        "CANCELLED",
                        "PENDING",
                    ],
                    weights=[45, 25, 10, 20],
                    k=1
                )[0]

                if order_status == "RESERVED":

                    reservation_status = "ACTIVE"
                    balance["reserved"] += quantity

                elif order_status == "FULFILLED":

                    reservation_status = "CONSUMED"
                    balance["on_hand"] -= quantity

                   # Record fulfilled order as a positive-quantity sale movement.
                    movement_count += 1

                    movement_writer.writerow({
                       "movement_id": (
                          f"MOV-{END_DATE.year}-{movement_count:08d}"
                    ),
                    "sku_id": sku_id,
                    "location_id": location_id,
                    "movement_type": "sale",
                    "quantity": quantity,
                    "reference_id": order_id,
                    "reason": "Order fulfillment",
                    "created_at": created_at,
                })

                elif order_status == "CANCELLED":

                    reservation_status = "RELEASED"

                else:

                    quantity = 0

            else:

                order_status = "PENDING"

            unit_price = sku_price_map[sku_id]
            line_total = round(quantity * unit_price, 2)

            order_writer.writerow({
                "order_id": order_id,
                "customer_id": (
                    f"CUS-{rng.randint(1, 100000):06d}"
                ),
                "channel": channel,
                "order_status": order_status,
                "fulfillment_location_id": location_id,
                "order_total": line_total,
                "created_at": created_at,
                "updated_at": created_at,
            })

            if quantity > 0:

                line_writer.writerow({
                    "order_line_id": f"LINE-{number:08d}",
                    "order_id": order_id,
                    "sku_id": sku_id,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "line_total": line_total,
                })

                reservation_number += 1

                expires_at = (
                    datetime.strptime(
                        created_at,
                        "%Y-%m-%d %H:%M:%S"
                    ) + timedelta(hours=2)
                ).strftime("%Y-%m-%d %H:%M:%S")

                reservation_writer.writerow({
                    "reservation_id": f"RES-{order_id}-01",
                    "order_id": order_id,
                    "sku_id": sku_id,
                    "location_id": location_id,
                    "quantity": quantity,
                    "reservation_status": reservation_status,
                    "reserved_at": created_at,
                    "expires_at": expires_at,
                    "released_at": (
                        created_at
                        if reservation_status == "RELEASED"
                        else ""
                    ),
                })

            # Shipment records for fulfilled orders.
            if order_status == "FULFILLED":

                shipment_number += 1

                shipment_writer.writerow({
                    "shipment_id": (
                        f"SHP-{END_DATE.year}-{shipment_number:06d}"
                    ),
                    "order_id": order_id,
                    "location_id": location_id,
                    "shipment_status": "SHIPPED",
                    "carrier": rng.choice([
                        "BlueDart",
                        "Delhivery",
                        "DTDC",
                        "India Post",
                    ]),
                    "tracking_number": (
                        f"TRK{shipment_number:010d}"
                    ),
                    "shipped_at": created_at,
                    "delivered_at": "",
                })

            status_counts[order_status] += 1

    return {
        "shipment_count": shipment_number,
        "reservation_count": reservation_number,
        "movement_count": movement_count,
        "order_status_counts": dict(status_counts),
    }


# =========================================================
# REPLENISHMENT RULES
# =========================================================

def generate_replenishment_rules(
    rng,
    skus,
    locations,
    output_dir
):

    fields = [
        "rule_id",
        "sku_id",
        "location_id",
        "reorder_point",
        "reorder_quantity",
        "lead_time_days",
        "safety_stock",
        "is_active",
    ]

    def rows():

        number = 0

        for sku in skus:

            for location in locations:

                number += 1

                safety_stock = rng.randint(2, 20)

                yield {
                    "rule_id": f"RUL-{number:08d}",
                    "sku_id": sku["sku_id"],
                    "location_id": location["location_id"],
                    "reorder_point": (
                        safety_stock + rng.randint(10, 100)
                    ),
                    "reorder_quantity": rng.randint(50, 250),
                    "lead_time_days": rng.randint(1, 21),
                    "safety_stock": safety_stock,
                    "is_active": True,
                }

    return write_csv(
        output_dir / "replenishment_rules.csv",
        fields,
        rows()
    )


# =========================================================
# CHANNEL BUFFERS
# =========================================================

def generate_channel_buffers(rng, skus, output_dir):

    fields = [
        "buffer_id",
        "sku_id",
        "channel",
        "buffer_quantity",
        "is_active",
    ]

    def rows():

        number = 0

        for sku in skus:

            for channel in CHANNELS:

                number += 1

                yield {
                    "buffer_id": f"BUF-{number:08d}",
                    "sku_id": sku["sku_id"],
                    "channel": channel,
                    "buffer_quantity": rng.randint(0, 10),
                    "is_active": True,
                }

    return write_csv(
        output_dir / "channel_buffers.csv",
        fields,
        rows()
    )


# =========================================================
# GENERATION SUMMARY
# =========================================================

def write_summary(output_dir, seed, counts, parameters):

    files = {}

    for file_path in sorted(output_dir.glob("*.csv")):

        files[file_path.name] = {
            "rows": count_csv_rows(file_path),
            "sha256": sha256_file(file_path),
            "size_bytes": file_path.stat().st_size,
        }

    summary = {
        "project": "StockSync",
        "dataset_type": "synthetic_baseline",
        "seed": seed,
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "parameters": parameters,
        "counts": counts,
        "files": files,
        "status": "GENERATED",
    }

    with (
        output_dir / "generation_summary.json"
    ).open("w", encoding="utf-8") as file:

        json.dump(summary, file, indent=4)

    return summary


# =========================================================
# MAIN GENERATOR
# =========================================================

def generate_dataset(
    products_count=DEFAULT_PRODUCTS,
    locations_count=DEFAULT_LOCATIONS,
    movements_count=DEFAULT_MOVEMENTS,
    orders_count=DEFAULT_ORDERS,
    seed=DEFAULT_SEED,
    output_dir=OUTPUT_DIR,
):

    if products_count < 1:
        raise ValueError("Products must be at least 1.")

    if locations_count < 1:
        raise ValueError("Locations must be at least 1.")

    if orders_count < 0:
        raise ValueError("Orders cannot be negative.")

    minimum_movements = products_count * locations_count

    if movements_count < minimum_movements:
        raise ValueError(
            "Movements must be at least products multiplied by locations."
        )

    rng = random.Random(seed)

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    print("\nStockSync data generation started")
    print("---------------------------------")

    # Products
    print("1/8 Generating products...")

    products = generate_products(
        rng,
        products_count
    )

    write_csv(
        output_dir / "products.csv",
        list(products[0].keys()),
        products
    )

    # SKUs
    print("2/8 Generating SKUs...")

    skus = generate_skus(
        rng,
        products
    )

    # Include product unit price in SKU data for order pricing.
    product_price_map = {
        product["product_id"]: product["unit_price"]
        for product in products
    }

    for sku in skus:
        sku["unit_price"] = product_price_map[sku["product_id"]]

    write_csv(
        output_dir / "skus.csv",
        list(skus[0].keys()),
        skus
    )

    # Locations
    print("3/8 Generating locations...")

    locations = generate_locations(
        locations_count
    )

    write_csv(
        output_dir / "locations.csv",
        list(locations[0].keys()),
        locations
    )

    # Inventory and movements
    print("4/8 Generating inventory and movements...")

    balances, actual_movement_count = generate_inventory(
        rng,
        skus,
        locations,
        movements_count,
        output_dir
    )

    # Orders and fulfillment movements
    print("5/8 Generating orders and related records...")

    order_result = generate_orders(
        rng,
        skus,
        balances,
        orders_count,
        output_dir,
        actual_movement_count,
    )

    actual_movement_count = order_result["movement_count"]

    # Rewrite final balance snapshot after fulfilled orders
    # and active reservations have changed inventory.
    print("6/8 Updating final inventory balances...")

    write_inventory_balances(
        balances,
        output_dir / "inventory_balances.csv"
    )

    # Replenishment rules
    print("7/8 Generating replenishment rules...")

    replenishment_count = generate_replenishment_rules(
        rng,
        skus,
        locations,
        output_dir
    )

    # Channel buffers
    print("8/8 Generating channel buffers...")

    channel_buffer_count = generate_channel_buffers(
        rng,
        skus,
        output_dir
    )

    counts = {
        "products": len(products),
        "skus": len(skus),
        "locations": len(locations),
        "inventory_balances": len(balances),
        "inventory_movements": actual_movement_count,
        "orders": orders_count,
        "order_lines": count_csv_rows(
            output_dir / "order_lines.csv"
        ),
        "reservations": order_result["reservation_count"],
        "shipments": order_result["shipment_count"],
        "replenishment_rules": replenishment_count,
        "channel_buffers": channel_buffer_count,
        "order_status_counts": order_result["order_status_counts"],
    }

    parameters = {
        "products": products_count,
        "locations": locations_count,
        "movements": movements_count,
        "orders": orders_count,
    }

    write_summary(
        output_dir,
        seed,
        counts,
        parameters
    )

    print("\nGeneration completed successfully!")
    print("----------------------------------")

    for name, value in counts.items():
        print(f"{name}: {value}")

    print(f"\nOutput directory: {output_dir}")

    return counts


# =========================================================
# COMMAND LINE
# =========================================================

def main():

    parser = argparse.ArgumentParser(
        description="StockSync synthetic inventory data generator"
    )

    parser.add_argument(
        "--products",
        type=int,
        default=DEFAULT_PRODUCTS
    )

    parser.add_argument(
        "--locations",
        type=int,
        default=DEFAULT_LOCATIONS
    )

    parser.add_argument(
        "--movements",
        type=int,
        default=DEFAULT_MOVEMENTS
    )

    parser.add_argument(
        "--orders",
        type=int,
        default=DEFAULT_ORDERS
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED
    )

    parser.add_argument(
        "--output",
        type=str,
        default=str(OUTPUT_DIR)
    )

    args = parser.parse_args()

    generate_dataset(
        products_count=args.products,
        locations_count=args.locations,
        movements_count=args.movements,
        orders_count=args.orders,
        seed=args.seed,
        output_dir=Path(args.output),
    )


if __name__ == "__main__":
    main()

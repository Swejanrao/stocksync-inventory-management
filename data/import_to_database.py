import csv
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import inspect

# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app
from app.extensions import db
from app import models  # Register all models

from app.models import (
    Product,
    SKU,
    Location,
    InventoryBalance,
    InventoryMovement,
    CustomerOrder,
    OrderLine,
    Reservation,
    Shipment,
    ReplenishmentRule,
    ChannelBuffer,
)


DATA_DIR = BASE_DIR / "data" / "generated"
DATABASE_DIR = BASE_DIR / "instance"
DATABASE_PATH = DATABASE_DIR / "stocksync_generated.db"

CSV_FILES = [
    "products.csv",
    "skus.csv",
    "locations.csv",
    "inventory_balances.csv",
    "inventory_movements.csv",
    "orders.csv",
    "order_lines.csv",
    "reservations.csv",
    "shipments.csv",
    "replenishment_rules.csv",
    "channel_buffers.csv",
]

MODELS = [
    Product,
    SKU,
    Location,
    InventoryBalance,
    InventoryMovement,
    CustomerOrder,
    OrderLine,
    Reservation,
    Shipment,
    ReplenishmentRule,
    ChannelBuffer,
]


# --------------------------------------------------
# CSV HELPERS
# --------------------------------------------------

def read_csv(filename):
    path = DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    with path.open(
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        return list(csv.DictReader(file))


def parse_datetime(value, field_name, required=True):
    if value is None or str(value).strip() == "":
        if required:
            raise ValueError(
                f"Missing required datetime: {field_name}"
            )
        return None

    value = str(value).strip()

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid datetime in {field_name}: {value}"
        ) from exc


def integer(value, field_name, default=None):
    if value is None or str(value).strip() == "":
        if default is not None:
            return default

        raise ValueError(
            f"Missing integer value: {field_name}"
        )

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid integer in {field_name}: {value}"
        ) from exc


def decimal_value(value, field_name, default="0"):
    if value is None or str(value).strip() == "":
        value = default

    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(
            f"Invalid decimal in {field_name}: {value}"
        ) from exc

    if not result.is_finite():
        raise ValueError(
            f"Non-finite decimal in {field_name}"
        )

    return result


def boolean_value(value, field_name):
    normalized_value = str(value).strip().lower()

    if normalized_value in {"true", "1", "yes"}:
        return True

    if normalized_value in {"false", "0", "no"}:
        return False

    raise ValueError(
        f"Invalid boolean in {field_name}: {value}"
    )


def normalized(value):
    return str(value or "").strip().lower()


# --------------------------------------------------
# SOURCE FILE VALIDATION
# --------------------------------------------------

def validate_required_files():
    missing = [
        filename
        for filename in CSV_FILES
        if not (DATA_DIR / filename).exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing generated CSV files: "
            + ", ".join(missing)
        )


def load_source_data():
    data = {
        filename[:-4]: read_csv(filename)
        for filename in CSV_FILES
    }

    required_columns = {
        "products": {
            "product_id", "product_name", "category", "brand",
            "unit_cost", "unit_price", "is_active", "created_at",
        },
        "skus": {
            "sku_id", "product_id", "sku_code", "sku_name",
            "barcode", "unit_of_measure", "weight_kg",
            "is_active", "created_at", "unit_price",
        },
        "locations": {
            "location_id", "location_name", "location_type",
            "city", "state", "country", "is_active", "created_at",
        },
        "inventory_balances": {
            "balance_id", "sku_id", "location_id", "on_hand",
            "reserved", "blocked", "safety_stock", "in_transit",
            "available_stock", "last_updated",
        },
        "inventory_movements": {
            "movement_id", "sku_id", "location_id",
            "movement_type", "quantity", "reference_id",
            "reason", "created_at",
        },
        "orders": {
            "order_id", "customer_id", "channel", "order_status",
            "fulfillment_location_id", "order_total",
            "created_at", "updated_at",
        },
        "order_lines": {
            "order_line_id", "order_id", "sku_id",
            "quantity", "unit_price", "line_total",
        },
        "reservations": {
            "reservation_id", "order_id", "sku_id",
            "location_id", "quantity", "reservation_status",
            "reserved_at", "expires_at", "released_at",
        },
        "shipments": {
            "shipment_id", "order_id", "location_id",
            "shipment_status", "carrier", "tracking_number",
            "shipped_at", "delivered_at",
        },
        "replenishment_rules": {
            "rule_id", "sku_id", "location_id",
            "reorder_point", "reorder_quantity",
            "lead_time_days", "safety_stock", "is_active",
        },
        "channel_buffers": {
            "buffer_id", "sku_id", "channel",
            "buffer_quantity", "is_active",
        },
    }

    for name, columns in required_columns.items():
        rows = data[name]

        if not rows:
            raise ValueError(
                f"{name}.csv is empty."
            )

        actual_columns = set(rows[0].keys())
        missing_columns = columns - actual_columns

        if missing_columns:
            raise ValueError(
                f"{name}.csv is missing columns: "
                + ", ".join(sorted(missing_columns))
            )

    return data


def validate_source_relationships(data):
    product_ids = {row["product_id"] for row in data["products"]}
    sku_ids = {row["sku_id"] for row in data["skus"]}
    location_ids = {row["location_id"] for row in data["locations"]}
    order_ids = {row["order_id"] for row in data["orders"]}

    for row in data["skus"]:
        if row["product_id"] not in product_ids:
            raise ValueError(
                f"SKU {row['sku_id']} references an unknown product."
            )

    for row in data["inventory_balances"]:
        if row["sku_id"] not in sku_ids:
            raise ValueError("Balance references an unknown SKU.")

        if row["location_id"] not in location_ids:
            raise ValueError("Balance references an unknown location.")

    for row in data["inventory_movements"]:
        if row["sku_id"] not in sku_ids:
            raise ValueError("Movement references an unknown SKU.")

        if row["location_id"] not in location_ids:
            raise ValueError("Movement references an unknown location.")

    for row in data["orders"]:
        if row["fulfillment_location_id"] not in location_ids:
            raise ValueError(
                f"Order {row['order_id']} references an unknown location."
            )

    for row in data["order_lines"]:
        if row["order_id"] not in order_ids:
            raise ValueError("Order line references an unknown order.")

        if row["sku_id"] not in sku_ids:
            raise ValueError("Order line references an unknown SKU.")

    for row in data["reservations"]:
        if row["order_id"] not in order_ids:
            raise ValueError("Reservation references an unknown order.")

        if row["sku_id"] not in sku_ids:
            raise ValueError("Reservation references an unknown SKU.")

        if row["location_id"] not in location_ids:
            raise ValueError("Reservation references an unknown location.")

    for row in data["shipments"]:
        if row["order_id"] not in order_ids:
            raise ValueError("Shipment references an unknown order.")

        if row["location_id"] not in location_ids:
            raise ValueError("Shipment references an unknown location.")

    for row in data["replenishment_rules"]:
        if row["sku_id"] not in sku_ids:
            raise ValueError("Replenishment rule references an unknown SKU.")

        if row["location_id"] not in location_ids:
            raise ValueError("Replenishment rule references an unknown location.")

    for row in data["channel_buffers"]:
        if row["sku_id"] not in sku_ids:
            raise ValueError("Channel buffer references an unknown SKU.")


# --------------------------------------------------
# DATABASE SAFETY
# --------------------------------------------------

def ensure_database_is_empty():
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    if not existing_tables:
        return

    # Permit a retry if the tables exist but contain no records.
    for model in MODELS:
        if model.__tablename__ in existing_tables:
            if db.session.query(model).first() is not None:
                raise RuntimeError(
                    "The generated database already contains records. "
                    "Import stopped to prevent duplicate data. "
                    f"Database: {DATABASE_PATH}"
                )


# --------------------------------------------------
# MASTER DATA IMPORT
# --------------------------------------------------

def import_products(rows):
    product_map = {}
    product_cost_map = {}

    for row in rows:
        cost = decimal_value(
            row["unit_cost"],
            "product.unit_cost"
        )

        product = Product(
            product_code=row["product_id"],
            name=row["product_name"],
            category=row["category"] or "Uncategorized",
            brand=row["brand"] or None,
            unit_cost=cost,
            active=boolean_value(
                row["is_active"],
                "product.is_active"
            ),
            created_at=parse_datetime(
                row["created_at"],
                "product.created_at"
            ),
        )

        db.session.add(product)
        db.session.flush()

        product_map[row["product_id"]] = product.id
        product_cost_map[row["product_id"]] = cost

    return product_map, product_cost_map


def import_skus(rows, product_map, product_cost_map):
    sku_map = {}

    for row in rows:
        product_source_id = row["product_id"]

        sku = SKU(
            sku_code=row["sku_code"],
            product_id=product_map[product_source_id],
            description=row["sku_name"],
            unit_of_measure=normalized(
                row["unit_of_measure"]
            ) or "each",
            unit_cost=product_cost_map[product_source_id],
            barcode=row["barcode"] or None,
            weight_kg=decimal_value(
                row["weight_kg"],
                "sku.weight_kg"
            ),
            unit_price=decimal_value(
                row["unit_price"],
                "sku.unit_price"
            ),
            active=boolean_value(
                row["is_active"],
                "sku.is_active"
            ),
            created_at=parse_datetime(
                row["created_at"],
                "sku.created_at"
            ),
        )

        db.session.add(sku)
        db.session.flush()

        sku_map[row["sku_id"]] = sku.id

    return sku_map


def import_locations(rows):
    location_map = {}

    for row in rows:
        location = Location(
            location_code=row["location_id"],
            name=row["location_name"],
            location_type=normalized(row["location_type"]),
            channel="none",
            city=row["city"] or None,
            state=row["state"] or None,
            country=row["country"] or None,
            active=boolean_value(
                row["is_active"],
                "location.is_active"
            ),
            created_at=parse_datetime(
                row["created_at"],
                "location.created_at"
            ),
        )

        db.session.add(location)
        db.session.flush()

        location_map[row["location_id"]] = location.id

    return location_map


# --------------------------------------------------
# INVENTORY IMPORT
# --------------------------------------------------

def import_balances(rows, sku_map, location_map):
    for row in rows:
        values = {
            "on_hand": integer(row["on_hand"], "balance.on_hand"),
            "reserved": integer(row["reserved"], "balance.reserved"),
            "blocked": integer(row["blocked"], "balance.blocked"),
            "safety_stock": integer(
                row["safety_stock"],
                "balance.safety_stock"
            ),
            "in_transit": integer(
                row["in_transit"],
                "balance.in_transit"
            ),
        }

        if any(value < 0 for value in values.values()):
            raise ValueError(
                f"Negative inventory quantity in {row['balance_id']}."
            )

        db.session.add(
            InventoryBalance(
                sku_id=sku_map[row["sku_id"]],
                location_id=location_map[row["location_id"]],
                updated_at=parse_datetime(
                    row["last_updated"],
                    "balance.last_updated"
                ),
                **values,
            )
        )


def import_movements(rows, sku_map, location_map):
    incoming = {
        "opening",
        "receipt",
        "return",
        "adjustment_in",
        "transfer_in",
    }

    outgoing = {
        "sale",
        "adjustment_out",
        "transfer_out",
        "damage",
    }

    for row in rows:
        movement_type = normalized(row["movement_type"])
        quantity = integer(
            row["quantity"],
            "movement.quantity"
        )

        if quantity <= 0:
            raise ValueError(
                f"Movement {row['movement_id']} has non-positive quantity."
            )

        location_id = location_map[row["location_id"]]

        if movement_type in incoming:
            from_location_id = None
            to_location_id = location_id

        elif movement_type in outgoing:
            from_location_id = location_id
            to_location_id = None

        else:
            raise ValueError(
                f"Unsupported movement type: {movement_type}"
            )

        db.session.add(
            InventoryMovement(
                movement_code=row["movement_id"],
                sku_id=sku_map[row["sku_id"]],
                from_location_id=from_location_id,
                to_location_id=to_location_id,
                movement_type=movement_type,
                quantity=quantity,
                reference_type="generated",
                reference_id=row["reference_id"] or None,
                note=row["reason"] or None,
                occurred_at=parse_datetime(
                    row["created_at"],
                    "movement.created_at"
                ),
            )
        )


# --------------------------------------------------
# ORDER IMPORT
# --------------------------------------------------

def import_orders(rows, location_map):
    order_map = {}

    status_map = {
        "reserved": "reserved",
        "fulfilled": "completed",
        "completed": "completed",
        "cancelled": "cancelled",
        "pending": "pending",
    }

    for row in rows:
        source_status = normalized(row["order_status"])

        if source_status not in status_map:
            raise ValueError(
                f"Unsupported order status: {source_status}"
            )

        order = CustomerOrder(
            order_code=row["order_id"],
            customer_code=row["customer_id"] or None,
            channel=normalized(row["channel"]),
            status=status_map[source_status],
            fulfillment_location_id=location_map[
                row["fulfillment_location_id"]
            ],
            order_total=decimal_value(
                row["order_total"],
                "order.order_total"
            ),
            created_at=parse_datetime(
                row["created_at"],
                "order.created_at"
            ),
            updated_at=parse_datetime(
                row["updated_at"],
                "order.updated_at"
            ),
        )

        db.session.add(order)
        db.session.flush()

        order_map[row["order_id"]] = order.id

    return order_map


def import_order_lines(rows, order_map, sku_map):
    line_map = {}

    for row in rows:
        quantity = integer(
            row["quantity"],
            "order_line.quantity"
        )

        if quantity <= 0:
            raise ValueError(
                f"Order line {row['order_line_id']} has invalid quantity."
            )

        line = OrderLine(
            order_id=order_map[row["order_id"]],
            sku_id=sku_map[row["sku_id"]],
            quantity=quantity,
            unit_price=decimal_value(
                row["unit_price"],
                "order_line.unit_price"
            ),
            allocated_quantity=quantity,
        )

        db.session.add(line)
        db.session.flush()

        line_map[row["order_line_id"]] = line.id

    return line_map


# --------------------------------------------------
# RESERVATION IMPORT
# --------------------------------------------------

def import_reservations(
    rows,
    order_map,
    sku_map,
    location_map,
    source_order_lines,
    line_map,
):
    line_lookup = {}

    for source_line in source_order_lines:
        key = (
            source_line["order_id"],
            source_line["sku_id"],
        )

        line_lookup.setdefault(key, []).append(
            line_map[source_line["order_line_id"]]
        )

    used_lines = {}

    status_map = {
        "active": "active",
        "consumed": "consumed",
        "released": "released",
        "expired": "expired",
    }

    for row in rows:
        key = (row["order_id"], row["sku_id"])
        possible_lines = line_lookup.get(key, [])

        if not possible_lines:
            raise ValueError(
                f"Reservation {row['reservation_id']} "
                "has no matching order line."
            )

        used_count = used_lines.get(key, 0)

        if used_count >= len(possible_lines):
            raise ValueError(
                f"Too many reservations for order/SKU pair {key}."
            )

        order_line_id = possible_lines[used_count]
        used_lines[key] = used_count + 1

        source_status = normalized(row["reservation_status"])

        if source_status not in status_map:
            raise ValueError(
                f"Unsupported reservation status: {source_status}"
            )

        quantity = integer(
            row["quantity"],
            "reservation.quantity"
        )

        if quantity <= 0:
            raise ValueError(
                f"Reservation {row['reservation_id']} has invalid quantity."
            )

        reservation = Reservation(
            reservation_code=row["reservation_id"],
            order_id=order_map[row["order_id"]],
            order_line_id=order_line_id,
            sku_id=sku_map[row["sku_id"]],
            location_id=location_map[row["location_id"]],
            quantity=quantity,
            status=status_map[source_status],
            created_at=parse_datetime(
                row["reserved_at"],
                "reservation.reserved_at"
            ),
            expires_at=parse_datetime(
                row["expires_at"],
                "reservation.expires_at"
            ),
            closed_at=parse_datetime(
                row["released_at"],
                "reservation.released_at",
                required=False,
            ),
        )

        db.session.add(reservation)


# --------------------------------------------------
# SHIPMENT IMPORT
# --------------------------------------------------

def import_shipments(rows, order_map, location_map):
    for row in rows:
        status = normalized(row["shipment_status"])

        shipment = Shipment(
            shipment_code=row["shipment_id"],
            order_id=order_map[row["order_id"]],
            origin_location_id=location_map[row["location_id"]],
            destination_location_id=None,
            status=status,
            carrier=row["carrier"] or None,
            tracking_number=row["tracking_number"] or None,
            shipped_at=parse_datetime(
                row["shipped_at"],
                "shipment.shipped_at",
                required=False,
            ),
            delivered_at=parse_datetime(
                row["delivered_at"],
                "shipment.delivered_at",
                required=False,
            ),
        )

        db.session.add(shipment)


# --------------------------------------------------
# REPLENISHMENT RULE IMPORT
# --------------------------------------------------

def import_replenishment_rules(rows, sku_map, location_map):
    for row in rows:
        reorder_point = integer(
            row["reorder_point"],
            "rule.reorder_point"
        )

        reorder_quantity = integer(
            row["reorder_quantity"],
            "rule.reorder_quantity"
        )

        safety_stock = integer(
            row["safety_stock"],
            "rule.safety_stock"
        )

        lead_time = integer(
            row["lead_time_days"],
            "rule.lead_time_days"
        )

        if min(reorder_point, reorder_quantity, safety_stock, lead_time) < 0:
            raise ValueError(
                f"Negative replenishment value in {row['rule_id']}."
            )

        rule = ReplenishmentRule(
            sku_id=sku_map[row["sku_id"]],
            location_id=location_map[row["location_id"]],
            min_stock=safety_stock,
            reorder_point=reorder_point,
            target_stock=reorder_point + reorder_quantity,
            reorder_quantity=reorder_quantity,
            safety_stock=safety_stock,
            lead_time_days=lead_time,
            allow_inbound_atp=False,
            active=boolean_value(
                row["is_active"],
                "rule.is_active"
            ),
            effective_from=datetime(2025, 1, 1),
            effective_to=None,
        )

        db.session.add(rule)


# --------------------------------------------------
# CHANNEL BUFFER IMPORT
# --------------------------------------------------

def import_channel_buffers(rows, sku_map):
    for row in rows:
        quantity = integer(
            row["buffer_quantity"],
            "channel_buffer.buffer_quantity"
        )

        if quantity < 0:
            raise ValueError(
                f"Negative channel buffer in {row['buffer_id']}."
            )

        buffer = ChannelBuffer(
            buffer_code=row["buffer_id"],
            sku_id=sku_map[row["sku_id"]],
            channel=normalized(row["channel"]),
            buffer_quantity=quantity,
            active=boolean_value(
                row["is_active"],
                "channel_buffer.is_active"
            ),
        )

        db.session.add(buffer)


# --------------------------------------------------
# REPORTING
# --------------------------------------------------

def print_source_counts(data):
    print("\nSOURCE CSV ROW COUNTS")
    print("-" * 45)

    for name, rows in data.items():
        print(f"{name:25} {len(rows):>10,}")


def print_database_counts():
    print("\nDATABASE IMPORT COUNTS")
    print("-" * 45)

    for model in MODELS:
        count = db.session.query(model).count()
        print(
            f"{model.__tablename__:25} {count:>10,}"
        )


# --------------------------------------------------
# MAIN IMPORT FUNCTION
# --------------------------------------------------

def run_import():
    print("\nSTOCKSYNC DATABASE IMPORT")
    print("=" * 45)

    validate_required_files()

    data = load_source_data()
    validate_source_relationships(data)

    print_source_counts(data)

    DATABASE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    absolute_path = DATABASE_PATH.resolve().as_posix()
    database_uri = "sqlite:///" + absolute_path

    print("\nImport destination:")
    print(DATABASE_PATH)

    app = create_app({
        "SQLALCHEMY_DATABASE_URI": database_uri,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "TESTING": True,
    })

    with app.app_context():
        ensure_database_is_empty()

        db.create_all()

        try:
            # 1. Master data
            product_map, product_cost_map = import_products(
                data["products"]
            )

            sku_map = import_skus(
                data["skus"],
                product_map,
                product_cost_map,
            )

            location_map = import_locations(
                data["locations"]
            )

            # 2. Inventory data
            import_balances(
                data["inventory_balances"],
                sku_map,
                location_map,
            )

            import_movements(
                data["inventory_movements"],
                sku_map,
                location_map,
            )

            # 3. Orders and order lines
            order_map = import_orders(
                data["orders"],
                location_map,
            )

            line_map = import_order_lines(
                data["order_lines"],
                order_map,
                sku_map,
            )

            # 4. Reservations
            import_reservations(
                data["reservations"],
                order_map,
                sku_map,
                location_map,
                data["order_lines"],
                line_map,
            )

            # 5. Shipments
            import_shipments(
                data["shipments"],
                order_map,
                location_map,
            )

            # 6. Replenishment rules
            import_replenishment_rules(
                data["replenishment_rules"],
                sku_map,
                location_map,
            )

            # 7. Channel buffers
            import_channel_buffers(
                data["channel_buffers"],
                sku_map,
            )

            # Commit all imported records together.
            db.session.commit()

        except Exception:
            db.session.rollback()
            raise

        print_database_counts()

        print("\nIMPORT COMPLETED SUCCESSFULLY")
        print("=" * 45)
        print(f"Database: {DATABASE_PATH}")


if __name__ == "__main__":
    try:
        run_import()

    except Exception as error:
        print("\nIMPORT FAILED")
        print("-" * 45)
        print(f"{type(error).__name__}: {error}")
        raise

from datetime import datetime
from decimal import Decimal

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models import (
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
)
from ..services.inventory import (
    InventoryError,
    post_movement,
    available_to_promise,
    expire_reservations,
    replenishment_recommendations,
    reconcile_balance,
)
from ..services.orders import (
    create_order,
    release_order,
    fulfill_order,
)
from ..services.transfers import (
    create_transfer,
    receive_transfer,
    list_transfers,
)

api_bp = Blueprint("api", __name__)


# --------------------------------------------------
# Common helpers
# --------------------------------------------------

def serialize(value):
    """Convert dates and Decimal values into JSON-safe values."""
    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    return value


def success(data=None, message="Success", status=200):
    return jsonify({
        "success": True,
        "message": message,
        "data": data
    }), status


def error(message, status=400):
    return jsonify({
        "success": False,
        "error": str(message)
    }), status


def get_json():
    return request.get_json(silent=True) or {}


def get_int(data, field, required=True):
    value = data.get(field)

    if value is None or value == "":
        if required:
            raise ValueError(f"{field} is required")
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be an integer")


def get_positive_number(data, field):
    value = data.get(field)

    if value is None:
        raise ValueError(f"{field} is required")

    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number")

    if number <= 0:
        raise ValueError(f"{field} must be greater than zero")

    return number


def commit_or_error():
    try:
        db.session.commit()
        return None
    except Exception as exc:
        db.session.rollback()
        return error(str(exc), 400)


# --------------------------------------------------
# Dashboard summary
# --------------------------------------------------

@api_bp.get("/summary")
def summary():
    try:
        return success({
            "products": Product.query.count(),
            "skus": SKU.query.count(),
            "locations": Location.query.count(),
            "orders": CustomerOrder.query.count(),
            "movements": InventoryMovement.query.count(),
            "reservations": Reservation.query.count(),
            "shipments": Shipment.query.count(),
            "inventory_records": InventoryBalance.query.count(),
            "total_on_hand": db.session.query(
                func.coalesce(func.sum(InventoryBalance.on_hand), 0)
            ).scalar(),
            "total_reserved": db.session.query(
                func.coalesce(func.sum(InventoryBalance.reserved), 0)
            ).scalar(),
            "total_blocked": db.session.query(
                func.coalesce(func.sum(InventoryBalance.blocked), 0)
            ).scalar(),
            "total_in_transit": db.session.query(
                func.coalesce(func.sum(InventoryBalance.in_transit), 0)
            ).scalar(),
        })
    except Exception as exc:
        return error(exc, 500)


# --------------------------------------------------
# Products
# --------------------------------------------------

@api_bp.get("/products")
def get_products():
    products = Product.query.order_by(Product.id).all()

    return success([
        {
            "id": p.id,
            "product_code": p.product_code,
            "name": p.name,
            "category": p.category,
            "brand": p.brand,
            "active": p.active,
        }
        for p in products
    ])


@api_bp.post("/products")
def add_product():
    data = get_json()

    try:
        product_code = str(data.get("product_code", "")).strip()
        name = str(data.get("name", "")).strip()

        if not product_code or not name:
            raise ValueError("product_code and name are required")

        if Product.query.filter_by(product_code=product_code).first():
            raise ValueError("Product code already exists")

        product = Product(
            product_code=product_code,
            name=name,
            category=data.get("category"),
            brand=data.get("brand"),
            active=bool(data.get("active", True)),
        )

        db.session.add(product)
        db.session.commit()

        return success({
            "id": product.id,
            "product_code": product.product_code,
            "name": product.name,
        }, "Product created", 201)

    except ValueError as exc:
        db.session.rollback()
        return error(exc)
    except Exception as exc:
        db.session.rollback()
        return error(exc)


# --------------------------------------------------
# SKUs
# --------------------------------------------------

@api_bp.get("/skus")
def get_skus():
    skus = SKU.query.order_by(SKU.id).all()

    return success([
        {
            "id": s.id,
            "sku_code": s.sku_code,
            "product_id": s.product_id,
            "description": s.description,
            "unit_of_measure": s.unit_of_measure,
            "unit_cost": serialize(s.unit_cost),
            "active": s.active,
        }
        for s in skus
    ])


@api_bp.post("/skus")
def add_sku():
    data = get_json()

    try:
        sku_code = str(data.get("sku_code", "")).strip()
        product_id = get_int(data, "product_id")

        if not sku_code:
            raise ValueError("sku_code is required")

        if SKU.query.filter_by(sku_code=sku_code).first():
            raise ValueError("SKU code already exists")

        if not Product.query.get(product_id):
            raise ValueError("Product does not exist")

        unit_cost = float(data.get("unit_cost", 0))

        if unit_cost < 0:
            raise ValueError("unit_cost cannot be negative")

        sku = SKU(
            sku_code=sku_code,
            product_id=product_id,
            description=data.get("description"),
            unit_of_measure=data.get("unit_of_measure", "each"),
            unit_cost=unit_cost,
            active=bool(data.get("active", True)),
        )

        db.session.add(sku)
        db.session.commit()

        return success({
            "id": sku.id,
            "sku_code": sku.sku_code,
            "product_id": sku.product_id,
        }, "SKU created", 201)

    except ValueError as exc:
        db.session.rollback()
        return error(exc)
    except Exception as exc:
        db.session.rollback()
        return error(exc)


# --------------------------------------------------
# Locations
# --------------------------------------------------

@api_bp.get("/locations")
def get_locations():
    locations = Location.query.order_by(Location.id).all()

    return success([
        {
            "id": loc.id,
            "location_code": loc.location_code,
            "name": loc.name,
            "location_type": loc.location_type,
            "channel": loc.channel,
            "parent_id": loc.parent_id,
            "active": loc.active,
        }
        for loc in locations
    ])


@api_bp.post("/locations")
def add_location():
    data = get_json()

    try:
        location_code = str(data.get("location_code", "")).strip()
        name = str(data.get("name", "")).strip()

        if not location_code or not name:
            raise ValueError("location_code and name are required")

        if Location.query.filter_by(location_code=location_code).first():
            raise ValueError("Location code already exists")

        parent_id = get_int(data, "parent_id", required=False)

        if parent_id is not None and not Location.query.get(parent_id):
            raise ValueError("Parent location does not exist")

        location = Location(
            location_code=location_code,
            name=name,
            location_type=data.get("location_type", "warehouse"),
            channel=data.get("channel"),
            parent_id=parent_id,
            active=bool(data.get("active", True)),
        )

        db.session.add(location)
        db.session.commit()

        return success({
            "id": location.id,
            "location_code": location.location_code,
            "name": location.name,
        }, "Location created", 201)

    except ValueError as exc:
        db.session.rollback()
        return error(exc)
    except Exception as exc:
        db.session.rollback()
        return error(exc)


# --------------------------------------------------
# Inventory balances
# --------------------------------------------------

@api_bp.get("/inventory")
def get_inventory():
    rows = InventoryBalance.query.order_by(
        InventoryBalance.id
    ).all()

    result = []

    for row in rows:
        atp = available_to_promise(row.sku_id, row.location_id)

        result.append({
            "id": row.id,
            "sku_id": row.sku_id,
            "location_id": row.location_id,
            "on_hand": row.on_hand,
            "reserved": row.reserved,
            "blocked": row.blocked,
            "in_transit": row.in_transit,
            "safety_stock": row.safety_stock,
            "available_to_promise": atp,
            "updated_at": serialize(row.updated_at),
        })

    return success(result)


# --------------------------------------------------
# Inventory movements
# --------------------------------------------------

@api_bp.get("/movements")
def get_movements():
    limit = request.args.get("limit", 100, type=int)
    limit = max(1, min(limit, 1000))

    rows = InventoryMovement.query.order_by(
        InventoryMovement.id.desc()
    ).limit(limit).all()

    return success([
        {
            "id": m.id,
            "movement_code": m.movement_code,
            "sku_id": m.sku_id,
            "from_location_id": m.from_location_id,
            "to_location_id": m.to_location_id,
            "movement_type": m.movement_type,
            "quantity": m.quantity,
            "reference_type": m.reference_type,
            "reference_id": m.reference_id,
            "occurred_at": serialize(m.occurred_at),
            "note": m.note,
        }
        for m in rows
    ])


@api_bp.post("/movements")
def add_movement():
    data = get_json()

    try:
        movement_type = str(data.get("movement_type", "")).strip()
        sku_id = get_int(data, "sku_id")
        quantity = get_positive_number(data, "quantity")

        from_location_id = get_int(
            data, "from_location_id", required=False
        )
        to_location_id = get_int(
            data, "to_location_id", required=False
        )

        result = post_movement(
            movement_type=movement_type,
            sku_id=sku_id,
            quantity=quantity,
            from_location_id=from_location_id,
            to_location_id=to_location_id,
            reference_type=data.get("reference_type"),
            reference_id=data.get("reference_id"),
            note=data.get("note"),
        )

        return success(result, "Movement recorded", 201)

    except (ValueError, InventoryError) as exc:
        db.session.rollback()
        return error(exc)
    except Exception as exc:
        db.session.rollback()
        return error(exc)


# --------------------------------------------------
# Orders
# --------------------------------------------------

@api_bp.get("/orders")
def get_orders():
    orders = CustomerOrder.query.order_by(
        CustomerOrder.id.desc()
    ).all()

    result = []

    for order in orders:
        result.append({
            "id": order.id,
            "order_code": order.order_code,
            "channel": order.channel,
            "status": order.status,
            "fulfillment_location_id": order.fulfillment_location_id,
            "created_at": serialize(order.created_at),
            "lines": [
                {
                    "id": line.id,
                    "sku_id": line.sku_id,
                    "quantity": line.quantity,
                    "unit_price": serialize(line.unit_price),
                    "allocated_quantity": line.allocated_quantity,
                }
                for line in order.lines
            ],
        })

    return success(result)


@api_bp.post("/orders")
def add_order():
    data = get_json()

    try:
        channel = data.get("channel", "online")
        location_id = get_int(data, "fulfillment_location_id")
        lines = data.get("lines")

        if not isinstance(lines, list) or not lines:
            raise ValueError("At least one order line is required")

        result = create_order(
            channel=channel,
            lines=lines,
            fulfillment_location_id=location_id,
            reservation_minutes=int(data.get("reservation_minutes", 20)),
        )

        return success(result, "Order created and stock reserved", 201)

    except (ValueError, InventoryError, KeyError) as exc:
        db.session.rollback()
        return error(exc)
    except Exception as exc:
        db.session.rollback()
        return error(exc)


@api_bp.post("/orders/<int:order_id>/cancel")
def cancel_order(order_id):
    try:
        result = release_order(order_id)
        return success(result, "Order cancelled and reservations released")
    except (ValueError, InventoryError) as exc:
        db.session.rollback()
        return error(exc)
    except Exception as exc:
        db.session.rollback()
        return error(exc)


@api_bp.post("/orders/<int:order_id>/fulfill")
def fulfill_order_api(order_id):
    try:
        result = fulfill_order(order_id)
        return success(result, "Order fulfilled")
    except (ValueError, InventoryError) as exc:
        db.session.rollback()
        return error(exc)
    except Exception as exc:
        db.session.rollback()
        return error(exc)


# --------------------------------------------------
# Transfers
# --------------------------------------------------

@api_bp.get("/transfers")
def get_transfers():
    try:
        return success(list_transfers())
    except Exception as exc:
        return error(exc, 500)


@api_bp.post("/transfers")
def add_transfer():
    data = get_json()

    try:
        result = create_transfer(
            sku_id=get_int(data, "sku_id"),
            source_location_id=get_int(data, "source_location_id"),
            destination_location_id=get_int(data, "destination_location_id"),
            quantity=get_positive_number(data, "quantity"),
            reference_id=data.get("reference_id"),
            note=data.get("note"),
        )

        return success(result, "Transfer created", 201)

    except (ValueError, InventoryError) as exc:
        db.session.rollback()
        return error(exc)
    except Exception as exc:
        db.session.rollback()
        return error(exc)


@api_bp.post("/transfers/receive")
def receive_transfer_api():
    data = get_json()

    try:
        result = receive_transfer(
            sku_id=get_int(data, "sku_id"),
            source_location_id=get_int(data, "source_location_id"),
            destination_location_id=get_int(data, "destination_location_id"),
            quantity=get_positive_number(data, "quantity"),
            reference_id=data.get("reference_id"),
            note=data.get("note"),
        )

        return success(result, "Transfer received")

    except (ValueError, InventoryError) as exc:
        db.session.rollback()
        return error(exc)
    except Exception as exc:
        db.session.rollback()
        return error(exc)


# --------------------------------------------------
# Reservations
# --------------------------------------------------

@api_bp.get("/reservations")
def get_reservations():
    rows = Reservation.query.order_by(
        Reservation.id.desc()
    ).all()

    return success([
        {
            "id": r.id,
            "reservation_code": r.reservation_code,
            "order_id": r.order_id,
            "order_line_id": r.order_line_id,
            "sku_id": r.sku_id,
            "location_id": r.location_id,
            "quantity": r.quantity,
            "status": r.status,
            "created_at": serialize(r.created_at),
            "expires_at": serialize(r.expires_at),
            "closed_at": serialize(r.closed_at),
        }
        for r in rows
    ])


@api_bp.post("/reservations/expire")
def expire_due_reservations():
    try:
        count = expire_reservations()
        return success({
            "expired_count": count
        }, "Expired reservations processed")
    except Exception as exc:
        db.session.rollback()
        return error(exc)


# --------------------------------------------------
# Replenishment
# --------------------------------------------------

@api_bp.get("/replenishment")
def get_replenishment():
    try:
        return success(replenishment_recommendations())
    except Exception as exc:
        return error(exc, 500)


# --------------------------------------------------
# Reconciliation
# --------------------------------------------------

@api_bp.get("/reconciliation/<int:sku_id>/<int:location_id>")
def inventory_reconciliation(sku_id, location_id):
    try:
        return success(
            reconcile_balance(sku_id, location_id)
        )
    except Exception as exc:
        return error(exc)


# --------------------------------------------------
# Shipments
# --------------------------------------------------

@api_bp.get("/shipments")
def get_shipments():
    shipments = Shipment.query.order_by(
        Shipment.id.desc()
    ).all()

    return success([
        {
            "id": s.id,
            "shipment_code": s.shipment_code,
            "order_id": s.order_id,
            "origin_location_id": s.origin_location_id,
            "destination_location_id": s.destination_location_id,
            "status": s.status,
            "shipped_at": serialize(s.shipped_at),
            "delivered_at": serialize(s.delivered_at),
        }
        for s in shipments
    ])

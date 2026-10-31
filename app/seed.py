
from app.extensions import db
from app.models import Product, SKU, Location, InventoryBalance


def seed_database():
    """Insert a small, safe starter dataset if records do not exist."""

    # -----------------------------
    # Locations
    # -----------------------------

    location_data = [
        {
            "location_code": "LOC-000001",
            "name": "Hyderabad Warehouse",
            "location_type": "warehouse",
            "channel": None,
        },
        {
            "location_code": "LOC-000002",
            "name": "Hyderabad Retail Store",
            "location_type": "store",
            "channel": "store",
        },
        {
            "location_code": "LOC-000003",
            "name": "Online Fulfillment Center",
            "location_type": "warehouse",
            "channel": "online",
        },
    ]

    for item in location_data:
        if not Location.query.filter_by(
            location_code=item["location_code"]
        ).first():
            db.session.add(Location(**item))

    db.session.flush()

    # -----------------------------
    # Products
    # -----------------------------

    product_data = [
        {
            "product_code": "PRD-000001",
            "name": "Wireless Mouse",
            "category": "Electronics",
            "brand": "StockSync Demo",
            "active": True,
        },
        {
            "product_code": "PRD-000002",
            "name": "Mechanical Keyboard",
            "category": "Electronics",
            "brand": "StockSync Demo",
            "active": True,
        },
    ]

    for item in product_data:
        if not Product.query.filter_by(
            product_code=item["product_code"]
        ).first():
            db.session.add(Product(**item))

    db.session.flush()

    # -----------------------------
    # SKUs
    # -----------------------------

    mouse = Product.query.filter_by(
        product_code="PRD-000001"
    ).first()

    keyboard = Product.query.filter_by(
        product_code="PRD-000002"
    ).first()

    sku_data = [
        {
            "sku_code": "SKU-000001",
            "product_id": mouse.id,
            "description": "Wireless Mouse - Black",
            "unit_of_measure": "each",
            "unit_cost": 450.00,
            "active": True,
        },
        {
            "sku_code": "SKU-000002",
            "product_id": keyboard.id,
            "description": "Mechanical Keyboard - Standard",
            "unit_of_measure": "each",
            "unit_cost": 1200.00,
            "active": True,
        },
    ]

    for item in sku_data:
        if not SKU.query.filter_by(
            sku_code=item["sku_code"]
        ).first():
            db.session.add(SKU(**item))

    db.session.flush()

    # -----------------------------
    # Initial inventory balance rows
    # -----------------------------

    locations = Location.query.filter(
        Location.location_code.in_([
            "LOC-000001",
            "LOC-000002",
            "LOC-000003",
        ])
    ).all()

    skus = SKU.query.filter(
        SKU.sku_code.in_([
            "SKU-000001",
            "SKU-000002",
        ])
    ).all()

    for sku in skus:
        for location in locations:
            existing = InventoryBalance.query.filter_by(
                sku_id=sku.id,
                location_id=location.id,
            ).first()

            if not existing:
                db.session.add(
                    InventoryBalance(
                        sku_id=sku.id,
                        location_id=location.id,
                        on_hand=0,
                        reserved=0,
                        blocked=0,
                        in_transit=0,
                        safety_stock=0,
                    )
                )

    db.session.commit()

    return {
        "products": Product.query.count(),
        "skus": SKU.query.count(),
        "locations": Location.query.count(),
        "inventory_balances": InventoryBalance.query.count(),
    }

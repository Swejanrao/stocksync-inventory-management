from datetime import datetime

from .extensions import db


def current_time():
    return datetime.utcnow()


class Product(db.Model):

    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)

    product_code = db.Column(
        db.String(40),
        unique=True,
        nullable=False
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    category = db.Column(
        db.String(80),
        nullable=False
    )

    brand = db.Column(db.String(80))

    active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )
    unit_cost = db.Column(
     db.Numeric(12, 2),
     default=0,
     nullable=False
    )

    created_at = db.Column(
     db.DateTime,
     default=current_time,
     nullable=False
   )

    skus = db.relationship(
        "SKU",
        back_populates="product"
    )


class SKU(db.Model):

    __tablename__ = "skus"

    id = db.Column(db.Integer, primary_key=True)

    sku_code = db.Column(
        db.String(40),
        unique=True,
        nullable=False
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=False
    )

    description = db.Column(db.String(255))

    unit_of_measure = db.Column(
        db.String(20),
        default="each",
        nullable=False
    )

    unit_cost = db.Column(
        db.Numeric(12, 2),
        default=0,
        nullable=False
    )

    active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )
    barcode = db.Column(db.String(50), unique=True, nullable=True)
    weight_kg = db.Column(db.Numeric(10, 3), default=0, nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), default=0, nullable=False)

    created_at = db.Column(
      db.DateTime,
      default=current_time,
      nullable=False
   )
    product = db.relationship(
        "Product",
        back_populates="skus"
    )


class Location(db.Model):

    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)

    location_code = db.Column(
        db.String(40),
        unique=True,
        nullable=False
    )

    name = db.Column(
        db.String(120),
        nullable=False
    )

    location_type = db.Column(
        db.String(30),
        nullable=False
    )

    channel = db.Column(
        db.String(30),
        default="none",
        nullable=False
    )

    parent_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id")
    )

    active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    parent = db.relationship(
        "Location",
        remote_side=[id],
        backref="children"
    )
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    country = db.Column(db.String(100))

    created_at = db.Column(
     db.DateTime,
     default=current_time,
     nullable=False
    )


class InventoryBalance(db.Model):

    __tablename__ = "inventory_balances"

    id = db.Column(db.Integer, primary_key=True)

    sku_id = db.Column(
        db.Integer,
        db.ForeignKey("skus.id"),
        nullable=False
    )

    location_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id"),
        nullable=False
    )

    on_hand = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    reserved = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    blocked = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    in_transit = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    safety_stock = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime,
        default=current_time,
        onupdate=current_time,
        nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint(
            "sku_id",
            "location_id",
            name="uq_inventory_sku_location"
        ),
    )


class InventoryMovement(db.Model):

    __tablename__ = "inventory_movements"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    movement_code = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    sku_id = db.Column(
        db.Integer,
        db.ForeignKey("skus.id"),
        nullable=False
    )

    from_location_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id"),
        nullable=True
    )

    to_location_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id"),
        nullable=True
    )

    movement_type = db.Column(
        db.String(30),
        nullable=False
    )

    quantity = db.Column(
        db.Integer,
        nullable=False
    )

    reference_type = db.Column(db.String(40),nullable=True)

    reference_id = db.Column(db.String(80))

    occurred_at = db.Column(
        db.DateTime,
        default=current_time,
        nullable=False
    )

    note = db.Column(db.String(255),nullable=True)


class CustomerOrder(db.Model):

    __tablename__ = "customer_orders"

    id = db.Column(db.Integer, primary_key=True)

    order_code = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    channel = db.Column(
        db.String(30),
        nullable=False
    )

    status = db.Column(
        db.String(30),
        default="created",
        nullable=False
    )

    fulfillment_location_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=current_time,
        nullable=False
    )
    customer_code = db.Column(db.String(50))
    order_total = db.Column(db.Numeric(14, 2), default=0, nullable=False)

    updated_at = db.Column(
     db.DateTime,
     default=current_time,
     onupdate=current_time,
     nullable=False
  )
    lines = db.relationship(
        "OrderLine",
        back_populates="order",
        cascade="all, delete-orphan"
    )


class OrderLine(db.Model):

    __tablename__ = "order_lines"

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("customer_orders.id"),
        nullable=False
    )

    sku_id = db.Column(
        db.Integer,
        db.ForeignKey("skus.id"),
        nullable=False
    )

    quantity = db.Column(
        db.Integer,
        nullable=False
    )

    unit_price = db.Column(
        db.Numeric(12, 2),
        default=0,
        nullable=False
    )

    allocated_quantity = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    order = db.relationship(
        "CustomerOrder",
        back_populates="lines"
    )


class Reservation(db.Model):

    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)

    reservation_code = db.Column(
        db.String(60),
        unique=True,
        nullable=False
    )

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("customer_orders.id"),
        nullable=False
    )

    order_line_id = db.Column(
        db.Integer,
        db.ForeignKey("order_lines.id"),
        nullable=False
    )

    sku_id = db.Column(
        db.Integer,
        db.ForeignKey("skus.id"),
        nullable=False
    )

    location_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id"),
        nullable=False
    )

    quantity = db.Column(
        db.Integer,
        nullable=False
    )

    status = db.Column(
        db.String(20),
        default="active",
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=current_time,
        nullable=False
    )

    expires_at = db.Column(
        db.DateTime,
        nullable=False
    )

    closed_at = db.Column(db.DateTime)


class Shipment(db.Model):

    __tablename__ = "shipments"

    id = db.Column(db.Integer, primary_key=True)

    shipment_code = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("customer_orders.id"),
        nullable=False
    )

    origin_location_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id"),
        nullable=False
    )

    destination_location_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id")
    )

    status = db.Column(
        db.String(20),
        default="created",
        nullable=False
    )

    shipped_at = db.Column(db.DateTime)

    delivered_at = db.Column(db.DateTime)
    carrier = db.Column(db.String(100))
    tracking_number = db.Column(db.String(100))


class ReplenishmentRule(db.Model):

    __tablename__ = "replenishment_rules"

    id = db.Column(db.Integer, primary_key=True)

    sku_id = db.Column(
        db.Integer,
        db.ForeignKey("skus.id"),
        nullable=False
    )

    location_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id"),
        nullable=False
    )

    min_stock = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    reorder_point = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    target_stock = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    lead_time_days = db.Column(
        db.Integer,
        default=1,
        nullable=False
    )

    allow_inbound_atp = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )
    reorder_quantity = db.Column(
     db.Integer,
     default=0,
     nullable=False
   )

    safety_stock = db.Column(
     db.Integer,
     default=0,
     nullable=False
    )

    active = db.Column(
     db.Boolean,
      default=True,
     nullable=False
   )

    effective_from = db.Column(
        db.DateTime,
        default=current_time,
        nullable=False
    )

    effective_to = db.Column(db.DateTime)


class InventoryEvent(db.Model):

    __tablename__ = "inventory_events"

    id = db.Column(db.Integer, primary_key=True)

    entity_type = db.Column(
        db.String(40),
        nullable=False
    )

    entity_id = db.Column(
        db.String(80),
        nullable=False
    )

    event_type = db.Column(
        db.String(40),
        nullable=False
    )

    old_state = db.Column(db.String(40))

    new_state = db.Column(db.String(40))

    event_at = db.Column(
        db.DateTime,
        default=current_time,
        nullable=False
    )

    details = db.Column(db.JSON)                      
    
class ChannelBuffer(db.Model):

    __tablename__ = "channel_buffers"

    id = db.Column(db.Integer, primary_key=True)

    buffer_code = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    sku_id = db.Column(
        db.Integer,
        db.ForeignKey("skus.id"),
        nullable=False
    )

    channel = db.Column(
        db.String(30),
        nullable=False
    )

    buffer_quantity = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )
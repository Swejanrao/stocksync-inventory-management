from datetime import datetime, timedelta

from ..extensions import db
from ..models import (
    CustomerOrder,
    OrderLine,
    Reservation,
)
from .inventory import (
    InventoryError,
    available_to_promise,
    get_or_create_balance,
    record_event,
    post_movement,
)


def create_order(
    channel,
    lines,
    fulfillment_location_id,
    reservation_minutes=20,
):
    """
    Create an order and reserve its stock.

    Each line must contain:
    {"sku_id": 1, "quantity": 2, "unit_price": 99.99}
    """
    allowed_channels = {"online", "store", "marketplace"}

    if channel not in allowed_channels:
        raise ValueError("Channel must be online, store or marketplace.")

    if not isinstance(lines, list) or not lines:
        raise ValueError("An order must contain at least one line.")

    if reservation_minutes <= 0:
        raise ValueError("Reservation duration must be positive.")

    try:
        now = datetime.utcnow()

        order = CustomerOrder(
            order_code=f"ORD-{now.year}-{CustomerOrder.query.count() + 1:06d}",
            channel=channel,
            status="created",
            fulfillment_location_id=fulfillment_location_id,
            created_at=now,
        )

        db.session.add(order)
        db.session.flush()

        for index, line in enumerate(lines, start=1):
            sku_id = int(line["sku_id"])
            quantity = int(line["quantity"])
            unit_price = float(line.get("unit_price", 0))

            if quantity <= 0:
                raise ValueError("Order quantity must be positive.")

            if unit_price < 0:
                raise ValueError("Unit price cannot be negative.")

            balance = get_or_create_balance(
                sku_id,
                fulfillment_location_id,
                lock=True,
            )

            atp = available_to_promise(
                sku_id,
                fulfillment_location_id,
            )

            if atp < quantity:
                raise InventoryError(
                    f"Insufficient ATP for SKU {sku_id}. "
                    f"Requested {quantity}; available {atp}."
                )

            order_line = OrderLine(
                order_id=order.id,
                sku_id=sku_id,
                quantity=quantity,
                unit_price=unit_price,
                allocated_quantity=quantity,
            )

            db.session.add(order_line)
            db.session.flush()

            balance.reserved += quantity

            reservation = Reservation(
                reservation_code=f"RES-{order.id}-{index:02d}",
                order_id=order.id,
                order_line_id=order_line.id,
                sku_id=sku_id,
                location_id=fulfillment_location_id,
                quantity=quantity,
                status="active",
                created_at=now,
                expires_at=now + timedelta(
                    minutes=reservation_minutes
                ),
            )

            db.session.add(reservation)

            record_event(
                "reservation",
                reservation.reservation_code,
                "reservation_created",
                new_state="active",
                details={"quantity": quantity},
            )

        order.status = "reserved"

        record_event(
            "order",
            order.order_code,
            "order_reserved",
            old_state="created",
            new_state="reserved",
        )

        db.session.commit()
        return order

    except Exception:
        db.session.rollback()
        raise


def release_order(order_id):
    """Cancel an order and release its active reservations."""
    try:
        order = CustomerOrder.query.get(order_id)

        if order is None:
            raise ValueError("Order not found.")

        if order.status in {"cancelled", "completed", "shipped"}:
            raise ValueError(
                f"Order cannot be cancelled from status {order.status}."
            )

        active_reservations = Reservation.query.filter_by(
            order_id=order.id,
            status="active",
        ).with_for_update().all()

        now = datetime.utcnow()

        for reservation in active_reservations:
            balance = get_or_create_balance(
                reservation.sku_id,
                reservation.location_id,
                lock=True,
            )

            if balance.reserved < reservation.quantity:
                raise InventoryError(
                    "Reserved quantity is inconsistent; cancellation stopped."
                )

            balance.reserved -= reservation.quantity

            old_status = reservation.status
            reservation.status = "released"
            reservation.closed_at = now

            record_event(
                "reservation",
                reservation.reservation_code,
                "reservation_released",
                old_state=old_status,
                new_state="released",
            )

        old_order_status = order.status
        order.status = "cancelled"

        record_event(
            "order",
            order.order_code,
            "order_cancelled",
            old_state=old_order_status,
            new_state="cancelled",
        )

        db.session.commit()
        return order

    except Exception:
        db.session.rollback()
        raise


def fulfill_order(order_id):
    """Consume reservations and post sale movements for a reserved order."""
    try:
        order = CustomerOrder.query.get(order_id)

        if order is None:
            raise ValueError("Order not found.")

        if order.status != "reserved":
            raise ValueError("Only reserved orders can be fulfilled.")

        reservations = Reservation.query.filter_by(
            order_id=order.id,
            status="active",
        ).with_for_update().all()

        if not reservations:
            raise InventoryError("No active reservations found.")

        now = datetime.utcnow()

        for reservation in reservations:
            if reservation.expires_at <= now:
                raise InventoryError(
                    f"Reservation {reservation.reservation_code} has expired."
                )

            balance = get_or_create_balance(
                reservation.sku_id,
                reservation.location_id,
                lock=True,
            )

            if balance.reserved < reservation.quantity:
                raise InventoryError("Reserved stock is inconsistent.")

            if balance.on_hand - balance.blocked < reservation.quantity:
                raise InventoryError(
                    "Insufficient unblocked stock to fulfil order."
                )

            balance.reserved -= reservation.quantity

            post_movement(
                sku_id=reservation.sku_id,
                quantity=reservation.quantity,
                movement_type="sale",
                from_location_id=reservation.location_id,
                reference_type="order",
                reference_id=order.order_code,
                note="Order fulfilment",
            )

            old_status = reservation.status
            reservation.status = "consumed"
            reservation.closed_at = now

            record_event(
                "reservation",
                reservation.reservation_code,
                "reservation_consumed",
                old_state=old_status,
                new_state="consumed",
            )

        old_order_status = order.status
        order.status = "completed"

        record_event(
            "order",
            order.order_code,
            "order_fulfilled",
            old_state=old_order_status,
            new_state="completed",
        )

        db.session.commit()
        return order

    except Exception:
        db.session.rollback()
        raise


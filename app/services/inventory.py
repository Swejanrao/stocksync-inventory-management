from datetime import datetime
from uuid import uuid4

from sqlalchemy import func

from ..extensions import db
from ..models import (
    InventoryBalance,
    InventoryMovement,
    InventoryEvent,
    Reservation,
    ReplenishmentRule,
)


class InventoryError(Exception):
    """Raised when an inventory operation violates a business rule."""


MOVEMENT_TYPES = {
    "opening",
    "receipt",
    "sale",
    "return",
    "transfer_out",
    "transfer_in",
    "adjustment_in",
    "adjustment_out",
    "damage",
}


def record_event(entity_type, entity_id, event_type,
                 old_state=None, new_state=None, details=None):
    event = InventoryEvent(
        entity_type=entity_type,
        entity_id=str(entity_id),
        event_type=event_type,
        old_state=old_state,
        new_state=new_state,
        details=details or {},
    )
    db.session.add(event)
    return event


def get_balance(sku_id, location_id, lock=False):
    query = InventoryBalance.query.filter_by(
        sku_id=sku_id,
        location_id=location_id,
    )

    if lock:
        query = query.with_for_update()

    return query.first()


def get_or_create_balance(sku_id, location_id, lock=False):
    balance = get_balance(sku_id, location_id, lock=lock)

    if balance is None:
        balance = InventoryBalance(
            sku_id=sku_id,
            location_id=location_id,
            on_hand=0,
            reserved=0,
            blocked=0,
            in_transit=0,
            safety_stock=0,
        )
        db.session.add(balance)
        db.session.flush()

    return balance


def available_to_promise(sku_id, location_id, include_inbound=None):
    balance = get_balance(sku_id, location_id)

    if balance is None:
        return 0

    if include_inbound is None:
        rule = (
            ReplenishmentRule.query
            .filter_by(sku_id=sku_id, location_id=location_id)
            .filter(ReplenishmentRule.effective_from <= datetime.utcnow())
            .filter(
                db.or_(
                    ReplenishmentRule.effective_to.is_(None),
                    ReplenishmentRule.effective_to > datetime.utcnow(),
                )
            )
            .order_by(ReplenishmentRule.effective_from.desc())
            .first()
        )
        include_inbound = bool(rule and rule.allow_inbound_atp)

    inbound = balance.in_transit if include_inbound else 0

    return max(
        0,
        balance.on_hand
        - balance.reserved
        - balance.blocked
        - balance.safety_stock
        + inbound,
    )



def generate_movement_code():
    last_id = db.session.query(
        db.func.max(InventoryMovement.id)
    ).scalar() or 0

    next_number = int(last_id) + 1

    return f"MOV-{datetime.utcnow().year}-{next_number:08d}"


def post_movement(
    sku_id,
    quantity,
    movement_type,
    from_location_id=None,
    to_location_id=None,
    reference_type=None,
    reference_id=None,
    note=None,
    movement_code=None,
    occurred_at=None,
):
    """
    Post one immutable inventory movement and update the current balance.

    A movement is never edited to represent a later event. Corrections
    should be recorded as additional movements.
    """
    if movement_type not in MOVEMENT_TYPES:
        raise InventoryError("Unsupported movement type.")

    if not isinstance(quantity, int) or quantity <= 0:
        raise InventoryError("Quantity must be a positive whole number.")

    try:
        if movement_type in {"opening", "receipt", "return"}:
            if not to_location_id:
                raise InventoryError("Destination location is required.")

            destination = get_or_create_balance(
                sku_id, to_location_id, lock=True
            )
            destination.on_hand += quantity

        elif movement_type == "sale":
            if not from_location_id:
                raise InventoryError("Source location is required.")

            source = get_or_create_balance(
                sku_id, from_location_id, lock=True
            )

            if source.on_hand - source.blocked < quantity:
                raise InventoryError("Insufficient unblocked physical stock.")

            source.on_hand -= quantity

        elif movement_type == "transfer_out":
            if not from_location_id or not to_location_id:
                raise InventoryError("Both transfer locations are required.")

            if from_location_id == to_location_id:
                raise InventoryError("Transfer locations must be different.")

            if not reference_id:
                raise InventoryError("A transfer reference ID is required.")

            source = get_or_create_balance(
                sku_id, from_location_id, lock=True
            )
            destination = get_or_create_balance(
                sku_id, to_location_id, lock=True
            )

            if source.on_hand - source.blocked < quantity:
                raise InventoryError("Insufficient unblocked stock to transfer.")

            source.on_hand -= quantity
            destination.in_transit += quantity

        elif movement_type == "transfer_in":
            if not from_location_id or not to_location_id:
                raise InventoryError("Both transfer locations are required.")

            if from_location_id == to_location_id:
                raise InventoryError("Transfer locations must be different.")

            if not reference_id:
                raise InventoryError("A transfer reference ID is required.")

            source = get_or_create_balance(
                sku_id, from_location_id, lock=True
            )
            destination = get_or_create_balance(
                sku_id, to_location_id, lock=True
            )

            sent = (
                db.session.query(func.coalesce(func.sum(
                    InventoryMovement.quantity
                ), 0))
                .filter_by(
                    sku_id=sku_id,
                    from_location_id=from_location_id,
                    to_location_id=to_location_id,
                    movement_type="transfer_out",
                    reference_type="transfer",
                    reference_id=str(reference_id),
                )
                .scalar()
            )

            received = (
                db.session.query(func.coalesce(func.sum(
                    InventoryMovement.quantity
                ), 0))
                .filter_by(
                    sku_id=sku_id,
                    from_location_id=from_location_id,
                    to_location_id=to_location_id,
                    movement_type="transfer_in",
                    reference_type="transfer",
                    reference_id=str(reference_id),
                )
                .scalar()
            )

            outstanding = sent - received

            if outstanding < quantity:
                raise InventoryError(
                    "Receipt exceeds the outstanding transfer quantity."
                )

            if destination.in_transit < quantity:
                raise InventoryError(
                    "Destination in-transit balance is insufficient."
                )

            destination.in_transit -= quantity
            destination.on_hand += quantity

        elif movement_type == "adjustment_in":
            if not to_location_id:
                raise InventoryError("Destination location is required.")

            destination = get_or_create_balance(
                sku_id, to_location_id, lock=True
            )
            destination.on_hand += quantity

        elif movement_type == "adjustment_out":
            if not from_location_id:
                raise InventoryError("Source location is required.")

            source = get_or_create_balance(
                sku_id, from_location_id, lock=True
            )

            if source.on_hand - source.blocked < quantity:
                raise InventoryError("Adjustment exceeds unblocked stock.")

            source.on_hand -= quantity

        elif movement_type == "damage":
            if not from_location_id:
                raise InventoryError("Location is required for damaged stock.")

            source = get_or_create_balance(
                sku_id, from_location_id, lock=True
            )

            available_unblocked = source.on_hand - source.blocked

            if available_unblocked < quantity:
                raise InventoryError("Damage quantity exceeds unblocked stock.")

            source.blocked += quantity

        movement = InventoryMovement(
            movement_code=movement_code or generate_movement_code(),
            sku_id=sku_id,
            from_location_id=from_location_id,
            to_location_id=to_location_id,
            movement_type=movement_type,
            quantity=quantity,
            reference_type=reference_type,
            reference_id=str(reference_id) if reference_id is not None else None,
            occurred_at=occurred_at or datetime.utcnow(),
            note=note,
        )

        db.session.add(movement)
        db.session.flush()

        record_event(
            "inventory_movement",
            movement.movement_code,
            "movement_posted",
            details={
                "sku_id": sku_id,
                "movement_type": movement_type,
                "quantity": quantity,
            },
        )

        db.session.flush()
        return movement

    except Exception:
        db.session.rollback()
        raise


def expire_reservations(now=None):
    """Expire due active reservations and release their reserved quantities."""
    now = now or datetime.utcnow()

    expired = (
        Reservation.query
        .filter(
            Reservation.status == "active",
            Reservation.expires_at <= now,
        )
        .with_for_update()
        .all()
    )

    for reservation in expired:
        balance = get_balance(
            reservation.sku_id,
            reservation.location_id,
            lock=True,
        )

        if balance is None or balance.reserved < reservation.quantity:
            raise InventoryError(
                f"Cannot release reservation {reservation.reservation_code}: "
                "reserved balance is inconsistent."
            )

        balance.reserved -= reservation.quantity
        old_status = reservation.status
        reservation.status = "expired"
        reservation.closed_at = now

        record_event(
            "reservation",
            reservation.reservation_code,
            "reservation_expired",
            old_state=old_status,
            new_state="expired",
            details={"quantity": reservation.quantity},
        )

    db.session.commit()
    return len(expired)


def replenishment_recommendations():
    now = datetime.utcnow()

    rules = (
        ReplenishmentRule.query
        .filter(ReplenishmentRule.effective_from <= now)
        .filter(
            db.or_(
                ReplenishmentRule.effective_to.is_(None),
                ReplenishmentRule.effective_to > now,
            )
        )
        .all()
    )

    recommendations = []

    for rule in rules:
        balance = get_balance(rule.sku_id, rule.location_id)

        on_hand = balance.on_hand if balance else 0
        reserved = balance.reserved if balance else 0
        blocked = balance.blocked if balance else 0
        safety = balance.safety_stock if balance else 0
        inbound = balance.in_transit if balance else 0

        atp = available_to_promise(
            rule.sku_id,
            rule.location_id,
        )

        if atp <= rule.reorder_point:
            effective_supply = (
                on_hand - reserved - blocked - safety
                + (inbound if rule.allow_inbound_atp else 0)
            )

            recommendations.append({
                "sku_id": rule.sku_id,
                "location_id": rule.location_id,
                "available_to_promise": atp,
                "reorder_point": rule.reorder_point,
                "target_stock": rule.target_stock,
                "suggested_quantity": max(
                    0, rule.target_stock - effective_supply
                ),
                "lead_time_days": rule.lead_time_days,
            })

    return recommendations


def reconcile_balance(sku_id, location_id):
    """
    Reconstruct expected on-hand from the movement ledger.

    Opening, receipt, return, adjustment_in and transfer_in increase stock.
    Sale, adjustment_out and transfer_out decrease stock.
    Damage blocks stock but does not remove it from on-hand.
    """
    movements = InventoryMovement.query.filter(
        InventoryMovement.sku_id == sku_id,
        db.or_(
            InventoryMovement.from_location_id == location_id,
            InventoryMovement.to_location_id == location_id,
        ),
    ).order_by(
        InventoryMovement.occurred_at,
        InventoryMovement.id,
    ).all()

    expected = 0

    increases = {
        "opening",
        "receipt",
        "return",
        "adjustment_in",
        "transfer_in",
    }

    decreases = {
        "sale",
        "adjustment_out",
        "transfer_out",
    }

    for movement in movements:
        if movement.movement_type in increases:
            if movement.to_location_id == location_id:
                expected += movement.quantity

        elif movement.movement_type in decreases:
            if movement.from_location_id == location_id:
                expected -= movement.quantity

    balance = get_balance(sku_id, location_id)
    actual = balance.on_hand if balance else 0

    return {
        "sku_id": sku_id,
        "location_id": location_id,
        "expected_on_hand": expected,
        "actual_on_hand": actual,
        "difference": actual - expected,
        "reconciled": actual == expected,
    }


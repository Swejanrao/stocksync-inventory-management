
from uuid import uuid4

from ..extensions import db
from ..models import InventoryMovement
from .inventory import InventoryError, post_movement


def create_transfer(sku_id, source_location_id, destination_location_id,
                    quantity, reference_id=None, note=None):
    if source_location_id == destination_location_id:
        raise ValueError("Source and destination must be different.")

    transfer_id = str(reference_id or f"TRF-{uuid4().hex[:12].upper()}")

    try:
        movement = post_movement(
            sku_id=sku_id,
            quantity=int(quantity),
            movement_type="transfer_out",
            from_location_id=source_location_id,
            to_location_id=destination_location_id,
            reference_type="transfer",
            reference_id=transfer_id,
            note=note or "Stock transfer dispatched",
        )
        db.session.commit()
        return {
            "transfer_id": transfer_id,
            "movement_code": movement.movement_code,
            "status": "in_transit",
        }
    except Exception:
        db.session.rollback()
        raise


def receive_transfer(sku_id, source_location_id, destination_location_id,
                     quantity, transfer_id, note=None):
    if not transfer_id:
        raise ValueError("Transfer ID is required.")

    try:
        movement = post_movement(
            sku_id=sku_id,
            quantity=int(quantity),
            movement_type="transfer_in",
            from_location_id=source_location_id,
            to_location_id=destination_location_id,
            reference_type="transfer",
            reference_id=str(transfer_id),
            note=note or "Stock transfer received",
        )
        db.session.commit()
        return {
            "transfer_id": str(transfer_id),
            "movement_code": movement.movement_code,
            "status": "received",
        }
    except Exception:
        db.session.rollback()
        raise


def list_transfers():
    sent = InventoryMovement.query.filter_by(
        movement_type="transfer_out",
        reference_type="transfer",
    ).order_by(InventoryMovement.occurred_at.desc()).all()

    results = []

    for movement in sent:
        received_quantity = sum(
            row.quantity
            for row in InventoryMovement.query.filter_by(
                movement_type="transfer_in",
                reference_type="transfer",
                reference_id=movement.reference_id,
                sku_id=movement.sku_id,
                from_location_id=movement.from_location_id,
                to_location_id=movement.to_location_id,
            ).all()
        )

        remaining = movement.quantity - received_quantity

        if remaining < 0:
            status = "exception"
        elif remaining == 0:
            status = "received"
        elif received_quantity == 0:
            status = "in_transit"
        else:
            status = "partially_received"

        results.append({
            "transfer_id": movement.reference_id,
            "sku_id": movement.sku_id,
            "source_location_id": movement.from_location_id,
            "destination_location_id": movement.to_location_id,
            "sent_quantity": movement.quantity,
            "received_quantity": received_quantity,
            "remaining_quantity": remaining,
            "status": status,
            "dispatched_at": movement.occurred_at.isoformat(),
        })

    return results

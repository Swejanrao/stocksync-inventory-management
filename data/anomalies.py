
import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "generated"


def read_csv(filename):
    path = DATA_DIR / filename

    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def write_csv(filename, rows, fieldnames):
    path = DATA_DIR / filename

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return path


def create_anomalies():
    balances = read_csv("inventory_balances.csv")
    movements = read_csv("inventory_movements.csv")
    orders = read_csv("orders.csv")
    reservations = read_csv("reservations.csv")

    if not balances or not orders or not reservations:
        raise ValueError(
            "Generate the baseline dataset before creating anomalies."
        )

    scenarios = []
    ground_truth = []

    def add_scenario(
        scenario_id,
        anomaly_type,
        entity_type,
        entity_id,
        field_name,
        baseline_value,
        anomalous_value,
        description,
        evidence,
    ):
        scenarios.append({
            "scenario_id": scenario_id,
            "anomaly_type": anomaly_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "field_name": field_name,
            "baseline_value": baseline_value,
            "anomalous_value": anomalous_value,
            "description": description,
            "evidence": evidence,
        })

        ground_truth.append({
            "scenario_id": scenario_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "label": 1,
            "anomaly_type": anomaly_type,
        })

    # -------------------------------------------------
    # 1. Inventory balance does not reconcile to ledger
    # -------------------------------------------------

    balance = balances[0]

    sku_id = balance["sku_id"]
    location_id = balance["location_id"]

    ledger_quantity = 0

    for movement in movements:
        if movement["sku_id"] != sku_id:
            continue

        quantity = int(movement["quantity"])
        movement_type = movement["movement_type"]

        if movement_type in (
            "opening", "receipt", "return", "adjustment_in"
        ):
            if movement.get("to_location_id") == location_id:
                ledger_quantity += quantity

        elif movement_type in (
            "sale", "adjustment_out", "transfer_out"
        ):
            if movement.get("from_location_id") == location_id:
                ledger_quantity -= quantity

        elif movement_type == "transfer_in":
            if movement.get("to_location_id") == location_id:
                ledger_quantity += quantity

    recorded_quantity = int(balance["on_hand"])

    add_scenario(
        "ANOM-001",
        "balance_mismatch",
        "inventory_balance",
        balance["balance_id"],
        "on_hand",
        recorded_quantity,
        recorded_quantity + 25,
        "The recorded on-hand quantity is 25 units higher than the movement ledger.",
        f"Ledger quantity is {ledger_quantity}; baseline recorded quantity is {recorded_quantity}.",
    )

    # -------------------------------------------------
    # 2. Reservation exceeds available stock
    # -------------------------------------------------

    reservation = reservations[0]

    reservation_balance = next(
        (
            row for row in balances
            if row["sku_id"] == reservation["sku_id"]
            and row["location_id"] == reservation["location_id"]
        ),
        None,
    )

    if reservation_balance is None:
        raise ValueError("Could not find the reservation's inventory balance.")

    on_hand = int(reservation_balance["on_hand"])
    blocked = int(reservation_balance["blocked"])
    safety_stock = int(reservation_balance["safety_stock"])
    reserved = int(reservation_balance["reserved"])

    available = max(
        0,
        on_hand - blocked - reserved - safety_stock,
    )

    excessive_reservation = reserved + available + 10

    add_scenario(
        "ANOM-002",
        "reservation_oversell",
        "reservation",
        reservation["reservation_id"],
        "quantity",
        reservation["quantity"],
        excessive_reservation,
        "The reservation quantity is deliberately increased beyond the available stock.",
        f"On hand={on_hand}, blocked={blocked}, reserved={reserved}, safety stock={safety_stock}, available={available}.",
    )

    # -------------------------------------------------
    # 3. Order fulfilled using blocked stock
    # -------------------------------------------------

    blocked_balance = next(
        (row for row in balances if int(row["blocked"]) > 0),
        balances[0],
    )

    order = orders[0]

    blocked_quantity = int(blocked_balance["blocked"])

    # If the selected baseline balance has no blocked stock,
    # this scenario introduces blocked stock in the anomaly overlay.
    if blocked_quantity == 0:
        blocked_quantity = 10

    add_scenario(
        "ANOM-003",
        "blocked_stock_fulfillment",
        "order",
        order["order_id"],
        "fulfillment_stock_source",
        "unblocked_stock",
        "blocked_stock",
        "The order is marked as fulfilled using inventory that is blocked or damaged.",
        f"Related SKU={blocked_balance['sku_id']}; location={blocked_balance['location_id']}; blocked quantity used for scenario={blocked_quantity}.",
    )

    # -------------------------------------------------
    # 4. Transfer counted at both ends prematurely
    # -------------------------------------------------

    transfer_reference = "TRF-ANOM-004"

    add_scenario(
        "ANOM-004",
        "transfer_double_count",
        "inventory_transfer",
        transfer_reference,
        "destination_stock_status",
        "in_transit",
        "received_before_confirmation",
        "The same transferred quantity is counted at the source and destination before receipt is confirmed.",
        "This is a synthetic transfer scenario. The baseline generator does not create transfer records yet.",
    )

    # -------------------------------------------------
    # Save anomaly scenarios and ground truth
    # -------------------------------------------------

    scenario_fields = [
        "scenario_id",
        "anomaly_type",
        "entity_type",
        "entity_id",
        "field_name",
        "baseline_value",
        "anomalous_value",
        "description",
        "evidence",
    ]

    ground_truth_fields = [
        "scenario_id",
        "entity_type",
        "entity_id",
        "label",
        "anomaly_type",
    ]

    scenario_path = write_csv(
        "anomaly_scenarios.csv",
        scenarios,
        scenario_fields,
    )

    ground_truth_path = write_csv(
        "ground_truth.csv",
        ground_truth,
        ground_truth_fields,
    )

    ground_truth_json_path = DATA_DIR / "ground_truth.json"

    with ground_truth_json_path.open("w", encoding="utf-8") as file:
        json.dump(ground_truth, file, indent=4)

    print("\nSTOCKSYNC ANOMALY SCENARIOS")
    print("-" * 40)
    print(f"Scenarios created: {len(scenarios)}")
    print(f"Ground-truth labels: {len(ground_truth)}")
    print(f"Scenario file: {scenario_path}")
    print(f"Ground truth CSV: {ground_truth_path}")
    print(f"Ground truth JSON: {ground_truth_json_path}")
    print("\nBaseline files have not been modified.")


if __name__ == "__main__":
    create_anomalies()

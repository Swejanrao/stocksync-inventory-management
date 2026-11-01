import sqlite3
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "instance" / "stocksync_generated.db"

EXPECTED_COUNTS = {
    "products": 50,
    "skus": 50,
    "locations": 10,
    "inventory_balances": 500,
    "inventory_movements": 1029,
    "customer_orders": 100,
    "order_lines": 84,
    "reservations": 84,
    "shipments": 29,
    "replenishment_rules": 500,
    "channel_buffers": 150,
}

INCOMING_TYPES = {
    "opening",
    "receipt",
    "return",
    "adjustment_in",
    "transfer_in",
}

OUTGOING_TYPES = {
    "sale",
    "adjustment_out",
    "transfer_out",
}


def main():
    print("\nSTOCKSYNC DATABASE VERIFICATION")
    print("=" * 50)

    if not DB_PATH.exists():
        print("ERROR: Generated database was not found.")
        return

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:
        # 1. Verify table row counts
        print("\n1. TABLE ROW COUNTS")
        print("-" * 50)

        count_errors = []

        for table, expected in EXPECTED_COUNTS.items():
            actual = connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]

            status = "PASS" if actual == expected else "FAIL"
            print(f"{table:25} {actual:8}  {status}")

            if actual != expected:
                count_errors.append(
                    f"{table}: expected {expected}, found {actual}"
                )

        # 2. Check foreign keys
        print("\n2. FOREIGN KEY CHECK")
        print("-" * 50)

        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if foreign_key_errors:
            print(f"FAIL: {len(foreign_key_errors)} foreign-key issue(s)")
            for error in foreign_key_errors[:10]:
                print(dict(error))
        else:
            print("PASS: No foreign-key violations found.")

        # 3. Reconcile inventory balances with movement history
        print("\n3. INVENTORY RECONCILIATION")
        print("-" * 50)

        ledger = defaultdict(int)

        movements = connection.execute("""
            SELECT sku_id, from_location_id, to_location_id,
                   movement_type, quantity
            FROM inventory_movements
        """).fetchall()

        for movement in movements:
            sku_id = movement["sku_id"]
            movement_type = movement["movement_type"].lower()
            quantity = int(movement["quantity"])

            if movement_type in INCOMING_TYPES:
                location_id = movement["to_location_id"]
                if location_id:
                    ledger[(sku_id, location_id)] += quantity

            elif movement_type in OUTGOING_TYPES:
                location_id = movement["from_location_id"]
                if location_id:
                    ledger[(sku_id, location_id)] -= quantity

            # Damage is intentionally excluded from on-hand
            # reconciliation because it is tracked as blocked stock.

        balances = connection.execute("""
            SELECT sku_id, location_id, on_hand
            FROM inventory_balances
        """).fetchall()

        reconciliation_errors = []

        for balance in balances:
            key = (balance["sku_id"], balance["location_id"])
            expected_on_hand = ledger[key]
            actual_on_hand = int(balance["on_hand"])

            if expected_on_hand != actual_on_hand:
                reconciliation_errors.append({
                    "sku_id": key[0],
                    "location_id": key[1],
                    "ledger_quantity": expected_on_hand,
                    "balance_quantity": actual_on_hand,
                })

        if reconciliation_errors:
            print(
                f"FAIL: {len(reconciliation_errors)} "
                "balance mismatch(es)"
            )
            for error in reconciliation_errors[:10]:
                print(error)
        else:
            print(
                "PASS: All inventory balances match "
                "their movement history."
            )

        # 4. Final result
        print("\n4. VERIFICATION SUMMARY")
        print("-" * 50)

        if count_errors:
            print("Row count errors:", count_errors)

        print("Foreign-key violations:", len(foreign_key_errors))
        print("Inventory mismatches:", len(reconciliation_errors))

        if (
            not count_errors
            and not foreign_key_errors
            and not reconciliation_errors
        ):
            print("\nALL CHECKS PASSED")
        else:
            print("\nSOME CHECKS NEED ATTENTION")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
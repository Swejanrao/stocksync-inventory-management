# StockSync – Data Dictionary

## Project Overview

StockSync is a unified inventory and availability management system.
It combines product, inventory, order, reservation, movement and
replenishment information.

The baseline dataset contains valid synthetic records. Intentional
anomaly scenarios and their labels are stored separately.

**Random seed:** 20261022

## 1. Master Data

### products.csv

| Column | Description |
|---|---|
| product_id | Unique product identifier |
| product_code | Unique product code |
| name | Product name |
| category | Product category |
| brand | Product brand |

### skus.csv

| Column | Description |
|---|---|
| sku_id | Unique SKU identifier |
| sku_code | Unique SKU code |
| product_id | Parent product identifier |
| description | SKU description |
| unit_of_measure | Unit used for stock quantities |

### locations.csv

| Column | Description |
|---|---|
| location_id | Unique location identifier |
| location_code | Unique location code |
| name | Location name |
| location_type | Store, warehouse or other location type |
| channel | Associated sales channel |

## 2. Inventory Data

### inventory_balances.csv

| Column | Description |
|---|---|
| balance_id | Unique inventory balance identifier |
| sku_id | SKU identifier |
| location_id | Location identifier |
| on_hand | Physical stock recorded at the location |
| reserved | Stock reserved for orders |
| blocked | Damaged or unavailable stock |
| in_transit | Stock moving between locations |
| safety_stock | Minimum stock buffer |

### inventory_movements.csv

| Column | Description |
|---|---|
| movement_id | Unique movement identifier |
| movement_code | Business movement reference |
| sku_id | SKU affected by movement |
| from_location_id | Source location, when applicable |
| to_location_id | Destination location, when applicable |
| movement_type | Type of inventory movement |
| quantity | Quantity moved |
| occurred_at | Movement timestamp |
| note | Additional movement information |

## 3. Order and Reservation Data

### orders.csv

| Column | Description |
|---|---|
| order_id | Unique order identifier |
| order_code | Business order reference |
| channel | Order channel |
| status | Order lifecycle status |
| fulfillment_location_id | Location assigned to fulfill the order |
| created_at | Order creation timestamp |

### order_lines.csv

| Column | Description |
|---|---|
| order_line_id | Unique order line identifier |
| order_id | Parent order identifier |
| sku_id | Ordered SKU |
| quantity | Ordered quantity |
| unit_price | Price per unit |
| allocated_quantity | Quantity allocated to fulfillment |

### reservations.csv

| Column | Description |
|---|---|
| reservation_id | Unique reservation identifier |
| reservation_code | Reservation business reference |
| order_id | Related order |
| order_line_id | Related order line |
| sku_id | Reserved SKU |
| location_id | Location holding the reservation |
| quantity | Reserved quantity |
| status | Reservation lifecycle status |
| created_at | Reservation creation time |
| expires_at | Reservation expiry time |

## 4. Replenishment Data

### replenishment_rules.csv

| Column | Description |
|---|---|
| rule_id | Unique replenishment rule identifier |
| sku_id | SKU covered by the rule |
| location_id | Location covered by the rule |
| min_stock | Minimum desired stock |
| reorder_point | Stock level that triggers replenishment |
| target_stock | Desired stock after replenishment |
| lead_time_days | Expected replenishment lead time |

## 5. Anomaly Data

### anomaly_scenarios.csv

Contains intentionally constructed anomaly examples.

| Column | Description |
|---|---|
| scenario_id | Unique anomaly scenario |
| anomaly_type | Type of inventory anomaly |
| entity_type | Affected entity category |
| entity_id | Affected record identifier |
| field_name | Field affected by the scenario |
| baseline_value | Original valid value |
| anomalous_value | Deliberately incorrect value |
| description | Explanation of the anomaly |
| evidence | Supporting scenario information |

### ground_truth.csv and ground_truth.json

Contain the expected anomaly labels.

| Column | Description |
|---|---|
| scenario_id | Related anomaly scenario |
| entity_type | Entity category |
| entity_id | Affected record |
| label | 1 indicates an anomaly |
| anomaly_type | Expected anomaly category |

These labels must not be included in model input features.

## 6. Important Inventory Concepts

### Available to Promise (ATP)

A basic inventory availability calculation is:

ATP = On Hand - Reserved - Blocked - Safety Stock

Approved inbound stock may be included when the applicable
replenishment policy allows it.

### Inventory Reconciliation

Recorded on-hand stock should reconcile to the movement ledger:

Opening + Receipts + Returns + Adjustments In
- Sales - Adjustments Out - Transfers Out
+ Transfers In

Damage movements affect blocked stock rather than on-hand stock
in the current baseline design.

## 7. Data Quality Principles

- Primary keys must be unique.
- Foreign keys must reference existing records.
- Quantities must be valid and non-negative.
- Inventory movements must have valid movement types.
- Reservation and order states must follow valid lifecycle transitions.
- Baseline inventory must reconcile to movement history.
- Anomaly labels must remain separate from input features.
- Generated data must be reproducible using the fixed random seed.

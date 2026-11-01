
# StockSync – Unified Inventory & Availability Management System

StockSync is a Flask-based inventory management system designed to
provide a unified view of inventory across stores, warehouses and
online sales channels.

It combines inventory balances, stock movements, order reservations,
transfers and replenishment rules. It also includes a deterministic
synthetic data generator and data-quality validation tools.

## Project Objectives

- Maintain a unified inventory view across multiple locations.
- Track on-hand, reserved, blocked and in-transit stock.
- Calculate Available to Promise (ATP).
- Record inventory movements as an auditable ledger.
- Create and manage customer orders and reservations.
- Support stock transfers between locations.
- Recommend replenishment quantities.
- Detect inventory reconciliation and reservation anomalies.
- Generate reproducible synthetic datasets for analytics and testing.

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, Flask |
| Database ORM | Flask-SQLAlchemy |
| Database | SQLite / MySQL |
| Frontend | HTML, CSS, Bootstrap, JavaScript |
| Data processing | Python, CSV, JSON |
| Testing | Pytest |
| Version control | Git and GitHub |

## Project Structure

```text
stocksync/
│
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── extensions.py
│   ├── seed.py
│   ├── cli.py
│   ├── routes/
│   │   └── api.py
│   └── services/
│       ├── inventory.py
│       ├── orders.py
│       └── transfers.py
│
├── templates/
│   └── index.html
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
│
├── database/
│   └── schema.sql
│
├── data/
│   ├── generator.py
│   ├── validate.py
│   ├── anomalies.py
│   ├── export.py
│   ├── reproducibility.py
│   └── generated/
│
├── exports/
│   └── generated/
│       ├── json/
│       └── sql/
│
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_exports.py
│   └── test_data_quality.py
│
├── data_dictionary.md
├── requirements.txt
├── .env.example
├── .gitignore
├── run.py
└── README.md
```

## Features

### 1. Inventory Management

- Manage products and SKUs.
- Manage multiple inventory locations.
- Track on-hand quantities.
- Track reserved and blocked stock.
- Track inventory in transit.
- Maintain safety-stock levels.

### 2. Inventory Movement Ledger

Supported movement types include:

- Opening stock
- Receipt
- Sale
- Return
- Transfer out
- Transfer in
- Adjustment in
- Adjustment out
- Damage

Movement records provide an audit trail for inventory changes.

### 3. Order Management

- Create customer orders.
- Assign fulfillment locations.
- Reserve available inventory.
- Cancel orders and release reservations.
- Fulfill reserved orders.
- Record order lifecycle events.

### 4. Available to Promise

The basic ATP calculation is:

```text
ATP = On Hand - Reserved - Blocked - Safety Stock
```

Approved inbound inventory can be included according to
the applicable replenishment rule.

### 5. Stock Transfers

- Create stock transfers.
- Reduce source on-hand inventory.
- Record destination in-transit inventory.
- Receive transferred quantities.
- Prevent premature receipt counting.

### 6. Replenishment

Replenishment recommendations compare available inventory
with configured reorder points and target stock.

### 7. Analytics Dashboard

The dashboard displays inventory and operational summaries,
including products, SKUs, locations, orders and stock quantities.

## Synthetic Dataset

The synthetic data generator uses a fixed random seed:

```text
20261022
```

Default generation parameters:

| Dataset | Default records |
|---|---:|
| Products | 5,000 |
| SKUs | 5,000 |
| Locations | 100 |
| Inventory movements | 1,000,000 |
| Orders | 50,000 |

The generator also creates inventory balances, order lines,
reservations and replenishment rules.

### Generate a small test dataset

```powershell
python data/generator.py --products 50 --locations 10 --movements 1000 --orders 100
```

### Generate the full dataset

```powershell
python data/generator.py
```

Large dataset generation requires additional memory, disk space
and processing time.

## Data Validation

Run:

```powershell
python data/validate.py
```

The validator checks primary-key uniqueness, foreign-key
integrity, quantity constraints and inventory reconciliation.

The validation report is saved as:

```text
data/generated/validation_summary.json
```

## Anomaly Scenarios

Run:

```powershell
python data/anomalies.py
```

The project creates separate anomaly examples for:

1. Inventory balance mismatch.
2. Reservation overselling.
3. Fulfillment from blocked stock.
4. Transfer double counting.

Anomaly labels are stored separately from baseline input data:

```text
data/generated/anomaly_scenarios.csv
data/generated/ground_truth.csv
data/generated/ground_truth.json
```

These are synthetic scenarios for testing and analytics.
They do not modify the valid baseline CSV files.

## Export Data

Run:

```powershell
python data/export.py
```

Exports are created in:

```text
exports/generated/
├── json/
└── sql/
```

The SQL export also creates a standalone SQLite database.

## Reproducibility

Run:

```powershell
python data/reproducibility.py
```

The script generates two small datasets using the same seed
and compares their CSV SHA-256 checksums.

A successful check confirms that both runs produced identical
CSV outputs for the selected generation parameters.

## Installation

### 1. Clone the repository

```powershell
git clone https://github.com/YOUR_USERNAME/stocksync.git
cd stocksync
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

### 3. Activate the environment

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 5. Configure environment variables

Copy `.env.example` to `.env` and set a private secret key
and database connection URL.

For a local SQLite setup:

```env
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=sqlite:///stocksync.db
```

Do not commit `.env` or expose database credentials.

### 6. Initialize the application database

```powershell
flask --app run.py init-db
```

### 7. Insert starter records

```powershell
flask --app run.py seed
```

### 8. Start the application

```powershell
python run.py
```

Open:

```text
http://127.0.0.1:5000
```

Health check:

```text
http://127.0.0.1:5000/health
```

## Run Tests

```powershell
python -m pytest -v
```

## API Endpoints

The API is available under `/api`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/summary` | Dashboard summary |
| GET / POST | `/api/products` | List or create products |
| GET / POST | `/api/skus` | List or create SKUs |
| GET / POST | `/api/locations` | List or create locations |
| GET | `/api/inventory` | Inventory balances |
| GET / POST | `/api/movements` | List or post movements |
| GET / POST | `/api/orders` | List or create orders |
| POST | `/api/orders/<id>/cancel` | Cancel an order |
| POST | `/api/orders/<id>/fulfill` | Fulfill an order |
| GET / POST | `/api/transfers` | List or create transfers |
| POST | `/api/transfers/receive` | Receive a transfer |
| GET | `/api/reservations` | List reservations |
| POST | `/api/reservations/expire` | Expire due reservations |
| GET | `/api/replenishment` | Replenishment recommendations |
| GET | `/api/reconciliation/<sku_id>/<location_id>` | Reconcile inventory |
| GET | `/api/shipments` | List shipments |

## Data Model

The application models include:

- Product
- SKU
- Location
- InventoryBalance
- InventoryMovement
- CustomerOrder
- OrderLine
- Reservation
- Shipment
- ReplenishmentRule
- InventoryEvent

See `app/models.py` and `database/schema.sql` for
the model definitions and relationship documentation.

## Current Dataset Scope

The baseline generator currently generates products, SKUs,
locations, inventory balances, movements, orders, order lines,
reservations and replenishment rules.

Transfer and shipment functionality is represented in the
application models and services. The synthetic generator's
transfer/shipment dataset and full anomaly lifecycle simulation
are not yet implemented.

The anomaly scenarios are separate test cases, not production
transaction records.

## Important Notes

- The generated records are synthetic, not real customer data.
- Baseline data should pass validation before anomaly scenarios
  are used.
- Ground-truth labels must not be used as model input features.
- Inventory movements should be corrected using compensating
  events rather than silently overwritten.
- The generated SQL export is separate from the application database.

## Future Improvements

- Generate synthetic transfer and shipment histories.
- Add channel-specific inventory buffers.
- Add richer reservation expiry and lifecycle scenarios.
- Add advanced anomaly detection models.
- Add role-based authentication and access control.
- Add automated deployment and monitoring.

## Author

**Swejanrao**

Data Science Graduate | Aspiring Data Analyst

GitHub: https://github.com/Swejanrao


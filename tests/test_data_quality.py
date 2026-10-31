
import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "generated"


def read_csv(filename):
    path = DATA_DIR / filename

    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_baseline_files_exist():
    required_files = [
        "products.csv",
        "skus.csv",
        "locations.csv",
        "inventory_balances.csv",
        "inventory_movements.csv",
        "orders.csv",
        "order_lines.csv",
        "reservations.csv",
        "replenishment_rules.csv",
    ]

    for filename in required_files:
        assert (DATA_DIR / filename).exists()


def test_validation_report_passes():
    report_path = DATA_DIR / "validation_summary.json"
    assert report_path.exists()

    with report_path.open("r", encoding="utf-8") as file:
        report = json.load(file)

    assert report["status"] == "PASS"
    assert report["error_count"] == 0


def test_anomaly_scenarios_exist():
    scenarios = read_csv("anomaly_scenarios.csv")
    assert len(scenarios) == 4


def test_ground_truth_labels_match_scenarios():
    scenarios = read_csv("anomaly_scenarios.csv")
    labels = read_csv("ground_truth.csv")

    scenario_ids = {row["scenario_id"] for row in scenarios}
    label_ids = {row["scenario_id"] for row in labels}

    assert scenario_ids == label_ids
    assert all(row["label"] == "1" for row in labels)


def test_ground_truth_not_in_baseline_feature_files():
    baseline_files = [
        "products.csv",
        "skus.csv",
        "locations.csv",
        "inventory_balances.csv",
        "inventory_movements.csv",
        "orders.csv",
        "order_lines.csv",
        "reservations.csv",
        "replenishment_rules.csv",
    ]

    for filename in baseline_files:
        rows = read_csv(filename)

        if rows:
            assert "label" not in rows[0]
            assert "anomaly_type" not in rows[0]

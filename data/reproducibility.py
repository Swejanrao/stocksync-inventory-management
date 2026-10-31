
import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

DATA_DIR = Path(__file__).parent
GENERATOR = DATA_DIR / "generator.py"


def file_checksum(path):
    sha256 = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def generate_dataset(output_dir, products, locations, movements, orders):
    command = [
        sys.executable,
        str(GENERATOR),
        "--products", str(products),
        "--locations", str(locations),
        "--movements", str(movements),
        "--orders", str(orders),
        "--output", str(output_dir),
    ]

    print("Running:", " ".join(command))

    subprocess.run(
        command,
        check=True,
        cwd=GENERATOR.parent.parent,
    )


def get_checksums(folder):
    return {
        path.name: file_checksum(path)
        for path in sorted(folder.glob("*.csv"))
    }


def main():
    parser = argparse.ArgumentParser(
        description="Check StockSync synthetic data reproducibility."
    )

    parser.add_argument("--products", type=int, default=50)
    parser.add_argument("--locations", type=int, default=10)
    parser.add_argument("--movements", type=int, default=1000)
    parser.add_argument("--orders", type=int, default=100)

    args = parser.parse_args()

    if min(
        args.products,
        args.locations,
        args.movements,
        args.orders,
    ) <= 0:
        parser.error("All dataset sizes must be positive integers.")

    with tempfile.TemporaryDirectory(prefix="stocksync_repro_") as temp:
        temp_dir = Path(temp)

        output_a = temp_dir / "run_a"
        output_b = temp_dir / "run_b"

        print("\nSTOCKSYNC REPRODUCIBILITY CHECK")
        print("-" * 45)

        generate_dataset(
            output_a,
            args.products,
            args.locations,
            args.movements,
            args.orders,
        )

        generate_dataset(
            output_b,
            args.products,
            args.locations,
            args.movements,
            args.orders,
        )

        checksums_a = get_checksums(output_a)
        checksums_b = get_checksums(output_b)

        if checksums_a.keys() != checksums_b.keys():
            print("FAIL: Generated CSV file lists do not match.")
            sys.exit(1)

        differences = []

        for filename in checksums_a:
            if checksums_a[filename] != checksums_b[filename]:
                differences.append(filename)

        if differences:
            print("FAIL: Dataset files are not reproducible.")

            for filename in differences:
                print("-", filename)

            sys.exit(1)

        print("\nPASS: Both generated datasets are identical.")
        print(f"Files compared: {len(checksums_a)}")
        print("Random seed: 20261022")
        print("All CSV SHA-256 checksums match.")


if __name__ == "__main__":
    main()

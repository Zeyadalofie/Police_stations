import csv
import json
import random
import sys
from pathlib import Path
import argparse

FIELDS = ["id", "category", "status", "minutes"]
BASE = Path(__file__).resolve().parent

def make_records(extra_count=0, seed=31):
    if type(extra_count) is not int or extra_count < 0:
        raise ValueError("extra_count must be nonnegative")
    values = [
        ("SIM-001", "assistance", "closed", "20"),
        ("SIM-002", "traffic", "open", "35"),
        ("SIM-003", "property", "closed", "15"),
        ("SIM-004", "assistance", "open", "0"),
        ("SIM-005", "traffic", "closed", "50"),
        ("SIM-006", "property", "pending", "10"),
        ("SIM-007", "traffic", "open", "-5"),
        ("SIM-008", "unknown", "closed", "12"),
    ]

    records = [dict(zip(FIELDS, row)) for row in values]
    rng = random.Random(seed)
    for number in range(9, 9 + extra_count):
        records.append({
            "id": f"SIM-{number:03d}",
            "category": rng.choice(
                ["assistance", "traffic", "property"]),
            "status": rng.choice(['open', 'closed']),
            "minutes": str(rng.randint(0, 120)),
        })
    return records


def save_fixture(records):
    folder = BASE / "data" / "raw"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "shift.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
    with(folder / "shift.json").open("w", encoding="utf-8") as handle:
        json.dump(records, handle, indent=2)

def main():
    parse = argparse.ArgumentParser(description="The app run the generate data file")
    parse.add_argument("extra_count", type=int, nargs="?", default=0)
    parse.add_argument("--outpu_dir", type=Path, default=BASE / "data"/ "row")
    arg = parse.parse_args()
    if arg.extra_count < 0:
        parse.error("The number muts be nonnigative")
    folder = (BASE / arg.extra_count).resolve()
    record = make_records(arg.extra_count)
    save_fixture(record, folder)
    print(f"Generat the file {len(record)} fictional records in {folder}")

if __name__ == "__main__":
    main()


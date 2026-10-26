import argparse
import csv
import gzip
import json
import re
from pathlib import Path


BOOKING_COLUMNS = [
    "booking_id", "created_at", "slot_at", "city", "clinic_id",
    "channel", "source", "patient_id", "patient_name",
    "patient_is_new", "home_fee", "rescheduled_from",
    "status_at_export", "source_system", "source_month",
]

TEST_COLUMNS = [
    "booking_id", "test_code", "test_price",
    "source_system", "source_city", "source_month",
]

RESULT_COLUMNS = [
    "booking_id", "test_code", "result_ts",
    "result_value", "result_flag", "source_city", "source_month",
]


def open_text(path):
    """Open a plain or gzip-compressed text file."""
    if path.name.lower().endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


def find_folder(parent, name):
    """Find a folder without depending on capitalization."""
    for folder in parent.iterdir():
        if folder.is_dir() and folder.name.lower() == name.lower():
            return folder
    raise FileNotFoundError(f"Cannot find '{name}' inside {parent}")


def find_files(folder, extension):
    """Find files with an extension, including compressed files."""
    return sorted(
        path for path in folder.rglob("*")
        if path.is_file()
        and (
            path.name.lower().endswith(extension)
            or path.name.lower().endswith(extension + ".gz")
        )
    )


def get_month(path):
    match = re.search(r"20\d{2}-\d{2}", path.name)
    return match.group(0) if match else ""


def read_csv_rows(path):
    with open_text(path) as file:
        yield from csv.DictReader(file)


def read_jsonl_rows(path):
    with open_text(path) as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                yield json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON in {path}, line {line_number}"
                ) from error


def make_booking(row, system, path):
    patient = row.get("patient") or {}

    if isinstance(patient, str):
        try:
            patient = json.loads(patient)
        except json.JSONDecodeError:
            patient = {}

    if not isinstance(patient, dict):
        patient = {}

    booking = {column: row.get(column, "") for column in BOOKING_COLUMNS}
    booking["patient_id"] = (
        row.get("patient_id") or patient.get("patient_id", "")
    )
    booking["patient_is_new"] = patient.get(
        "is_new", row.get("patient_is_new", "")
    )
    booking["source_system"] = system
    booking["source_month"] = get_month(path)
    return booking


def get_tests(row, system):
    """Get tests from a Legacy or Nova row."""
    if system == "Legacy":
        return [{
            "code": row.get("test_code", ""),
            "price": row.get("test_price", ""),
        }]

    tests = row.get("tests") or []

    if isinstance(tests, str):
        try:
            tests = json.loads(tests)
        except json.JSONDecodeError:
            tests = []

    # Some Nova CSV files have one test directly in each row.
    if not tests and (row.get("test_code") or row.get("test_price")):
        tests = [{
            "code": row.get("test_code", ""),
            "price": row.get("test_price", ""),
        }]

    return tests if isinstance(tests, list) else []


def copy_one_csv(folder, output_path):
    """Write the one CSV in a folder as a plain CSV."""
    files = find_files(folder, ".csv")

    if len(files) != 1:
        raise ValueError(
            f"Expected one CSV in {folder}, but found {len(files)}"
        )

    with open_text(files[0]) as source:
        reader = csv.DictReader(source)

        if not reader.fieldnames:
            raise ValueError(f"CSV header is missing: {files[0]}")

        with output_path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
            writer.writeheader()
            writer.writerows(reader)


def row_key(row, columns):
    """Make a key from every output column in a row."""
    return tuple(row.get(column, "") for column in columns)


def main():
    parser = argparse.ArgumentParser(
        description="Combine the already-cleaned Brief A data."
    )
    parser.add_argument("--input", required=True, help="Cleaned input folder")
    parser.add_argument(
        "--output",
        default="data/data_merged",
        help="Folder for the merged CSV files",
    )
    args = parser.parse_args()

    source = Path(args.input).resolve()
    output = Path(args.output).resolve()

    if not source.is_dir():
        raise FileNotFoundError(f"Input folder not found: {source}")

    if source == output or source in output.parents:
        raise ValueError("Choose an output folder outside the input folder.")

    legacy_folder = find_folder(source, "Legacy")
    nova_folder = find_folder(source, "Nova")
    results_folder = find_folder(source, "results")
    patients_folder = find_folder(source, "Patients")
    plan_folder = find_folder(source, "Plan")

    legacy_files = find_files(legacy_folder, ".csv")

    # Read all available Nova files; exact duplicate output rows are skipped.
    nova_files = (
        find_files(nova_folder, ".jsonl")
        + find_files(nova_folder, ".csv")
    )
    result_files = find_files(results_folder, ".csv")

    if not legacy_files or not nova_files or not result_files:
        raise ValueError(
            f"Files found — Legacy: {len(legacy_files)}, "
            f"Nova: {len(nova_files)}, results: {len(result_files)}. "
            "Check the folders and file types."
        )

    output.mkdir(parents=True, exist_ok=True)

    seen_bookings = set()
    seen_tests = set()
    seen_results = set()

    booking_count = test_count = result_count = 0
    duplicate_bookings = duplicate_tests = duplicate_results = 0

    # "w" replaces old outputs; it does not append rows.
    with (
        (output / "bookings_combined.csv").open(
            "w", encoding="utf-8", newline=""
        ) as booking_file,
        (output / "booking_tests.csv").open(
            "w", encoding="utf-8", newline=""
        ) as test_file,
    ):
        booking_writer = csv.DictWriter(
            booking_file, fieldnames=BOOKING_COLUMNS
        )
        test_writer = csv.DictWriter(
            test_file, fieldnames=TEST_COLUMNS
        )
        booking_writer.writeheader()
        test_writer.writeheader()

        for system, files in (
            ("Legacy", legacy_files),
            ("Nova", nova_files),
        ):
            for path in files:
                if system == "Legacy" or path.name.lower().removesuffix(
                    ".gz"
                ).endswith(".csv"):
                    rows = read_csv_rows(path)
                else:
                    rows = read_jsonl_rows(path)

                for row in rows:
                    booking = make_booking(row, system, path)
                    booking_key = row_key(booking, BOOKING_COLUMNS)

                    if booking_key in seen_bookings:
                        duplicate_bookings += 1
                    else:
                        seen_bookings.add(booking_key)
                        booking_writer.writerow(booking)
                        booking_count += 1

                    for test in get_tests(row, system):
                        if not isinstance(test, dict):
                            continue

                        test_row = {
                            "booking_id": row.get("booking_id", ""),
                            "test_code": test.get(
                                "code", test.get("test_code", "")
                            ),
                            "test_price": test.get(
                                "price", test.get("test_price", "")
                            ),
                            "source_system": system,
                            "source_city": row.get("city", ""),
                            "source_month": get_month(path),
                        }
                        test_key = row_key(test_row, TEST_COLUMNS)

                        if test_key in seen_tests:
                            duplicate_tests += 1
                        else:
                            seen_tests.add(test_key)
                            test_writer.writerow(test_row)
                            test_count += 1

    with (output / "results_combined.csv").open(
        "w", encoding="utf-8", newline=""
    ) as result_file:
        result_writer = csv.DictWriter(
            result_file, fieldnames=RESULT_COLUMNS
        )
        result_writer.writeheader()

        for path in result_files:
            for row in read_csv_rows(path):
                result_row = {
                    "booking_id": row.get("booking_id", ""),
                    "test_code": row.get("test_code", ""),
                    "result_ts": row.get("result_ts", ""),
                    "result_value": row.get("result_value", ""),
                    "result_flag": row.get("result_flag", ""),
                    "source_city": path.parent.name,
                    "source_month": get_month(path),
                }
                result_key = row_key(result_row, RESULT_COLUMNS)

                if result_key in seen_results:
                    duplicate_results += 1
                else:
                    seen_results.add(result_key)
                    result_writer.writerow(result_row)
                    result_count += 1

    copy_one_csv(patients_folder, output / "patients.csv")
    copy_one_csv(plan_folder, output / "plan_2026_H1.csv")

    print(f"Booking rows written: {booking_count:,}")
    print(f"Exact duplicate booking rows skipped: {duplicate_bookings:,}")
    print(f"Booking-test rows written: {test_count:,}")
    print(f"Exact duplicate test rows skipped: {duplicate_tests:,}")
    print(f"Result rows written: {result_count:,}")
    print(f"Exact duplicate result rows skipped: {duplicate_results:,}")
    print(f"Five CSV files saved in: {output}")


if __name__ == "__main__":
    main() 
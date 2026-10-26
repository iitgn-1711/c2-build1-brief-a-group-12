import argparse
import csv
import gzip
import io
import json
import re
from pathlib import Path


def read_text(path):
    """Read a normal file or decompress a .gz file."""
    data = path.read_bytes()

    if path.name.lower().endswith(".gz"):
        data = gzip.decompress(data)

    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def clean_csv(source, destination):
    """Trim CSV cells and remove blank rows, repeated headers, and duplicates."""
    text = read_text(source)
    reader = csv.reader(io.StringIO(text, newline=""))
    header = [cell.strip() for cell in next(reader, [])]

    if not header:
        raise ValueError("No header row found")

    rows = []
    seen_rows = set()

    for row in reader:
        values = [cell.strip() for cell in row]

        if not values or all(value == "" for value in values):
            continue

        if values == header:
            continue

        if len(values) != len(header):
            raise ValueError(
                f"Found {len(values)} values; expected {len(header)}"
            )

        row_key = tuple(values)
        if row_key in seen_rows:
            continue

        seen_rows.add(row_key)
        rows.append(values)

    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def clean_nova_jsonl(source, destination):
    """Convert Nova JSONL bookings to CSV, with one row per booking-test."""
    columns = [
        "booking_id", "created_at", "slot_at", "city", "clinic_id",
        "channel", "source", "patient_id", "patient_is_new", "home_fee",
        "rescheduled_from", "status_at_export", "test_code", "test_price",
        "source_month",
    ]

    month_match = re.search(r"20\d{2}-\d{2}", source.name)
    source_month = month_match.group() if month_match else ""
    rows = []

    for line in read_text(source).splitlines():
        if not line.strip():
            continue

        booking = json.loads(line)
        patient = booking.get("patient") or {}
        tests = booking.get("tests") or [{}]

        for test in tests:
            rows.append({
                "booking_id": booking.get("booking_id", ""),
                "created_at": booking.get("created_at", ""),
                "slot_at": booking.get("slot_at", ""),
                "city": booking.get("city", ""),
                "clinic_id": booking.get("clinic_id", ""),
                "channel": booking.get("channel", ""),
                "source": booking.get("source", ""),
                "patient_id": patient.get("patient_id", ""),
                "patient_is_new": patient.get("is_new", ""),
                "home_fee": booking.get("home_fee", ""),
                "rescheduled_from": booking.get("rescheduled_from", ""),
                "status_at_export": booking.get("status_at_export", ""),
                "test_code": test.get("code", ""),
                "test_price": test.get("price", ""),
                "source_month": source_month,
            })

    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Clean Brief A data into CSV files.")
    parser.add_argument("--input", required=True, help="Extracted data/raw folder")
    parser.add_argument("--output", required=True, help="Folder for cleaned CSV files")
    args = parser.parse_args()

    input_folder = Path(args.input).resolve()
    output_folder = Path(args.output).resolve()
    cleaned_folder = output_folder / "cleaned_source"

    files_found = 0
    cleaned = 0
    errors = []

    for source in input_folder.rglob("*"):
        if not source.is_file():
            continue

        parts = source.relative_to(input_folder).parts
        folders = [part.lower() for part in parts]
        name = source.name.lower()

        if name.endswith((".csv", ".csv.gz")):
            file_type = "csv"
        elif name.endswith((".jsonl", ".jsonl.gz")):
            file_type = "jsonl"
        else:
            continue

        # Keep Legacy and Nova under bookings, plus results, patients, and plan.
        if len(folders) >= 3 and folders[0] == "bookings":
            if folders[1] == "legacy":
                output_parts = ("Legacy", *parts[2:])
            elif folders[1] == "nova":
                output_parts = ("Nova", *parts[2:])
            else:
                continue
        elif folders[0] in {"results", "patients", "plan"}:
            folder_name = {
                "results": "results",
                "patients": "Patients",
                "plan": "Plan",
            }[folders[0]]
            output_parts = (folder_name, *parts[1:])
        else:
            continue

        # Remove .gz and change Nova .jsonl files to .csv.
        output_name = source.name
        if output_name.lower().endswith(".gz"):
            output_name = output_name[:-3]
        if output_name.lower().endswith(".jsonl"):
            output_name = output_name[:-6] + ".csv"

        destination = cleaned_folder.joinpath(*output_parts[:-1], output_name)
        files_found += 1

        try:
            if file_type == "csv":
                clean_csv(source, destination)
            else:
                clean_nova_jsonl(source, destination)

            cleaned += 1

        except Exception as error:
            destination.unlink(missing_ok=True)
            errors.append(f"{source}: {error}")

    print(f"Brief A files found: {files_found}")
    print(f"Cleaned successfully: {cleaned}")
    print(f"Errors: {len(errors)}")
    print(f"Cleaned CSV files: {cleaned_folder}")

    for error in errors:
        print("ERROR:", error)


if __name__ == "__main__":
    main()   
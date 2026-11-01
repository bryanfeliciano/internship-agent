
"""Safely import application results returned by ChatGPT Work."""

import csv
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

JOBS_FILE = DATA / "jobs.csv"
BATCH_FILE = DATA / "work_batch.csv"
RESULTS_FILE = DATA / "work_results.csv"
BACKUP_DIR = DATA / "backups"

RESULT_FIELDS = [
    "url",
    "status",
    "confirmation",
    "notes",
]

ALLOWED_STATUSES = {
    "submitted",
    "needs_review",
    "failed",
    "skipped",
}


def timestamp():
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def unique_stamp():
    return datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S_%f"
    )


def normalize_url(value):
    parsed = urlsplit((value or "").strip())

    return urlunsplit((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path.rstrip("/"),
        "",
        "",
    ))


def read_csv(path):
    if not path.exists():
        return [], []

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            return [], []

        return list(reader), reader.fieldnames


def write_csv_atomic(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temporary = tempfile.mkstemp(
        prefix=".import_",
        suffix=".tmp",
        dir=str(path.parent),
    )

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
            newline="",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fields,
                extrasaction="ignore",
            )

            writer.writeheader()
            writer.writerows(rows)

        os.replace(temporary, path)

    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def backup_file(path):
    if not path.exists():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    destination = BACKUP_DIR / (
        f"{path.stem}_{unique_stamp()}{path.suffix}"
    )

    shutil.copy2(path, destination)

    return destination


def validate_results(results, jobs, batch):
    errors = []
    validated = []
    seen = set()

    job_lookup = {
        normalize_url(job.get("url")): job
        for job in jobs
        if job.get("url")
    }

    batch_urls = {
        normalize_url(job.get("url"))
        for job in batch
        if job.get("url")
    }

    for number, result in enumerate(results, start=2):
        url = (result.get("url") or "").strip()
        key = normalize_url(url)

        status = (
            result.get("status") or ""
        ).strip().lower()

        confirmation = (
            result.get("confirmation") or ""
        ).strip()

        notes = (
            result.get("notes") or ""
        ).strip()

        if not key:
            errors.append(
                f"Row {number}: Missing URL."
            )
            continue

        if key in seen:
            errors.append(
                f"Row {number}: Duplicate URL."
            )
            continue

        seen.add(key)

        if status not in ALLOWED_STATUSES:
            errors.append(
                f"Row {number}: Invalid status '{status}'."
            )
            continue

        if key not in job_lookup:
            errors.append(
                f"Row {number}: Unknown job URL."
            )
            continue

        if key not in batch_urls:
            errors.append(
                f"Row {number}: URL is not in the "
                "current Work batch."
            )
            continue

        job = job_lookup[key]

        if job.get("status") != "in_progress":
            errors.append(
                f"Row {number}: Job is not in_progress "
                f"(current: {job.get('status')})."
            )
            continue

        if status == "submitted" and not confirmation:
            errors.append(
                f"Row {number}: Submitted status "
                "requires confirmation evidence."
            )
            continue

        if status == "submitted" and not notes:
            errors.append(
                f"Row {number}: Submitted status "
                "requires notes describing how "
                "successful submission was verified."
            )
            continue

        if status != "submitted":
            confirmation = ""

        validated.append({
            "url": url,
            "key": key,
            "status": status,
            "confirmation": confirmation,
            "notes": notes,
        })

    return validated, errors


def main():
    print("\nCHATGPT WORK RESULTS IMPORTER")
    print("=" * 45)

    if not JOBS_FILE.exists():
        print("ERROR: jobs.csv was not found.")
        return

    if not BATCH_FILE.exists():
        print("ERROR: work_batch.csv was not found.")
        return

    if not RESULTS_FILE.exists():
        print("ERROR: work_results.csv was not found.")
        print(
            "Export the results CSV from ChatGPT Work "
            "and place it inside the data folder."
        )
        return

    jobs, fields = read_csv(JOBS_FILE)
    batch, _ = read_csv(BATCH_FILE)
    results, result_fields = read_csv(RESULTS_FILE)

    if not jobs:
        print("ERROR: Job database is empty.")
        return

    if not results:
        print("ERROR: Results CSV is empty.")
        return

    missing = [
        field
        for field in RESULT_FIELDS
        if field not in result_fields
    ]

    if missing:
        print(
            "ERROR: Missing required CSV columns: "
            + ", ".join(missing)
        )
        return

    validated, errors = validate_results(
        results,
        jobs,
        batch,
    )

    if errors:
        print("\nIMPORT REJECTED")
        print("No application records were changed.")

        for error in errors:
            print(f" - {error}")

        print(
            "\nCorrect work_results.csv and retry."
        )
        return

    lookup = {
        result["key"]: result
        for result in validated
    }

    updated_jobs = [dict(job) for job in jobs]

    counts = {
        status: 0
        for status in ALLOWED_STATUSES
    }

    now = timestamp()

    for job in updated_jobs:
        key = normalize_url(job.get("url"))

        if key not in lookup:
            continue

        result = lookup[key]

        job["status"] = result["status"]
        job["confirmation"] = result["confirmation"]
        job["last_updated"] = now

        if result["notes"]:
            previous = (job.get("notes") or "").strip()

            job["notes"] = (
                previous + " | " + result["notes"]
                if previous
                else result["notes"]
            )

        counts[result["status"]] += 1

    print(f"\nResults validated: {len(validated)}")

    try:
        database_backup = backup_file(JOBS_FILE)
        results_backup = backup_file(RESULTS_FILE)

        write_csv_atomic(
            JOBS_FILE,
            updated_jobs,
            fields,
        )

        # Keep a recoverable copy of every imported result.
        # Remove only the active inbox file after saving.
        RESULTS_FILE.unlink()

    except OSError as error:
        print(f"\nERROR: {error}")
        print(
            "Check the database and backup files "
            "before retrying."
        )
        return

    print("\nIMPORT COMPLETE")
    print("-" * 45)

    for status in [
        "submitted",
        "needs_review",
        "failed",
        "skipped",
    ]:
        print(
            f"{status}: {counts[status]}"
        )

    remaining = sum(
        1
        for job in updated_jobs
        if job.get("status") == "in_progress"
    )

    print(f"\nRemaining in_progress: {remaining}")
    print(f"Database: {JOBS_FILE}")
    print(f"Database backup: {database_backup}")
    print(f"Results archived: {results_backup}")

    if remaining:
        print(
            "\nSome applications are still in progress. "
            "Resolve them before creating another batch."
        )
    else:
        print(
            "\nBatch processing complete. "
            "You can generate another batch."
        )


if __name__ == "__main__":
    main()

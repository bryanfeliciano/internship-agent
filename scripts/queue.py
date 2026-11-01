
"""Create ranked internship application batches for ChatGPT Work."""

import csv
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
JOBS_FILE = DATA / "jobs.csv"
BATCH_FILE = DATA / "work_batch.csv"
RESULTS_FILE = DATA / "work_results.csv"
BACKUP_DIR = DATA / "backups"

BATCH_SIZE = 10

BATCH_FIELDS = [
    "url",
    "company",
    "title",
    "location",
    "source",
    "score",
    "match_status",
    "matched_skills",
    "notes",
]


def read_csv(path):
    if not path.exists():
        return [], []

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader), reader.fieldnames or []


def write_csv_atomic(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        prefix=".queue_",
        suffix=".tmp",
        dir=str(path.parent),
    )

    try:
        with os.fdopen(
            fd, "w", encoding="utf-8", newline=""
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fields,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(rows)

        os.replace(temp_path, path)

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def backup(path):
    if not path.exists():
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    destination = BACKUP_DIR / (
        f"{path.stem}_{timestamp}{path.suffix}"
    )

    shutil.copy2(path, destination)


def get_score(row):
    try:
        return float(row.get("score") or 0)
    except (TypeError, ValueError):
        return 0


def main():
    print("\nINTERNSHIP APPLICATION QUEUE")
    print("=" * 40)

    if not JOBS_FILE.exists():
        print("ERROR: jobs.csv does not exist.")
        print("Run scripts/discover.py first.")
        return

    jobs, fields = read_csv(JOBS_FILE)

    if not jobs:
        print("No internship records available.")
        return

    # Never overwrite an existing, unimported result file.
    if RESULTS_FILE.exists():
        results, _ = read_csv(RESULTS_FILE)

        if results:
            print("BLOCKED: work_results.csv exists.")
            print(
                "Import or archive those results "
                "before creating another batch."
            )
            return

    # Protect previously exported applications.
    if BATCH_FILE.exists():
        previous_batch, _ = read_csv(BATCH_FILE)

        batch_urls = {
            row.get("url", "").strip()
            for row in previous_batch
        }

        active = [
            job for job in jobs
            if job.get("url", "").strip() in batch_urls
            and job.get("status") == "in_progress"
        ]

        if active:
            print(
                f"BLOCKED: {len(active)} jobs from the "
                "previous batch are still in progress."
            )
            print(
                "Import their results before "
                "generating another batch."
            )
            return

    # High-volume mode:
    # Scores determine priority, not application eligibility.
    # Only jobs marked "new" can enter the queue.
    # Previously processed and unresolved jobs remain excluded.
    available = [
        job for job in jobs
        if job.get("status") == "new"
        and job.get("url", "").strip()
    ]

    available.sort(
        key=lambda job: (
            -get_score(job),
            job.get("company", "").lower(),
            job.get("title", "").lower(),
        )
    )

    batch = available[:BATCH_SIZE]

    if not batch:
        print("No new ranked matches available.")
        print(
            "Run discovery again or review "
            "the matching thresholds."
        )
        return

    print(f"Total jobs in database: {len(jobs)}")
    print(f"Available ranked matches: {len(available)}")
    print(f"Selected for batch: {len(batch)}")

    print("\nSELECTED APPLICATIONS")
    print("-" * 40)

    for index, job in enumerate(batch, start=1):
        print(
            f"{index}. [{job['score']}] "
            f"{job['company']} - {job['title']}"
        )

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    batch_urls = {
        job["url"].strip() for job in batch
    }

    # Prepare new records without changing other statuses.
    updated_jobs = [dict(job) for job in jobs]

    for job in updated_jobs:
        if job.get("url", "").strip() in batch_urls:
            job["status"] = "in_progress"
            job["last_updated"] = timestamp

    exported_batch = [
        {field: job.get(field, "") for field in BATCH_FIELDS}
        for job in batch
    ]

    # Backups let us recover from a failed write.
    backup(JOBS_FILE)
    backup(BATCH_FILE)

    try:
        write_csv_atomic(
            BATCH_FILE,
            exported_batch,
            BATCH_FIELDS,
        )

        write_csv_atomic(
            JOBS_FILE,
            updated_jobs,
            fields,
        )

    except (OSError, ValueError) as exc:
        print(f"ERROR: Could not save batch: {exc}")
        print("Check data/backups before retrying.")
        return

    print("\nBATCH CREATED SUCCESSFULLY")
    print(f"File: {BATCH_FILE}")
    print(f"Jobs reserved: {len(batch)}")
    print("Status: in_progress")
    print("\nReady for ChatGPT Work.")


if __name__ == "__main__":
    main()

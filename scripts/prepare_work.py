
"""Package application files for ChatGPT Work."""

import csv
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "work_batch.csv": ROOT / "data" / "work_batch.csv",
    "WORK_AGENT.md": ROOT / "instructions" / "WORK_AGENT.md",
    "object.json": ROOT / "private" / "object.json",
    "resume.pdf": ROOT / "private" / "resume.pdf",
    "answers.md": ROOT / "private" / "answers.md",
}

PACKAGES = ROOT / "work_packages"
JOBS = ROOT / "data" / "jobs.csv"


def load_csv(path):
    with path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        return list(csv.DictReader(file))


def main():
    print("\nCHATGPT WORK PACKAGE GENERATOR")
    print("=" * 45)

    missing = [
        str(path)
        for path in FILES.values()
        if not path.is_file()
    ]

    if missing:
        print("ERROR: Missing required files:")
        for path in missing:
            print(f" - {path}")
        sys.exit(1)

    batch = load_csv(FILES["work_batch.csv"])

    if not batch:
        sys.exit("ERROR: The current batch is empty.")

    if len(batch) > 10:
        sys.exit("ERROR: Batch exceeds 10 applications.")

    urls = [
        (row.get("url") or "").strip()
        for row in batch
    ]

    if not all(urls) or len(set(urls)) != len(urls):
        sys.exit("ERROR: Missing or duplicate batch URLs.")

    if not JOBS.is_file():
        sys.exit("ERROR: jobs.csv not found.")

    jobs = {
        (row.get("url") or "").strip(): row
        for row in load_csv(JOBS)
    }

    for url in urls:
        if url not in jobs:
            sys.exit(
                f"ERROR: Batch URL not in jobs.csv: {url}"
            )

        if jobs[url].get("status") != "in_progress":
            sys.exit(
                f"ERROR: Job is not in_progress: {url}"
            )

    PACKAGES.mkdir(exist_ok=True)

    existing = [
        int(path.name.split("_")[1])
        for path in PACKAGES.glob("batch_*")
        if path.is_dir()
        and path.name.split("_")[-1].isdigit()
    ]

    next_number = max(existing, default=0) + 1

    destination = PACKAGES / f"batch_{next_number:03d}"
    destination.mkdir()

    try:
        for name, source in FILES.items():
            shutil.copy2(source, destination / name)
            print(f"[COPIED] {name}")

    except OSError:
        shutil.rmtree(destination, ignore_errors=True)
        raise

    print("\nPACKAGE READY")
    print(f"Applications: {len(batch)}")
    print(f"Folder: {destination}")
    print(
        "\nUpload the five files from this folder "
        "to ChatGPT Work."
    )
    print("No application statuses were changed.")

    # Automatically open the new batch in Windows File Explorer.
    os.startfile(str(destination))

if __name__ == "__main__":
    main()

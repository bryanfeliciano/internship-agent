
"""Read-only statistics dashboard for the internship agent."""

import csv
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS_FILE = ROOT / "data" / "jobs.csv"

BATCH_SIZE = 10

STATUSES = [
    "new",
    "in_progress",
    "needs_review",
    "submitted",
    "failed",
    "skipped",
]


def read_jobs():
    if not JOBS_FILE.exists():
        print("ERROR: jobs.csv not found.")
        print("Run scripts/discover.py first.")
        return None

    with JOBS_FILE.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        return list(csv.DictReader(file))


def priority(score):
    try:
        value = float(score or 0)
    except (ValueError, TypeError):
        value = 0

    if value >= 85:
        return "High (85-100)"
    if value >= 60:
        return "Medium (60-84)"
    if value >= 40:
        return "Low (40-59)"
    return "Other (0-39)"


def print_counts(title, counter, ordered=None):
    print(f"\n{title}")
    print("-" * 58)

    items = (
        [(name, counter.get(name, 0)) for name in ordered]
        if ordered
        else counter.most_common()
    )

    for name, count in items:
        print(f"{str(name):<43} {count:>8}")


def main():
    jobs = read_jobs()

    if jobs is None:
        return

    print("\n" + "=" * 58)
    print("INTERNSHIP AGENT — STATISTICS")
    print("=" * 58)
    print(
        "Generated:",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    total = len(jobs)

    status_counts = Counter(
        (job.get("status") or "unknown").strip().lower()
        for job in jobs
    )

    available = status_counts["new"]
    reserved = status_counts["in_progress"]
    submitted = status_counts["submitted"]
    reviewed = status_counts["needs_review"]
    failed = status_counts["failed"]
    skipped = status_counts["skipped"]

    print(f"\nTotal discovered opportunities: {total}")
    print(f"Available for future batches:  {available}")
    print(f"Currently reserved:             {reserved}")
    print(f"Verified submissions recorded:  {submitted}")
    print(
        f"Estimated remaining batches:    "
        f"{math.ceil(available / BATCH_SIZE)}"
    )

    print_counts(
        "APPLICATION STATUS",
        status_counts,
        STATUSES
    )

    unknown = {
        name: count
        for name, count in status_counts.items()
        if name not in STATUSES
    }

    if unknown:
        print_counts("UNKNOWN STATUSES", Counter(unknown))

    company_counts = Counter(
        job.get("company") or "Unknown"
        for job in jobs
    )

    print_counts(
        "OPPORTUNITIES BY COMPANY",
        company_counts
    )

    priorities = Counter(
        priority(job.get("score"))
        for job in jobs
        if job.get("status") == "new"
    )

    print_counts(
        "AVAILABLE JOBS BY PRIORITY",
        priorities,
        [
            "High (85-100)",
            "Medium (60-84)",
            "Low (40-59)",
            "Other (0-39)"
        ]
    )

    submitted_by_company = Counter(
        job.get("company") or "Unknown"
        for job in jobs
        if job.get("status") == "submitted"
    )

    if submitted_by_company:
        print_counts(
            "VERIFIED SUBMISSIONS BY COMPANY",
            submitted_by_company
        )

    print("\n" + "=" * 58)
    print("APPLICATION PIPELINE")
    print("=" * 58)

    processed = submitted + reviewed + failed + skipped

    print(f"Completed/attempted outcomes: {processed}")
    print(f"Awaiting review:             {reviewed}")
    print(f"Unsuccessful attempts:       {failed}")
    print(f"Skipped:                     {skipped}")

    if processed:
        rate = submitted / processed * 100
        print(
            f"Verified submission share:   {rate:.1f}%"
        )
    else:
        print("Verified submission share:   N/A")

    print("\nNote:")
    print(
        "These figures describe local CSV records only."
    )
    print(
        "Interviews, rejections and offers are not "
        "tracked separately yet."
    )
    print(
        "Discovery counts are not application counts."
    )

    print("\nDashboard complete.")
    print("No files were modified.")


if __name__ == "__main__":
    main()

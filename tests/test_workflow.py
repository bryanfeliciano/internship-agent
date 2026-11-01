
"""Test the internship queue and importer in an isolated temporary project."""

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FIELDS = [
    "url", "company", "title", "location", "source",
    "status", "last_updated", "notes", "confirmation",
    "score", "match_status", "matched_skills"
]


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def run_script(path):
    result = subprocess.run(
        [sys.executable, str(path)],
        capture_output=True,
        text=True,
        check=True
    )
    print(result.stdout)
    if "ERROR:" in result.stdout or "IMPORT REJECTED" in result.stdout:
        raise AssertionError(result.stdout)


def main():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        scripts = root / "scripts"
        data = root / "data"
        scripts.mkdir()
        data.mkdir()

        for name in ["queue.py", "import_results.py"]:
            (scripts / name).write_bytes(
                (ROOT / "scripts" / name).read_bytes()
            )

        jobs = [
            {
                "url": f"https://example.com/test-job/{i}",
                "company": "Test Company",
                "title": f"Electrical Engineering Intern {i}",
                "location": "Texas",
                "source": "test",
                "status": "new",
                "last_updated": "",
                "notes": "",
                "confirmation": "",
                "score": str(100 - i),
                "match_status": "match",
                "matched_skills": "Python; MATLAB"
            }
            for i in range(1, 13)
        ]

        write_csv(data / "jobs.csv", FIELDS, jobs)

        print("TEST 1: Create first batch")
        run_script(scripts / "queue.py")

        batch = read_csv(data / "work_batch.csv")
        assert len(batch) == 10

        database = read_csv(data / "jobs.csv")
        assert sum(j["status"] == "in_progress" for j in database) == 10
        assert sum(j["status"] == "new" for j in database) == 2

        print("TEST 2: Prevent duplicate batch")
        run_script(scripts / "queue.py")
        assert len(read_csv(data / "work_batch.csv")) == 10

        print("TEST 3: Reject unverified submission")
        invalid = [{
            "url": batch[0]["url"],
            "status": "submitted",
            "confirmation": "",
            "notes": "No verification"
        }]
        write_csv(
            data / "work_results.csv",
            ["url", "status", "confirmation", "notes"],
            invalid
        )
        result = subprocess.run(
            [sys.executable, str(scripts / "import_results.py")],
            capture_output=True,
            text=True,
            check=True
        )
        assert "IMPORT REJECTED" in result.stdout
        assert read_csv(data / "jobs.csv")[0]["status"] == "in_progress"

        print("TEST 4: Import verified and review results")
        results = []
        for index, job in enumerate(batch):
            submitted = index < 5
            results.append({
                "url": job["url"],
                "status": "submitted" if submitted else "needs_review",
                "confirmation": f"TEST-{index}" if submitted else "",
                "notes": (
                    "Dummy success confirmation"
                    if submitted else "Dummy review blocker"
                )
            })

        write_csv(
            data / "work_results.csv",
            ["url", "status", "confirmation", "notes"],
            results
        )
        run_script(scripts / "import_results.py")

        database = read_csv(data / "jobs.csv")
        assert sum(j["status"] == "submitted" for j in database) == 5
        assert sum(j["status"] == "needs_review" for j in database) == 5
        assert sum(j["status"] == "new" for j in database) == 2

        print("TEST 5: Queue only remaining new jobs")
        run_script(scripts / "queue.py")
        next_batch = read_csv(data / "work_batch.csv")
        assert len(next_batch) == 2

        print("\nALL FIVE TESTS PASSED")
        print("Real internship records were not modified.")


if __name__ == "__main__":
    main()

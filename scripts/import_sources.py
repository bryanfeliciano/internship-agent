
"""Bulk-import Greenhouse and Lever employer boards.

Input:  private/bulk_sources.csv
Output: private/sources.json

Never modifies jobs.csv or active application batches.
"""

import csv
import json
import os
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "private" / "bulk_sources.csv"
SOURCES = ROOT / "private" / "sources.json"
BACKUPS = ROOT / "data" / "backups"

GREENHOUSE_HOSTS = {
    "job-boards.greenhouse.io",
    "boards.greenhouse.io",
    "job-boards.eu.greenhouse.io",
}

LEVER_HOSTS = {
    "jobs.lever.co",
    "jobs.eu.lever.co",
}

TIMEOUT = 20


def read_json(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "InternshipAgent/1.0",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(
        request, timeout=TIMEOUT
    ) as response:
        return json.load(response)


def parse_board_url(value):
    parsed = urllib.parse.urlsplit(value.strip())

    if parsed.scheme != "https":
        raise ValueError("Board URL must use HTTPS")

    host = (parsed.hostname or "").lower()
    parts = [
        part for part in parsed.path.split("/")
        if part
    ]

    if host in GREENHOUSE_HOSTS:
        if not parts:
            raise ValueError("Missing Greenhouse token")

        platform = "greenhouse"
        token = parts[0]

    elif host in LEVER_HOSTS:
        if not parts:
            raise ValueError("Missing Lever site")

        platform = "lever"
        token = parts[0]

    else:
        raise ValueError(
            "Unsupported host: " + host
        )

    if not token.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Invalid board identifier")

    return platform, token.lower()


def validate_board(platform, token):
    safe = urllib.parse.quote(token, safe="")

    if platform == "greenhouse":
        endpoint = (
            "https://boards-api.greenhouse.io/v1/"
            f"boards/{safe}/jobs"
        )
        result = read_json(endpoint)

        if not isinstance(result, dict):
            raise ValueError("Unexpected API response")

        jobs = result.get("jobs")

        if not isinstance(jobs, list):
            raise ValueError("Missing jobs list")

        return len(jobs)

    endpoint = (
        f"https://api.lever.co/v0/postings/{safe}"
        "?mode=json&limit=100"
    )

    result = read_json(endpoint)

    if not isinstance(result, list):
        raise ValueError("Unexpected API response")

    # Lever response is capped at 100 postings.
    return len(result)


def write_json_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temporary = tempfile.mkstemp(
        prefix=".sources_",
        suffix=".tmp",
        dir=str(path.parent),
    )

    try:
        with os.fdopen(
            fd, "w", encoding="utf-8"
        ) as file:
            json.dump(data, file, indent=2)
            file.write("\n")

        os.replace(temporary, path)

    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def main():
    print("\nBULK EMPLOYER SOURCE IMPORTER")
    print("=" * 50)

    if not INPUT.exists():
        print(f"ERROR: Missing {INPUT}")
        return

    if not SOURCES.exists():
        print(f"ERROR: Missing {SOURCES}")
        return

    with INPUT.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        required = {"company", "board_url"}

        if not required.issubset(
            set(reader.fieldnames or [])
        ):
            print("ERROR: Expected company,board_url columns")
            return

        candidates = list(reader)

    config = json.loads(
        SOURCES.read_text(encoding="utf-8-sig")
    )

    config.setdefault("greenhouse", [])
    config.setdefault("lever", [])

    existing = {
        ("greenhouse", row["board_token"].lower())
        for row in config["greenhouse"]
    }

    existing.update({
        ("lever", row["site"].lower())
        for row in config["lever"]
    })

    seen = set()
    additions = []

    duplicates = 0
    unavailable = 0
    invalid = 0

    for row in candidates:
        company = (row.get("company") or "").strip()
        board_url = (row.get("board_url") or "").strip()

        if not company or not board_url:
            print("[INVALID] Missing company or URL")
            invalid += 1
            continue

        try:
            platform, token = parse_board_url(board_url)

        except ValueError as error:
            print(f"[INVALID] {company}: {error}")
            invalid += 1
            continue

        key = (platform, token)

        if key in existing or key in seen:
            print(f"[DUPLICATE] {company}: {token}")
            duplicates += 1
            continue

        seen.add(key)

        try:
            count = validate_board(platform, token)

        except (
            urllib.error.URLError,
            OSError,
            ValueError,
            TypeError,
            KeyError,
        ) as error:
            print(f"[UNAVAILABLE] {company}: {error}")
            unavailable += 1
            continue

        if count == 0:
            print(f"[EMPTY] {company}: No published jobs")
            unavailable += 1
            continue

        print(
            f"[CANDIDATE] {company}: "
            f"{count} published positions"
        )

        additions.append({
            "company": company,
            "platform": platform,
            "token": token,
        })

    print("\nVALIDATION SUMMARY")
    print("-" * 50)
    print(f"CSV entries:           {len(candidates)}")
    print(f"Already configured:    {duplicates}")
    print(f"New accessible boards: {len(additions)}")
    print(f"Unavailable or empty:  {unavailable}")
    print(f"Invalid entries:       {invalid}")

    if not additions:
        print("\nNo new boards to add.")
        print("Existing configuration unchanged.")
        return

    print("\nNEW BOARDS REQUIRING IDENTITY VERIFICATION")

    for entry in additions:
        print(
            f" - {entry['company']}: "
            f"{entry['platform']}/{entry['token']}"
        )

    print(
        "\nAPI availability does not prove that the "
        "board belongs to the named employer."
    )
    print(
        "Verify each company-to-board association "
        "before approving the import."
    )

    approval = input(
        "\nType YES to add all listed boards: "
    ).strip()

    if approval != "YES":
        print("Cancelled. No files modified.")
        return

    for entry in additions:
        if entry["platform"] == "greenhouse":
            config["greenhouse"].append({
                "company": entry["company"],
                "board_token": entry["token"],
                "enabled": True,
            })
        else:
            config["lever"].append({
                "company": entry["company"],
                "site": entry["token"],
                "enabled": True,
            })

    BACKUPS.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    backup = BACKUPS / f"sources_{stamp}.json"
    shutil.copy2(SOURCES, backup)

    write_json_atomic(SOURCES, config)

    print("\nIMPORT SUCCESSFUL")
    print(f"New employers added: {len(additions)}")
    print(f"Backup: {backup}")
    print(f"Configuration: {SOURCES}")
    print("\nRun discover.py to search the new boards.")


if __name__ == "__main__":
    main()

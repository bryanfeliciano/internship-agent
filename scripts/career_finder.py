
"""Find Greenhouse and Lever boards linked from employer career pages.

Read:  private/career_pages.csv
Write: data/discovered_sources.csv
Does not modify sources.json or application records.
"""

import csv
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "private" / "career_pages.csv"
OUTPUT = ROOT / "data" / "discovered_sources.csv"

MAX_PAGES_PER_COMPANY = 3
MAX_BYTES = 2_000_000
TIMEOUT = 15

FIELDS = [
    "company", "platform", "token",
    "board_url", "found_on", "status"
]

GREENHOUSE_HOSTS = {
    "job-boards.greenhouse.io",
    "boards.greenhouse.io",
    "job-boards.eu.greenhouse.io",
}
LEVER_HOSTS = {
    "jobs.lever.co",
    "jobs.eu.lever.co",
}

# Never visit arbitrary third-party links.
# Follow only the supplied employer's website,
# plus identify ATS URLs without crawling them.


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.references = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)

        if tag == "a" and values.get("href"):
            self.links.append(values["href"])

        for attribute in ("href", "src", "data-url"):
            value = values.get(attribute)
            if value:
                self.references.append(value)


def hostname(url):
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def employer_domain(host):
    parts = host.split(".")
    if len(parts) < 2:
        return host
    return ".".join(parts[-2:])


def allowed_employer_host(host, origin):
    return (
        host == origin
        or host.endswith("." + origin)
    )


def get_page(url, origin):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "InternshipAgentCareerFinder/1.0",
            "Accept": "text/html",
        }
    )

    # Disable automatic redirects so redirects cannot
    # silently escape the employer's website.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(
            self, req, fp, code, msg, headers, newurl
        ):
            return None

    opener = urllib.request.build_opener(NoRedirect)

    current = url

    for _ in range(5):
        if not allowed_employer_host(
            hostname(current), origin
        ):
            raise ValueError(
                "Redirect leaves employer website"
            )

        try:
            response = opener.open(
                urllib.request.Request(
                    current,
                    headers={
                        "User-Agent":
                            "InternshipAgentCareerFinder/1.0",
                        "Accept": "text/html"
                    }
                ),
                timeout=TIMEOUT,
            )

        except urllib.error.HTTPError as exc:
            if exc.code not in (301, 302, 303, 307, 308):
                raise

            location = exc.headers.get("Location")
            if not location:
                raise ValueError(
                    "Redirect has no destination"
                )

            current = urllib.parse.urljoin(
                current, location
            )
            continue

        with response:
            content_type = response.headers.get(
                "Content-Type", ""
            ).lower()

            if "text/html" not in content_type:
                raise ValueError("Not an HTML page")

            data = response.read(MAX_BYTES + 1)

            if len(data) > MAX_BYTES:
                raise ValueError("Page exceeds size limit")

            charset = response.headers.get_content_charset()
            return (
                data.decode(charset or "utf-8", errors="replace"),
                current,
            )

    raise ValueError("Too many redirects")


def extract_board(link):
    parsed = urllib.parse.urlsplit(link)
    host = (parsed.hostname or "").lower()
    parts = [p for p in parsed.path.split("/") if p]

    platform = None
    token = None

    if host in GREENHOUSE_HOSTS:
        if (
            len(parts) >= 2
            and parts[0] == "embed"
            and parts[1] == "job_board"
        ):
            query = urllib.parse.parse_qs(parsed.query)
            token = (query.get("for") or [None])[0]
        elif parts:
            token = parts[0]

        platform = "greenhouse"

    elif host in LEVER_HOSTS and parts:
        platform = "lever"
        token = parts[0]

    if not token or not re.fullmatch(
        r"[A-Za-z0-9_-]{2,100}", token
    ):
        return None

    if platform == "greenhouse":
        board_url = (
            "https://job-boards.greenhouse.io/" + token
        )
    else:
        board_url = "https://jobs.lever.co/" + token

    return platform, token, board_url


def find_candidates(company, start_url):
    origin = employer_domain(hostname(start_url))

    if not origin or "." not in origin:
        raise ValueError("Invalid employer domain")

    pending = [start_url]
    visited = set()
    results = {}

    while pending and len(visited) < MAX_PAGES_PER_COMPANY:
        url = pending.pop(0)

        if url in visited:
            continue

        visited.add(url)

        try:
            html, final_url = get_page(url, origin)
        except (OSError, ValueError) as exc:
            print(f"  [WARNING] {url}: {exc}")
            continue

        parser = LinkParser()
        parser.feed(html)

        # Look at actual links and embedded URLs.
        # URL regex also catches common script configurations.
        raw_urls = list(parser.references)
        raw_urls.extend(
            re.findall(
                r'https?://[^\s"\'<>\\]+',
                html
            )
        )

        for raw in raw_urls:
            link = urllib.parse.urljoin(final_url, raw)
            candidate = extract_board(link)

            if candidate:
                platform, token, board_url = candidate
                results[(platform, token.lower())] = {
                    "company": company,
                    "platform": platform,
                    "token": token,
                    "board_url": board_url,
                    "found_on": final_url,
                    "status": "needs_verification",
                }

        # Discover additional employer-hosted career pages.
        for raw in parser.links:
            link = urllib.parse.urljoin(final_url, raw)
            parsed = urllib.parse.urlsplit(link)

            if parsed.scheme not in ("http", "https"):
                continue

            if not allowed_employer_host(
                hostname(link), origin
            ):
                continue

            path = parsed.path.lower()

            if not any(
                word in path
                for word in (
                    "career", "job", "opening",
                    "opportunit", "position"
                )
            ):
                continue

            clean_url = urllib.parse.urlunsplit((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                "",
                "",
            ))

            if (
                clean_url not in visited
                and clean_url not in pending
                and len(pending) < 10
            ):
                pending.append(clean_url)

    return list(results.values())


def main():
    if not INPUT.exists():
        print(f"Missing input: {INPUT}")
        return

    with INPUT.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        if not {"company", "url"}.issubset(
            set(reader.fieldnames or [])
        ):
            print("Input requires company,url columns.")
            return

        companies = list(reader)

    all_results = []

    for item in companies:
        company = (item.get("company") or "").strip()
        url = (item.get("url") or "").strip()

        parsed = urllib.parse.urlsplit(url)

        if (
            not company
            or parsed.scheme != "https"
            or not parsed.hostname
        ):
            print(f"[SKIP] Invalid entry: {company}")
            continue

        print(f"\n[CHECK] {company}: {url}")

        results = find_candidates(company, url)
        all_results.extend(results)

        print(f"  Found {len(results)} candidate boards")

        for result in results:
            print(
                f"  {result['platform']}: "
                f"{result['token']}"
            )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    temporary = OUTPUT.with_suffix(".csv.tmp")

    with temporary.open(
        "w", encoding="utf-8", newline=""
    ) as file:
        writer = csv.DictWriter(
            file, fieldnames=FIELDS
        )
        writer.writeheader()
        writer.writerows(all_results)

    temporary.replace(OUTPUT)

    print("\nCAREER SOURCE DISCOVERY COMPLETE")
    print(f"Employers checked: {len(companies)}")
    print(f"Candidates found: {len(all_results)}")
    print(f"Report: {OUTPUT}")
    print(
        "No sources or application records were changed."
    )


if __name__ == "__main__":
    main()

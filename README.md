# internship-agent
Python-based internship discovery, ranking, and application automation system.
# Internship Agent

### Automated Internship Discovery and Application Management System

Internship Agent is a Python-based automation project designed to simplify the process of finding, evaluating, organizing, and applying for engineering internships.

I developed this project to address the repetitive and time-consuming nature of internship applications. Rather than manually searching hundreds of listings, tracking individual applications, and repeatedly entering the same information, the system automates job discovery, qualification matching, application prioritization, and tracking.

The project integrates with ChatGPT Work to assist with application submission while maintaining a local record of application statuses and outcomes.

## Features

- **Automated Job Discovery:** Retrieves publicly available job listings from configured Greenhouse and Lever employer boards.
- **Qualification Matching:** Compares job listings against a locally stored JSON profile containing education, professional experience, technical skills, and internship preferences.
- **Application Ranking:** Assigns scores based on relevant skills, position requirements, and location preferences.
- **High-Volume Application Management:** Prioritizes stronger matches without excluding other potentially suitable internship opportunities.
- **Duplicate Prevention:** Tracks previously discovered and processed applications to reduce repeated submissions.
- **Batch Processing:** Organizes applications into groups of 10 for processing through ChatGPT Work.
- **Application Tracking:** Records submitted, skipped, failed, and review-required applications.
- **Statistics Dashboard:** Displays discovered opportunities, application statuses, company distributions, and remaining application batches.
- **Private Applicant Data:** Keeps personal information, resumes, application history, and generated Work packages outside public Git tracking.

## Technologies

- Python 3
- REST APIs
- JSON
- CSV
- Git and GitHub
- Windows PowerShell
- Visual Studio Code
- ChatGPT Work

The local Python scripts use the standard library and do not require additional Python packages.

## Getting Started

### 1. Clone the repository

```powershell
git clone https://github.com/bryanfeliciano/internship-agent.git
cd internship-agent
```

### 2. Configure applicant information

Create a `private` directory containing:

- `object.json` — Applicant profile, qualifications, skills, and preferences.
- `sources.json` — Configured Greenhouse and Lever job boards.
- `resume.pdf` — Applicant resume.
- `answers.md` — Previously approved application answers.

These files contain personal information and are excluded from Git.

The project requires correctly structured JSON configuration files before running the discovery engine.

### 3. Discover internship opportunities

```powershell
py -3 scripts\discover.py
```

This searches the configured employer boards, evaluates internship opportunities, removes previously discovered duplicates, and updates the local CSV database.

Results are stored in:

- `data/jobs.csv`
- `data/ranked_internships.csv`

### 4. View application statistics

```powershell
py -3 scripts\stats.py
```

Displays discovered opportunities, available applications, reserved batches, submission records, and priority distributions.

### 5. Generate an application batch

```powershell
py -3 scripts\queue.py
```

Selects up to 10 new applications, prioritizes them by matching score, and marks them as `in_progress`.

The selected applications are saved in `data/work_batch.csv`.

### 6. Prepare files for ChatGPT Work

```powershell
py -3 scripts\prepare_work.py
```

Creates a numbered folder containing:

- `work_batch.csv`
- `WORK_AGENT.md`
- `object.json`
- `resume.pdf`
- `answers.md`

The package can then be provided to ChatGPT Work for application processing.

On Windows, the script can be configured to automatically open the generated folder in File Explorer.

### 7. Import application results

After ChatGPT Work processes the applications, save its returned CSV as:

`data/work_results.csv`

Then run:

```powershell
py -3 scripts\import_results.py
```

The importer updates the application database, records reported outcomes, preserves historical results, and prevents previously processed opportunities from being automatically queued again.

### 8. Generate the next batch

After successfully importing the previous batch:

```powershell
py -3 scripts\queue.py
py -3 scripts\prepare_work.py
```

Repeat this process to continue processing internship opportunities.

## Expanding Employer Coverage

Additional employer job boards can be configured through `private/sources.json`.

The project also includes tools for validating and importing employer sources:

```powershell
py -3 scripts\validate_sources.py
py -3 scripts\import_sources.py
```

These tools help expand the discovery network while identifying duplicate or unavailable recruiting-platform endpoints.

## Application Safety and Data Integrity

The system is designed to:

- Preserve previously recorded application statuses.
- Avoid automatically resubmitting unresolved applications.
- Prevent duplicate jobs from entering active queues.
- Require reported submission confirmation before marking an application as submitted.
- Avoid inventing applicant qualifications, employment experience, or technical expertise.
- Back up application records before importing results.
- Keep applicant data excluded from Git through `.gitignore`.

Application submission is handled separately through ChatGPT Work. The local Python discovery engine does not independently submit job applications.

## Future Development

Planned improvements include:

- Integration with additional recruiting platforms, including Ashby and Workday.
- Improved qualification matching using local language models.
- Expanded employer discovery.
- Automated application-status synchronization.
- Interview, rejection, and offer tracking.
- Reduced dependence on paid AI-agent usage.
- More advanced analytics and application dashboards.

## Project Status

Active development.

The current implementation supports automated employer-board discovery, profile-based ranking, CSV batch management, application-result importing, and local statistics.

## Author

Bryan Feliciano

Electrical Engineering Undergraduate

GitHub: https://github.com/bryanfeliciano
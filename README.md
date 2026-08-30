# BugFlow – Step 1: Issue Database

Module 1 foundation: Issue Reporting & Management.

## VS Code

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python create_database.py
python check_database.py
```

A `bugflow.db` SQLite database and an `issues` table will be created.

## Issue table

The table contains issue key, type, title, description, reproduction steps,
severity, priority, status, affected module, environment, screenshot URL,
project, reporter, assignee, created time and updated time.

Next: Step 2 – FastAPI Issue Reporting API.

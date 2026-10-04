# BugFlow Deployment Guide

## 1. Project Prerequisites

- **Operating System:** Windows 10/11, Linux (Ubuntu 20.04+), or macOS (12+)
- **Python:** Python 3.11+ (recommended: 3.11.9)
- **Database:** PostgreSQL 14+ (or compatible managed PostgreSQL service)
- **Web Browser:** Modern Chromium, Firefox, or Safari browser
- **Version Control:** Git 2.30+

---

## 2. Python Environment & Setup

Clone the repository and navigate into the root directory:

```powershell
git clone https://github.com/soma896/BugFlow.git
cd BugFlow
```

Create and activate a Python virtual environment:

### Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Linux / macOS (Bash)
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Dependency Installation

Upgrade pip and install the production dependencies:

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

Core dependencies installed:
- `fastapi` — Asynchronous REST API framework
- `uvicorn` — ASGI production web server
- `sqlalchemy` — Enterprise ORM & SQL toolkit
- `psycopg2` / `psycopg2-binary` — PostgreSQL adapter
- `pydantic` — Data validation and request schemas
- `werkzeug` — Secure password hashing and crypto primitives
- `python-multipart` — Form data and file upload support

---

## 4. PostgreSQL Configuration

1. Ensure the PostgreSQL service is active:
   ```powershell
   # Windows Service Check
   Get-Service -Name postgresql*
   ```

2. Create the target database:
   ```sql
   CREATE DATABASE bugfinding;
   ```

3. Ensure PostgreSQL user permissions:
   ```sql
   GRANT ALL PRIVILEGES ON DATABASE bugfinding TO postgres;
   ```

---

## 5. Environment Variables & Database Connection

BugFlow reads the database connection string and optional integration secrets from environment variables or configuration files.

Create a `.env` file in the root project directory:

```env
# Database Connection (Replace with your actual credentials)
DATABASE_URL=postgresql+psycopg2://<DB_USER>:<DB_PASSWORD>@<DB_HOST>:<DB_PORT>/<DB_NAME>

# Application Server Configuration
HOST=127.0.0.1
PORT=8080
LOG_LEVEL=info

# Integration Credentials (Placeholders)
GITHUB_WEBHOOK_SECRET=<your-github-webhook-secret>
GITHUB_TOKEN=<your-github-personal-access-token>
CICD_WEBHOOK_KEY=<your-cicd-webhook-api-key>
```

In `app/database.py`:
```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:somu2005@localhost:8000/bugfinding"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## 6. Database Initialization & Optimization Indexes

Run the initialization scripts to verify connectivity and apply performance indexes:

```powershell
python check_database.py
python scratch/apply_db_indexes.py
```

The database optimization indexes include:
- `idx_defects_status` on `defects(status)`
- `idx_defects_assigned_role` on `defects(assigned_role)`
- `idx_defects_priority` on `defects(priority)`
- `idx_defects_category` on `defects(category)`
- `idx_defects_created_at` on `defects(created_at)`
- `idx_defects_user_id` on `defects(user_id)`
- `idx_admin_actions_defect_id` on `admin_actions(defect_id)`
- `idx_sprint_issues_sprint_id` on `sprint_issues(sprint_id)`
- `idx_sprint_issues_issue_id` on `sprint_issues(issue_id)`
- `idx_sprints_assigned_role` on `sprints(assigned_role)`
- `idx_sprints_status` on `sprints(status)`

---

## 7. Application & API Startup

Start BugFlow with Uvicorn:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

For production deployment with multiple worker processes:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
```

Verify service health:
```bash
curl http://127.0.0.1:8080/health
# Response: {"status":"ok","service":"BugFlow API"}
```

---

## 8. Frontend Access & Web UI Routes

Open your browser and navigate to:

| UI View | Route | Description |
|---|---|---|
| **Login** | `/login-ui` | Authentication entry point |
| **Admin Dashboard** | `/admin-ui` | Admin KPIs and defect triage |
| **All Defects** | `/all-defects-ui` | Comprehensive searchable defect catalog |
| **Sprint Management** | `/milestone2-ui` | Agile sprint boards and backlog planning |
| **Team Collaboration** | `/team-collaboration-ui` | Cross-role defect collaboration & review |
| **Analytics Reports** | `/analytics-ui` | Advanced reporting & productivity analytics |
| **Integrations & CI/CD** | `/integrations-ui` | GitHub webhooks and automated CI/CD pipeline |
| **API Explorer** | `/api-explorer-ui` | Interactive OpenAPI / REST testing suite |
| **Developer Workspace** | `/developer-ui` | Sasuke (Developer) task dashboard |
| **Tester Workspace** | `/tester-ui` | Hinata (Tester) QA verification board |
| **Senior Dev Workspace** | `/senior-developer-ui` | Itachi (Senior Dev) review & architecture |
| **User Workspace** | `/user-ui` | End-user defect reporting interface |

---

## 9. Authentication & Workspace Context

BugFlow implements a secure single-administrator session model with server-side workspace switching:

1. **Authentication:**
   - Endpoint: `POST /login`
   - Body: `{"email": "admin@example.com", "password": "Admin@123"}`
   - Token Type: Bearer JWT / persistent session token in `auth_sessions`.

2. **Workspace Switching (Admin Only):**
   - Endpoint: `POST /api/v1/workspace/switch`
   - Header: `Authorization: Bearer <TOKEN>`
   - Body: `{"role": "developer"}` (Options: `admin`, `developer`, `tester`, `senior_dev`, `user`)
   - Role permissions and database records are strictly preserved without mutating the user's base identity.

---

## 10. GitHub Integration Configuration

Configure GitHub Webhooks to synchronize commits, PRs, and defect statuses:

1. In your GitHub repository: **Settings > Webhooks > Add webhook**
2. Payload URL: `https://<your-bugflow-domain>/api/v1/integrations/github/webhook`
3. Content type: `application/json`
4. Secret: `<your-github-webhook-secret>`
5. Events: Select **Pushes** and **Pull requests**
6. Commit reference syntax supported in commit messages:
   - `#<id>` (e.g. `Fix auth validation error (refs #2)`)
   - `BUG-<id>` (e.g. `BUG-002: Resolve connection leak`)
   - `DEF-<id>` (e.g. `DEF-14: Update query index`)

---

## 11. CI/CD Pipeline Integration

Connect your CI/CD pipeline (GitHub Actions, GitLab CI, or Jenkins) to auto-report build failures:

```yaml
# Sample GitHub Actions workflow step:
- name: Notify BugFlow CI/CD
  if: always()
  run: |
    curl -X POST "http://127.0.0.1:8080/api/v1/integrations/cicd/webhook" \
      -H "Content-Type: application/json" \
      -d '{
        "pipeline_id": "gh-actions-ci",
        "pipeline_name": "BugFlow Main CI",
        "build_number": ${{ github.run_number }},
        "branch": "${{ github.ref_name }}",
        "status": "${{ job.status == '\''success'\'' && '\''SUCCESS'\'' || '\''FAILURE'\'' }}",
        "total_tests": 120,
        "passed_tests": 120,
        "failed_tests": 0
      }'
```

When a build fails, BugFlow automatically creates a high-priority defect and links the build log to the defect tracker.

---

## 12. Running Test Suites

Run the comprehensive integration, performance, security, and UAT test suites:

```powershell
# Full Regression & Integration Verification (111 tests)
python scratch/verify_full_integration.py

# Performance & Load Benchmark (p95 <= 300ms, 50K records)
python scratch/test_performance.py

# Security Verification Suite (15 assertions)
python scratch/test_security.py

# Usability & User Acceptance Testing (23 pages, 4 roles)
python scratch/test_uat_usability.py
```

---

## 13. Production Considerations

1. **Reverse Proxy:** Run behind Nginx or Caddy with HTTPS/TLS termination and HTTP/2 enabled.
2. **Process Management:** Use Systemd (Linux) or NSSM (Windows) to supervise the Uvicorn process.
3. **Database Pooling:** Use PgBouncer or SQLAlchemy connection pool sizing (`pool_size=20, max_overflow=10`).
4. **Static Assets:** Serve `/Frontend` assets with caching headers (`Cache-Control: public, max-age=86400`).
5. **Backups:** Implement daily `pg_dump` backups for the `bugfinding` database.

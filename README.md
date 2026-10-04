# BugFlow — Enterprise Defect Tracking & Analytics System

BugFlow is a full-lifecycle defect tracking, workflow automation, team productivity analytics, and CI/CD integration platform built with FastAPI, PostgreSQL, SQLAlchemy, and modern HTML5/CSS3.

---

## Architectural Milestones

- **Module 1: Foundation & Defect Tracking**
  - Authentication, secure sessions, user dashboard, defect reporting, issue categorization, priority assignment, reproduction steps, audit history.
- **Module 2: Workflow Automation & Agile Collaboration**
  - Smart priority recommendations, role assignment (Admin Naruto, Dev Sasuke, Tester Hinata, Senior Dev Itachi), Accept/Reject workflow, Sprint management (`/milestone2-ui`), threaded comments, file attachments, traceable code references.
- **Module 3: REST API Layer, Analytics & DevOps Integrations**
  - Comprehensive REST APIs, interactive API Explorer (`/api-explorer-ui`), real-time PostgreSQL analytics, DSI & MTTR quality metrics, GitHub webhook synchronization, CI/CD automated defect reporting, in-app notifications.
- **Module 4: Finalization, Productivity Analytics, Testing & Optimization**
  - Factual team productivity metrics across canonical personas, workflow funnel throughput, defect aging analysis, multi-format report exports (CSV, JSON, HTML), 11 PostgreSQL performance indexes, in-memory query optimization (sub-30ms p95 latency), 50,000+ issue processing verification, comprehensive security, usability, and UAT test suites.

---

## Canonical Team Personas

- **Naruto (Admin):** Triage, assignment, sprint planning, analytics, and system settings.
- **Sasuke (Developer):** Investigation, implementation, PR linking, and progress tracking.
- **Hinata (Tester):** Test verification, QA signoff, regression tests, and bug reporting.
- **Itachi (Senior Developer):** Architectural review, code review, escalations, and resolution signoff.

*There is ONE real authenticated Admin account (`admin@example.com`). Persona views are seamlessly accessed via the server-side **Switch Workspace** mechanism.*

---

## Quick Start

### 1. Setup Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Verify Database & Apply Optimization Indexes
```powershell
python check_database.py
python scratch/apply_db_indexes.py
```

### 3. Start Application Server
```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Access the application at `http://127.0.0.1:8080/admin-ui` (or `/login-ui`).

---

## Documentation Links

- [Deployment Guide](docs/DEPLOYMENT.md) — Prerequisites, configuration, environment variables, startup, and production guidelines.
- [REST API Reference](docs/API_REFERENCE.md) — Complete endpoint reference for Issues, Sprints, Analytics, Integrations, and Productivity APIs.
- [User Guide](docs/USER_GUIDE.md) — Step-by-step role workflows, defect lifecycles, sprint boards, and reporting.

---

## Running Verification & Test Suites

```powershell
# Master Comprehensive Verification (All Modules 1, 2, 3, 4)
python scratch/verify_module4_final.py

# Full Integration Regression Suite (111 tests)
python scratch/verify_full_integration.py

# Performance & Load Benchmark (p95 latency, 50K issue processing)
python scratch/test_performance.py

# Security Verification Suite (15 assertions)
python scratch/test_security.py

# Usability & User Acceptance Testing (23 pages, 4 roles)
python scratch/test_uat_usability.py
```

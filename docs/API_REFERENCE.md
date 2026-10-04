# BugFlow REST API Reference

Base URL: `http://127.0.0.1:8080/api/v1`

Interactive API Explorer: `http://127.0.0.1:8080/api-explorer-ui`  
OpenAPI Interactive Docs: `http://127.0.0.1:8080/docs`

---

## Authentication & Headers

Protected endpoints require a Bearer token in the `Authorization` header:

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

To obtain a token:
```http
POST /login
Content-Type: application/json

{"email": "admin@example.com", "password": "Admin@123"}
```
Response:
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "role": "admin"
}
```

---

## 1. Issue & Defect Management

### 1.1 List Issues & Defects
- **Endpoint:** `GET /api/v1/issues`
- **Purpose:** Retrieve paginated issues and defects with filtering.
- **Auth:** Optional / Bearer Token
- **Query Parameters:**
  - `status` *(string, optional)*: Filter by status (e.g. `Pending`, `Assigned`, `Accepted`, `Resolved`)
  - `priority` *(string, optional)*: Filter by priority (`Urgent`, `High`, `Medium`, `Low`)
  - `role` *(string, optional)*: Filter by assigned role (`admin`, `developer`, `tester`, `senior_dev`)
  - `q` *(string, optional)*: Full-text search term in title or description
  - `skip` *(integer, default: 0)*: Pagination offset
  - `limit` *(integer, default: 50, max: 200)*: Items per page
  - `source` *(string, default: "all")*: Source (`all`, `defects`, `issues`)
- **Response (200 OK):**
```json
{
  "total": 52,
  "skip": 0,
  "limit": 50,
  "items": [
    {
      "id": 1,
      "issue_key": "BUG-001",
      "title": "Database connection pool timeout",
      "category": "Backend",
      "priority": "High",
      "status": "Assigned",
      "assigned_role": "developer",
      "created_at": "2026-10-01T10:00:00"
    }
  ]
}
```
- **Errors:** 400 Bad Request (invalid filter syntax)

### 1.2 Retrieve Single Issue
- **Endpoint:** `GET /api/v1/issues/{issue_id}`
- **Purpose:** Retrieve full details of an issue or defect by its integer ID.
- **Auth:** Optional
- **Response (200 OK):** JSON defect object with comments, attachments, and audit history.
- **Errors:** 404 Not Found

### 1.3 Create Issue / Defect
- **Endpoint:** `POST /api/v1/issues` (or `POST /defects`)
- **Purpose:** Create a new bug report in the system.
- **Auth:** Bearer Token
- **Request Body:**
```json
{
  "title": "NullPointerException on checkout",
  "description": "Clicking Pay Now without address triggers 500 error",
  "category": "Backend",
  "priority": "High",
  "severity": "CRITICAL",
  "environment": "Production",
  "affected_module": "Payments"
}
```
- **Response (201 Created / 200 OK):** Created issue object with assigned ID.
- **Errors:** 422 Unprocessable Entity (missing required fields)

---

## 2. Assignment & Workflow Operations

### 2.1 Assign Issue to Role
- **Endpoint:** `POST /api/v1/issues/{issue_id}/assign`
- **Purpose:** Assign an issue to a canonical project role (Admin, Developer, Tester, Senior Dev).
- **Auth:** Bearer Token (Admin only)
- **Request Body:**
```json
{
  "role": "developer",
  "note": "Assigned to Sasuke for investigation"
}
```
- **Response (200 OK):**
```json
{
  "status": "success",
  "defect_id": 1,
  "assigned_role": "developer",
  "defect_status": "ASSIGNED"
}
```
- **Critical Rule:** Admin assignment transitions status to `ASSIGNED`. It does NOT auto-resolve the issue.
- **Errors:** 400 Bad Request (invalid role), 404 Not Found

### 2.2 Role Response (Accept / Reject)
- **Endpoint:** `POST /api/v1/issues/{issue_id}/assignment-response`
- **Purpose:** Assigned persona accepts or rejects defect ownership.
- **Auth:** Bearer Token
- **Request Body:**
```json
{
  "action": "ACCEPT",
  "role": "developer",
  "note": "Work started"
}
```
- **Response (200 OK):**
```json
{
  "status": "success",
  "defect_id": 1,
  "defect_status": "ACCEPTED"
}
```
- **Errors:** 400 Bad Request (`action` must be `ACCEPT` or `REJECT`)

### 2.3 Resolve Issue
- **Endpoint:** `POST /api/v1/issues/{issue_id}/resolve` (or `POST /collaboration/issues/{issue_id}/resolve`)
- **Purpose:** Mark an accepted defect as resolved.
- **Auth:** Bearer Token
- **Request Body:**
```json
{
  "resolution_summary": "Fixed deadlock in connection manager",
  "note": "Verified locally with 200 concurrent requests"
}
```
- **Response (200 OK):**
```json
{
  "status": "success",
  "defect_id": 1,
  "defect_status": "RESOLVED"
}
```
- **Critical Rule:** Resolution is strictly blocked with HTTP 400 if the issue is in `REJECTED` status.
- **Errors:** 400 Bad Request, 404 Not Found

### 2.4 Update Role Work Progress
- **Endpoint:** `PUT /api/v1/collaboration/issues/{issue_id}/work`
- **Purpose:** Role records progress percentage, notes, and sub-status.
- **Auth:** Bearer Token
- **Request Body:**
```json
{
  "role": "developer",
  "progress": 85,
  "status": "IN_PROGRESS",
  "note": "Pull request submitted for code review"
}
```
- **Allowed Statuses by Role:**
  - `developer`: `NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`, `BLOCKED`
  - `tester`: `NOT_STARTED`, `IN_TESTING`, `PASSED`, `FAILED`, `BLOCKED`
  - `senior_dev`: `NOT_STARTED`, `IN_REVIEW`, `APPROVED`, `REVISION_REQUESTED`, `BLOCKED`
- **Response (200 OK):** Status updated confirmation.
- **Errors:** 400 Bad Request (invalid status for role)

---

## 3. Sprint Management Operations

### 3.1 List All Sprints
- **Endpoint:** `GET /api/v1/sprints/`
- **Purpose:** Retrieve all sprint milestones with issue counts and assigned roles.
- **Auth:** Bearer Token
- **Response (200 OK):**
```json
[
  {
    "id": 1,
    "sprint_name": "Sprint 2",
    "goal": "Core payment integration stabilization",
    "status": "ACTIVE",
    "assigned_role": "developer",
    "issues_count": 4
  }
]
```

### 3.2 Sprint Backlog
- **Endpoint:** `GET /api/v1/sprints/backlog`
- **Purpose:** Retrieve unassigned defects available for sprint planning.
- **Auth:** Bearer Token
- **Response (200 OK):** Array of backlog defect records.

### 3.3 Create Sprint
- **Endpoint:** `POST /api/v1/sprints/`
- **Purpose:** Create a new sprint cycle.
- **Auth:** Bearer Token (Admin only)
- **Request Body:**
```json
{
  "sprint_name": "Sprint 7 - Security Hardening",
  "goal": "Patch authentication and session leaks",
  "start_date": "2026-10-10",
  "end_date": "2026-10-24",
  "assigned_role": "developer"
}
```

### 3.4 Sprint Metrics & Velocity
- **Endpoint:** `GET /api/v1/sprints/metrics/analytics`
- **Purpose:** Agile velocity, burndown, and completion percentages.
- **Auth:** Bearer Token

---

## 4. Advanced Reporting & Analytics

### 4.1 Summary KPIs
- **Endpoint:** `GET /api/v1/analytics/summary`
- **Purpose:** High-level KPIs: total defects, resolution rate, MTTR, DSI, CI/CD pass rate.
- **Auth:** Optional

### 4.2 Defect Trends & Trajectories
- **Endpoint:** `GET /api/v1/analytics/trends`
- **Purpose:** Daily arrival vs resolution trend, cumulative trajectories, aging buckets (<24h, 1-3d, 4-7d, >7d).
- **Auth:** Optional

### 4.3 Software Quality Metrics
- **Endpoint:** `GET /api/v1/analytics/quality`
- **Purpose:** Defect Severity Index (DSI), defect density by category, priority distribution, reopen rate, SLA compliance.
- **Auth:** Optional

### 4.4 Team Workload Distribution
- **Endpoint:** `GET /api/v1/analytics/team`
- **Purpose:** Workload and resolution counts across Admin, Developer, Tester, and Senior Dev.
- **Auth:** Optional

### 4.5 Team Productivity Analytics (Module 4)
- **Endpoint:** `GET /api/v1/analytics/productivity`
- **Purpose:** Factual productivity indicators across Naruto (Admin), Sasuke (Developer), Hinata (Tester), and Itachi (Senior Dev).
- **Auth:** Optional
- **Response (200 OK):**
```json
{
  "total_defects_analyzed": 52,
  "total_assigned": 43,
  "total_audit_transitions": 233,
  "sprint_progress": {
    "total_sprints": 6,
    "active_sprints": 5,
    "completed_sprints": 1,
    "completion_rate_pct": 16.7
  },
  "aging_analysis": {
    "< 24h": 0,
    "1 - 3 days": 2,
    "4 - 7 days": 26,
    "> 7 days": 0
  },
  "roles": [
    {
      "role_key": "developer",
      "persona_name": "Sasuke",
      "role_title": "Developer",
      "label": "Sasuke (Developer)",
      "issues_assigned": 18,
      "issues_accepted": 0,
      "issues_rejected": 0,
      "issues_resolved": 7,
      "open_backlog": 4,
      "resolution_rate_pct": 38.9,
      "avg_resolution_time_hours": 14.5,
      "status_transition_activity": 22,
      "work_distribution_pct": 41.9,
      "sprints_count": 3,
      "sprint_issues_count": 4
    }
  ]
}
```

### 4.6 Workflow Funnel Metrics (Module 4)
- **Endpoint:** `GET /api/v1/analytics/workflow`
- **Purpose:** Funnel distribution (Reported -> Assigned -> Accepted -> Testing -> Resolved) and transition pairs.
- **Auth:** Optional

### 4.7 Unified Dashboard Payload
- **Endpoint:** `GET /api/v1/analytics/dashboard`
- **Purpose:** One-shot combined payload powering Admin Analytics UI charts.
- **Auth:** Optional

---

## 5. Report Exports

- **CSV Export:** `GET /api/v1/analytics/export/csv` — Stream all defect records as CSV.
- **JSON Export:** `GET /api/v1/analytics/export/json` — Full JSON analytics snapshot.
- **Executive Summary:** `GET /api/v1/analytics/export/summary` — Printable executive quality report HTML.
- **Productivity CSV Export:** `GET /api/v1/analytics/export/productivity` — Team productivity report CSV.
- **Sprint CSV Export:** `GET /api/v1/analytics/export/sprint` — Sprint milestone and backlog CSV.
- **Workflow CSV Export:** `GET /api/v1/analytics/export/workflow` — Workflow funnel throughput CSV.

---

## 6. GitHub & CI/CD Integrations

### 6.1 GitHub Webhook Receiver
- **Endpoint:** `POST /api/v1/integrations/github/webhook`
- **Headers:** `X-GitHub-Event: push`

### 6.2 Manual GitHub Synchronization
- **Endpoint:** `POST /api/v1/integrations/github/sync`
- **Request Body:**
```json
{
  "repository": "soma896/BugFlow",
  "branch": "main",
  "author": "Sasuke Uchiha",
  "commit_message": "Fix authentication bug (refs #1)"
}
```

### 6.3 CI/CD Pipeline Webhook
- **Endpoint:** `POST /api/v1/integrations/cicd/webhook`
- **Request Body:**
```json
{
  "pipeline_id": "bugflow-ci",
  "pipeline_name": "Test & Lint Suite",
  "build_number": 42,
  "branch": "main",
  "status": "FAILURE",
  "total_tests": 85,
  "passed_tests": 84,
  "failed_tests": 1
}
```
*Note: A `FAILURE` payload automatically files an automated blocker defect in BugFlow.*

---

## 7. Notifications

- **List In-App Notifications:** `GET /api/v1/notifications`
- **Mark Notification Read:** `POST /api/v1/notifications/{id}/read`
- **Unread Count:** `GET /api/v1/notifications/unread-count`

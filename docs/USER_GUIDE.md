# BugFlow User Guide

Welcome to **BugFlow**, the enterprise-grade defect tracking, workflow automation, and productivity analytics system.

---

## Canonical Project Personas

BugFlow features four canonical role personas:

| Persona | Canonical Name | System Role | Primary Responsibilities |
|---|---|---|---|
| **Admin** | **Naruto** | `admin` | Triage, assignment, sprint planning, analytics, integrations, user management |
| **Developer** | **Sasuke** | `developer` | Defect investigation, code implementation, PR linking, work updates |
| **Tester** | **Hinata** | `tester` | Defect verification, regression testing, QA signoff, bug filing |
| **Senior Developer** | **Itachi** | `senior_dev` | Architecture review, code review, escalations, resolution approval |

There is **one real authenticated Admin account** (`admin@example.com`). The Admin switches between workspaces using the built-in **Switch Workspace** feature to interact as each persona without modifying underlying user credentials.

---

## 1. Authentication & Login

1. Navigate to `http://127.0.0.1:8080/login-ui`.
2. Enter your credentials:
   - **Email:** `admin@example.com`
   - **Password:** `Admin@123`
3. Click **Sign In**.
4. You will be authenticated with a persistent session and directed to the **Admin Dashboard** (`/admin-ui`).

---

## 2. Switching Workspace

1. In the top-right header of any administrative view, locate the **Switch Workspace** dropdown button.
2. Select your desired persona context:
   - **Naruto (Admin):** Loads `/admin-ui`
   - **Sasuke (Developer):** Loads `/developer-ui`
   - **Hinata (Tester):** Loads `/tester-ui`
   - **Itachi (Senior Developer):** Loads `/senior-developer-ui`
   - **User:** Loads `/user-ui`
3. The server immediately registers your active workspace context.

---

## 3. Reporting a Defect

*(Performed by: End User, Tester Hinata, or Admin Naruto)*

1. Navigate to `/user-ui` (or click **Report Defect** in the sidebar).
2. Fill out the defect form:
   - **Title:** Brief summary of the bug.
   - **Category:** Backend, Frontend, Database, API, Security, UI.
   - **Priority:** Low, Medium, High, Urgent.
   - **Severity:** MINOR, MAJOR, CRITICAL, BLOCKER.
   - **Environment:** Production, Staging, QA.
   - **Reproduction Steps:** Step-by-step instructions.
   - **Expected vs Actual Results:** What should happen vs what actually happened.
3. Click **Submit Defect Report**.
4. The defect is recorded with status `Pending` and queued for Admin triage.

---

## 4. Viewing Defects

- **All Defects Catalog (`/all-defects-ui`):** View, search, and filter all system defects by keyword, category, priority, or status.
- **Role-Specific Assigned Defects:**
  - Developer: `/developer-defects-ui`
  - Tester: `/tester-defects-ui`
  - Senior Developer: `/senior-developer-defects-ui`
- **My Defects (`/user-ui`):** View defects reported by your user account.

---

## 5. Admin Assignment Workflow

*(Performed by: Admin Naruto)*

1. Navigate to `/all-defects-ui` or `/team-collaboration-ui`.
2. Select the pending defect.
3. In the assignment panel, select the target role:
   - **Developer (Sasuke)**
   - **Tester (Hinata)**
   - **Senior Developer (Itachi)**
4. Click **Assign Defect**.
5. **Critical Behavior:** The defect status transitions to `ASSIGNED`. The defect is NOT resolved automatically.

---

## 6. Accept / Reject Workflow

*(Performed by: Assigned Persona)*

Once a defect is assigned:
1. The assigned persona opens the defect details.
2. Two action buttons appear:
   - **Accept Ownership:** Transitions status to `ACCEPTED`. Work begins.
   - **Reject Ownership:** Transitions status to `REJECTED`. The assignee must provide a rejection rationale.
3. **Strict Workflow Rule:** If a defect is marked `REJECTED`, resolution is strictly blocked until the defect is reassigned or triaged again.

---

## 7. Developer Workflow (Sasuke)

1. Open `/developer-ui`.
2. Inspect your **Assigned Defects** queue.
3. Accept the defect assignment.
4. Update work progress via the Work panel:
   - Select status: `IN_PROGRESS`.
   - Enter progress percentage (e.g. 75%).
   - Add implementation notes.
5. Reference commits using `[CODE_REFERENCE]` or GitHub commit hashes.
6. Once implementation is ready, notify testing.

---

## 8. Tester Workflow (Hinata)

1. Open `/tester-ui`.
2. Inspect defects marked for QA verification.
3. Execute verification test cases against the affected environment.
4. Record test progress:
   - Select status: `IN_TESTING`, `PASSED`, or `FAILED`.
   - Attach test execution screenshots or logs.
5. If verification passes, sign off for Senior Developer review.

---

## 9. Senior Developer Review (Itachi)

1. Open `/senior-developer-ui`.
2. Inspect defects in `IN_REVIEW`.
3. Review code references, architectural impact, and test results.
4. Select review outcome:
   - `APPROVED`: Authorizes final resolution.
   - `REVISION_REQUESTED`: Sends back to Developer with actionable review feedback.
   - `BLOCKED`: Identifies dependency blocks.

---

## 10. Resolving a Defect

*(Performed by: Admin Naruto or Authorized Lead)*

1. Once the defect is `ACCEPTED`, verified, and approved:
2. Open the defect in `/team-collaboration-ui`.
3. Click **Resolve Defect**.
4. Enter the resolution summary (e.g., "Patched query index and updated transaction handling").
5. The defect status transitions to `RESOLVED`.
6. Mean Time to Resolution (MTTR) is updated live in the analytics engine.

---

## 11. Comments & Collaboration

1. In `/team-collaboration-ui`, scroll to the **Discussion & Activity** section.
2. Enter your comment in the text area.
3. Click **Post Comment**.
4. All comments are timestamped and tagged with your persona badge.

---

## 12. Attachments

1. In the defect details view, locate the **Attachments** section.
2. Click **Choose File** and select an image (`.png`, `.jpg`), log file (`.txt`, `.log`), or document (`.pdf`).
3. Click **Upload Attachment**.
4. Files are securely stored in `app/uploads/attachments/` and downloadable via `/api/v1/collaboration/attachments/{id}/download`.

---

## 13. Code References

BugFlow supports traceable code references in comments:

Syntax:
```text
[CODE_REFERENCE] path/to/file.py|line_number|Description of reference
```
Example:
```text
[CODE_REFERENCE] app/analytics_engine.py|120|DSI calculation formula reference
```
When submitted, BugFlow renders this as an interactive, clickable code reference card.

---

## 14. Sprint Management (Milestone 2)

1. Open `/milestone2-ui` from the sidebar.
2. View active, planning, and completed sprint columns.
3. Click **Create Sprint** to launch a new iteration with goals and start/end dates.
4. Drag or assign backlog defects directly into the sprint.
5. View sprint velocity and burndown charts via the Sprint Analytics panel.

---

## 15. Analytics Reports (Module 3 & 4)

1. Open `/analytics-ui`.
2. Review real-time KPIs calculated directly from PostgreSQL:
   - **Defect Severity Index (DSI):** Weighted quality score (1.0 - 4.0).
   - **Mean Time to Resolution (MTTR):** Average hours to resolve bugs.
   - **CI/CD Pipeline Pass Rate:** Automated build health.
   - **Daily Defect Trend:** Arrival vs resolution line chart.
   - **Role Workload Share:** Distribution of assigned issues.
   - **Status, Priority & Category Distribution:** Multi-dimensional charts.

---

## 16. Productivity Analytics (Module 4)

In `/analytics-ui`, scroll to **Section 13: Team Productivity Analytics**:

- Factual productivity metrics across Naruto, Sasuke, Hinata, and Itachi:
  - **Issues Assigned:** Total workload assigned to each persona.
  - **Issues Accepted:** Count of accepted defects.
  - **Issues Resolved:** Count of resolved defects.
  - **Open Backlog:** Active defects currently in their court.
  - **Resolution Rate (%):** Percentage of assigned issues resolved.
  - **Average Turnaround:** Mean hours to resolution per role.
- **Workflow Funnel (Section 14):** Visualizes throughput across Reported -> Assigned -> Accepted -> Testing -> Resolved.

---

## 17. GitHub Integration

1. Open `/integrations-ui`.
2. Inspect synced commits, branch names, and authors.
3. To trigger a manual sync:
   - Enter repo name, commit hash, and message with issue reference (e.g. `Fix auth bug (refs #1)`).
   - Click **Trigger Manual Sync**.
4. BugFlow links the commit to the defect and updates the activity history.

---

## 18. CI/CD Integration

1. In `/integrations-ui`, inspect automated build pipeline runs.
2. Click **Simulate Pipeline Run** to test integration.
3. If a pipeline run fails, BugFlow automatically creates a high-priority defect and logs the build details.

---

## 19. REST API Explorer

1. Navigate to `/api-explorer-ui`.
2. Select any endpoint category: Issues, Assignment, Workflow, Sprints, Analytics, Integrations.
3. Click **Send Request** to test the live API and view raw JSON responses.

---

## 20. Advanced Report Exports

From `/analytics-ui` or directly via API:

- **Export CSV:** `/api/v1/analytics/export/csv` — Full defect dump.
- **Export JSON:** `/api/v1/analytics/export/json` — System analytics JSON.
- **Executive Summary:** `/api/v1/analytics/export/summary` — Printable executive report.
- **Productivity Report:** `/api/v1/analytics/export/productivity` — Team metrics CSV.
- **Workflow Report:** `/api/v1/analytics/export/workflow` — Funnel throughput CSV.
- **Sprint Report:** `/api/v1/analytics/export/sprint` — Sprint backlog CSV.

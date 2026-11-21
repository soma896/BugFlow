# BugFlow Live Deployment Guide (Render)

This guide walks you through deploying **BugFlow – Intelligent Software Defect Tracking System** from your local machine to **Render** with a live PostgreSQL database and automated seed data initialization.

---

## 📋 Table of Contents
1. [Overview & Architecture](#1-overview--architecture)
2. [Prerequisites](#2-prerequisites)
3. [Deployment Files Overview](#3-deployment-files-overview)
4. [Step-by-Step Deployment Options](#4-step-by-step-deployment-options)
   - [Option A: One-Click Blueprint (Recommended)](#option-a-one-click-blueprint-recommended)
   - [Option B: Manual Web Service + PostgreSQL Setup](#option-b-manual-web-service--postgresql-setup)
5. [Database Seeding & Verification](#5-database-seeding--verification)
6. [Default Login Credentials](#6-default-login-credentials)
7. [Post-Deployment Verification Checklist](#7-post-deployment-verification-checklist)
8. [Troubleshooting & FAQs](#8-troubleshooting--faqs)

---

## 1. Overview & Architecture

BugFlow runs as a single unified service:
- **Backend:** FastAPI (Python 3.11) with Uvicorn ASGI server.
- **Frontend:** Responsive Tailwind / HTML5 templates served directly by FastAPI under `/app/Frontend`. All frontend API calls use relative paths (`/api/v1/...`), ensuring they adapt dynamically to any live custom domain or Render URL (`https://<your-service>.onrender.com`).
- **Database:** PostgreSQL database via SQLAlchemy and `psycopg2-binary`.
- **Auto-Seeder (`init_live_db.py`):** On startup, detects if tables exist; if unpopulated, automatically seeds all canonical users, defects, issues, sprints, and admin actions from `seed_data.json` and synchronizes PostgreSQL ID sequences.

---

## 2. Prerequisites

1. A **GitHub** account with push access to the repository: `https://github.com/soma896/BugFlow.git`.
2. A free account at **[Render.com](https://render.com/)**.
3. Git installed and configured locally.

---

## 3. Deployment Files Overview

The following production files are already configured and ready in the repository:

| File | Purpose |
| :--- | :--- |
| `render.yaml` | Infrastructure as Code (Blueprint) for auto-provisioning PostgreSQL + Web Service |
| `Procfile` | Specifies the production web dyno command |
| `init_live_db.py` | Auto-seeds database schema, records, and serial sequences on first run |
| `seed_data.json` | 52 canonical defects, 13 issues, 6 sprints, 3 users, 67 admin actions |
| `requirements.txt` | Production dependencies (FastAPI, Uvicorn, psycopg2-binary, etc.) |
| `app/database.py` | Detects `DATABASE_URL` environment variable with fallback for local testing |
| `app/main.py` | Automatically redirects root `/` to `/login-ui` for web visitors |

---

## 4. Step-by-Step Deployment Options

### First Step: Commit & Push Your Changes to GitHub

Run these commands in your PowerShell terminal:

```powershell
# Check current status
git status

# Stage all deployment and updated files
git add app/database.py app/main.py requirements.txt Procfile Dockerfile init_live_db.py render.yaml seed_data.json DEPLOYMENT.md

# Commit
git commit -m "feat: configure live deployment for Render with auto-seeding database"

# Push to your working branch (or main)
git push origin ui-enhancement
```

*(If you wish to merge `ui-enhancement` into `main`, you can create a PR or merge it directly. Render can deploy from either `ui-enhancement` or `main`.)*

---

### Option A: One-Click Blueprint (Recommended)

Render Blueprints read the included `render.yaml` and provision both the PostgreSQL database and the Web Service with zero manual variable wiring.

1. Log into your [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** (top right) and select **Blueprint**.
3. Connect your GitHub account and select the **BugFlow** repository (`soma896/BugFlow`).
4. Select the branch: `ui-enhancement` (or `main`).
5. Render will detect `render.yaml` and display two components:
   - **bugflow-db**: PostgreSQL Database (Free tier)
   - **bugflow-web**: Web Service (Python 3)
6. Click **Apply**.
7. Render will automatically:
   - Create and provision the PostgreSQL database.
   - Connect the database connection string (`DATABASE_URL`) to the web service.
   - Run `pip install -r requirements.txt`.
   - Execute `python init_live_db.py` to create tables and import all canonical defects and users.
   - Start Uvicorn on the allocated `$PORT`.
8. Once the build completes (usually 1-2 minutes), click your live Web Service URL:
   `https://bugflow-web.onrender.com`

---

### Option B: Manual Web Service + PostgreSQL Setup

If you prefer to configure the services manually on Render:

#### Step 1: Create the Managed PostgreSQL Database
1. In Render Dashboard, click **New +** -> **PostgreSQL**.
2. Set the fields:
   - **Name:** `bugflow-db`
   - **Database:** `bugfinding`
   - **User:** `postgres`
   - **Region:** Choose closest to you (e.g., Oregon, Frankfurt, Singapore)
   - **Plan:** Free
3. Click **Create Database**.
4. Once created, copy the **Internal Database URL** (e.g., `postgres://postgres:...@dpg-...:5432/bugfinding`).

#### Step 2: Create the Web Service
1. Click **New +** -> **Web Service**.
2. Connect your **BugFlow** GitHub repository.
3. Select branch: `ui-enhancement`.
4. Configure the settings:
   - **Name:** `bugflow-web`
   - **Runtime:** `Python 3`
   - **Region:** Same region as your database
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python init_live_db.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Under **Environment Variables**, click **Add Environment Variable**:
   - Key: `DATABASE_URL`
   - Value: Paste the **Internal Database URL** copied from Step 1.
   *(Note: If the URL starts with `postgres://`, `app/database.py` automatically converts it to `postgresql+psycopg2://` for SQLAlchemy compatibility.)*
6. Click **Create Web Service**.

---

## 5. Database Seeding & Verification

When the Web Service boots up, `python init_live_db.py` executes before the server starts:
- It connects to your Render PostgreSQL instance.
- Creates all required tables (`users`, `issues`, `defects`, `sprints`, `sprint_issues`, `admin_actions`, `audit_logs`).
- If the tables are empty, it reads `seed_data.json` and inserts:
  - **3 Users** (Admin, Manoj, Soma Sekhar)
  - **6 Sprints**
  - **13 Issues**
  - **52 Defects**
  - **10 Sprint Issues**
  - **67 Admin Actions**
  - **408 Audit Logs**
- Resets and aligns PostgreSQL's auto-increment sequences (`setval`) so newly created defects get incremented IDs without collisions.
- If records already exist, it skips seeding harmlessly, preserving any newly created data across restarts.

---

## 6. Default Login Credentials

Use the following verified credentials to log in to your live BugFlow Aroma workspaces:

| Role | Email (Primary / Alias) | Password | Target Workspace |
| :--- | :--- | :--- | :--- |
| **👑 Admin (System Administrator)** | `admin@bugflow.io` / `admin@example.com` | `Admin@123` *(or `admin123`)* | Admin Control Center (`/admin-ui`) |
| **⚡ Senior Developer** | `senior@bugflow.io` / `senior_dev@example.com` | `Senior@123` *(or `senior123`)* | Senior Developer Workspace (`/senior-developer-ui`) |
| **💻 Developer** | `dev@bugflow.io` / `developer@example.com` | `Developer@123` *(or `dev123`)* | Developer Workspace (`/developer-ui`) |
| **🧪 QA Tester** | `tester@bugflow.io` / `tester@example.com` | `Tester@123` *(or `tester123`)* | QA Tester Workspace (`/tester-ui`) |

---

## 7. Post-Deployment Verification Checklist

Once your deployment status is **Live**:

1. **Root URL Navigation:**
   - Open `https://<your-service>.onrender.com/` in your browser.
   - Verify that it automatically redirects to `/login-ui`.
2. **Login Verification:**
   - Log in with `admin@example.com` / `Admin@123`.
   - Verify redirection to `/admin-ui`.
3. **Defects Verification:**
   - Navigate to `/all-defects-ui`.
   - Verify all 52 defects are loaded properly with pagination and filters.
4. **Reports & Analytics:**
   - Check **Productivity Report** (`/productivity-report-ui`).
   - Check **Workflow Report** (`/workflow-report-ui`).
   - Test CSV export button to ensure downloaded CSV files contain actual records.
5. **Team Collaboration:**
   - Visit `/team-collaboration-ui` and verify issues and active sprint data load.

---

## 8. Troubleshooting & FAQs

### Q: Render shows `Application failed to respond` or timeout during build.
- **Cause:** Large builds or slow network on free tier.
- **Solution:** Render free tier cold-starts in 30-50 seconds when inactive. Give it 1 minute on first visit.

### Q: `sqlalchemy.exc.NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:postgres`
- **Cause:** Old dialect name `postgres://`.
- **Solution:** Already handled! `app/database.py` contains a built-in regular expression handler that transforms `postgres://` to `postgresql+psycopg2://` seamlessly.

### Q: Free tier spin-down behavior
- Render free Web Services spin down after 15 minutes of inactivity. The first request after spin-down may take ~45 seconds to wake up. PostgreSQL free database data persists across spin-downs.

---
*BugFlow is now ready for production! 🚀*

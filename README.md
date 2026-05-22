# Enterprise Compliance Workflow System

A robust backend for managing employee expense claims, featuring automated fraud detection, strict RBAC, and AI-powered invoice reconciliation.

## 🚀 Architectural Design & Constraints

This system is built with a focus on **Auditability** and **Data Integrity**.

### 1. Security & Ownership (New Policy)
- **Strict Evidence Ownership:** Evidence can only be deleted by its uploader or the parent claim owner, and ONLY while the claim is in `DRAFT` or `CHANGES_REQUESTED` state.
- **RBAC Enforcement:** Reviewers and Controllers are explicitly barred from modifying or deleting evidence to preserve the audit trail (Assignment Brief lines 73/89).

### 2. Fraud Detection: Evidence Reuse Hashing
- Instead of relying on filenames, the system uses **SHA256 Content Hashing**.
- If a file is uploaded that matches an existing record's hash, it is automatically flagged as a "Reuse" event. This prevents "Double-Dipping" fraud where multiple employees use the same receipt.

### 3. AI-Powered Reconciliation (GEMINI 3 FLASH PREVIEW)
- Integrated **Google Gemini AI** for multimodal receipt analysis.
- The `ai-verify` endpoint extracts line items and totals directly from images/PDFs and compares them with the user-submitted claim amount.

### 4. Database Integrity
- **Optimistic Locking:** Uses a `version` column to prevent race conditions during concurrent approval workflows.
- **Audit Trails:** Every status change and manual/AI validation is logged in an append-only audit table.

---

## 🛠️ Setup Instructions

### Step 1: Environment Setup
```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
pip install google-generativeai
```

### Step 2: Configuration
Create a `.env` file in the root directory:
```env
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>/<dbname>?ssl=require
GEMINI_API_KEY=your_gemini_api_key_here
```

### Step 3: Run Database Migrations
```bash
alembic upgrade head
```

### Step 4: Seed the Database
Run the seed scripts **in order** to populate initial users:

#### 4a. Seed Basic Employee (`seed.py`)
Creates a single test employee user (ID: 1).
```bash
.\venv\Scripts\python seed.py
```
**Creates:**
| ID | Name | Email | Role |
|----|------|-------|------|
| 1 | Test Employee | employee@example.com | EMPLOYEE |

#### 4b. Seed RBAC Users (`seed_rbac.py`) ✅ Recommended
Creates all three role types using the ORM layer with duplicate-safe logic.
```bash
.\venv\Scripts\python seed_rbac.py
```
**Creates:**
| Name | Email | Role |
|------|-------|------|
| Employee One | emp1@company.com | EMPLOYEE |
| Reviewer One | rev1@company.com | REVIEWER |
| Controller One | ctl1@company.com | CONTROLLER |

#### 4c. Seed via Raw SQL (`seed_raw.py`) — Optional
Alternative to `seed_rbac.py` using direct SQL. Use this only if ORM seeding fails.
```bash
.\venv\Scripts\python seed_raw.py
```
**Creates:**
| Name | Email | Role |
|------|-------|------|
| Reviewer One | rev1@company.com | REVIEWER |
| Controller One | ctl1@company.com | CONTROLLER |

> **Note:** All seed scripts are safe to run multiple times — they use `ON CONFLICT DO NOTHING` / existence checks to avoid duplicates.

### Step 5: Start the Server
```bash
.\venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🧪 Key Endpoints

Access the full interactive API docs at: **http://localhost:8000/docs**

All endpoints require `X-User-Id` header (use seeded user IDs from above).

| Endpoint | Method | Role Required | Description |
|----------|--------|---------------|-------------|
| `/api/v1/claims` | POST | EMPLOYEE | Create a new expense claim |
| `/api/v1/claims/{id}/evidence` | POST | EMPLOYEE | Upload evidence/receipt |
| `/api/v1/evidence/{id}/ai-verify` | POST | Any | AI receipt amount verification |
| `/api/v1/claims/{id}/approve` | POST | REVIEWER | Approve a claim |
| `/api/v1/claims/{id}/audit-report` | GET | CONTROLLER | Full audit trail report |

---

*Developed as part of the Senior Backend Developer Assignment.*

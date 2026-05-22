# One-Page Submission Summary
## Enterprise Compliance Workflow System

---

## What Was Built

A production-grade **async FastAPI backend** for managing employee expense claims through a multi-role approval workflow (Employee → Reviewer → Controller), with full audit traceability, fraud detection, and AI-powered invoice reconciliation.

---

## Architecture Overview

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI (async) |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL (via asyncpg) |
| Migrations | Alembic |
| AI | Google Gemini 1.5 Flash |
| Auth | Header-based RBAC (`X-User-Id`) |

---

## Four Core Constraints — How They Are Met

### 1. 🔒 Strict Audit Trail
Every state transition, evidence upload, deletion, amendment, and AI validation is inserted into an **append-only `audit_logs` table**. No UPDATE or DELETE is ever issued against this table. Each entry records: `actor_id`, `action`, `claim_id`, `old_value`, `new_value`, and `timestamp`.

### 2. 🔁 State Machine Enforcement
Claims follow a strict FSM: `DRAFT → PENDING_REVIEW → APPROVED / CHANGES_REQUESTED → PENDING_REVIEW → APPROVED`. Invalid transitions (e.g., approving a DRAFT directly) return HTTP 422. Transitions are validated in `ClaimService` before any DB write.

### 3. ⚡ Optimistic Concurrency Control
The `claims` table has a `version` INTEGER column. Every update increments the version and includes a `WHERE version = :expected` guard. If a concurrent update has already changed the version, the update affects 0 rows and a 409 Conflict is returned — preventing silent overwrites.

### 4. 📎 Amendment Integrity
Amendments create a **new record** in the `amendments` table referencing the original claim. The original claim's `amount` and `description` are never overwritten. The amendment stores `original_amount` and `amended_amount` separately, preserving the complete change history.

---

## Additional Features Implemented

| Feature | Detail |
|---------|--------|
| **Fraud Detection** | SHA-256 file hashing on every upload; duplicate files flagged as reuse events |
| **Evidence Ownership** | Only uploader/claim-owner can delete evidence; only in DRAFT or CHANGES_REQUESTED state |
| **AI Verification** | Gemini multimodal API extracts item totals from receipts and compares with claim amount |
| **RBAC Enforcement** | Role checks on every endpoint; Reviewers/Controllers cannot modify employee evidence |

---

## Key Design Decisions & Assumptions

- **Authentication:** Simplified to `X-User-Id` header per brief spec (no JWT required)
- **Amendment Approval:** Amendments are auto-approved by the Controller; no separate amendment state machine
- **Multiple Claims:** Employees can have multiple simultaneous claims in any state
- **Evidence on Non-Draft:** Evidence upload blocked on APPROVED/REJECTED claims to preserve integrity

---

## Running the Project

```bash
# 1. Install dependencies
pip install -r requirements.txt && pip install google-generativeai

# 2. Configure environment
cp .env.example .env  # Fill in DATABASE_URL and GEMINI_API_KEY

# 3. Run migrations & seed
alembic upgrade head
.\venv\Scripts\python seed_rbac.py   # Creates Employee, Reviewer, Controller users

# 4. Start server
.\venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 5. API Docs
open http://localhost:8000/docs
```

---

*Submitted by: Senior Backend Developer Candidate*

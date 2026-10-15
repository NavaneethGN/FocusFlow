# FocusFlow HLR Study Planner — Architecture, Implementation, Working Logic & Testing Report

This document is the master engineering report detailing the **architecture**, **implementation**, **working logic**, and **verification testing** of everything implemented in FocusFlow to date, along with a structured gap analysis of pending items from the final implementation plan.

---

## 1. System Vision & The Closed-Loop Architecture

The FocusFlow HLR Study Planner implements a closed-loop learning feedback cycle:

```
[1. Learn & Practice]
       │
       ▼
[2. Answer Quiz Questions] ──(event_id)──► [Attempts Table (Audit History)]
       │
       ▼
[3. Session Completed]
       │
       ├─────────────────────────────────► [Training Records (Immutable Snapshots)]
       ▼
[4. HLR Engine Updates]
       │  • Δ = (t_now - t_last) / 86400
       │  • h = 2^(θᵀ x)
       │  • p̂(Δ) = 2^(-Δ / h)
       │  • t_review = -h · log₂(τ)
       ▼
[5. Concept State Table] ◄─────────────── (Latest Memory State per Concept)
       │
       ▼
[6. Study Scheduler Engine]
       │  • Urgency (1 - p̂)
       │  • Subject weights & Exam proximity
       │  • Daily time-budget allocation
       ▼
[7. Student Study Plan (Today & Week)]
       │
       ▼
[8. Offline ML Training Pipeline] ──────► [Evaluates & Promotes Candidate Weights]
```

### Separation of Concerns
1. **HLR Engine (`backend/hlr/`)**: Estimates memory retention and decay. It has no awareness of daily time budgets or calendar deadlines.
2. **Study Scheduler (`backend/scheduler/`)**: Converts retention estimates and deadlines into practical daily/weekly study allocations.
3. **Learning Pipeline (`backend/learning/`)**: Groups answer attempts, computes session performance, and guarantees transaction-safe state transitions.
4. **ML Operations (`backend/ml/`, `backend/jobs/`)**: Trains candidate weights from historical data and gates model promotions.
5. **Storage Layer (`backend/repositories/`, `backend/app/models/`)**: Distinguishes immutable historical events (`attempts`) from latest point-in-time state estimates (`concept_state`).

---

## 2. Detailed Implementation Breakdown

### Module 1: Core HLR Mathematical Engine (`backend/hlr/`)
* **What Was Built:**
  - `features.py`: Feature vector extraction with support for:
    - `V1`: $x = [1.0, \text{correct}, \text{incorrect}]$
    - `V2`: $x = [1.0, \sqrt{\text{correct}}, \sqrt{\text{incorrect}}]$
    - `V3`: $x = [1.0, \sqrt{\text{correct}}, \sqrt{\text{incorrect}}, \text{difficulty\_weight}]$
  - `predictor.py`: Half-life prediction $\hat{h} = 2^{\theta^\top x}$ and recall probability $\hat{p}(\Delta) = 2^{-\Delta / \hat{h}}$, with numerical bounds $[-20, 20]$ on exponent dot products and probability clamping $[0.01, 0.99]$.
  - `review_policy.py`: Calculates target review intervals $t_{\text{review}} = -\hat{h} \log_2(\tau)$ where $\tau = 0.7$.
  - `updater.py`: Pure functional state update taking current state and session accuracy to return updated counts, elapsed days $\Delta$, new half-life, and review timestamps.
  - `trainer.py`: L-BFGS-B and Scipy optimization minimizing regularized squared prediction error:
    $$\mathcal{L}(\theta) = \frac{1}{N}\sum_{i=1}^N \left(p_i - 2^{-\Delta_i / 2^{\theta^\top x_i}}\right)^2 + \frac{\lambda}{2}\|\theta\|_2^2$$
  - `evaluation.py`: Computes MAE, RMSE, Pearson Correlation ($r$), Expected Calibration Error (ECE), Brier Score, and Wilcoxon signed-rank significance tests.
* **How It Was Built:** Standalone Python modules using NumPy and SciPy with zero web framework or database dependencies.
* **Purpose:** Forms the mathematical core that powers spaced repetition and memory decay modeling.
* **How to Test:** Run `pytest backend/tests/test_features.py backend/tests/test_predictor.py backend/tests/test_review_policy.py backend/tests/test_updater.py backend/tests/test_trainer.py backend/tests/test_evaluation.py`.

---

### Module 2: Learning Pipeline & Session Processing (`backend/learning/`)
* **What Was Built:**
  - `session_aggregator.py`: Groups individual quiz answers by concept, calculates observed session accuracy $p = \frac{\text{correct}}{\text{total}}$, and computes elapsed days $\Delta$ since prior practice.
  - `training_record_builder.py`: Captures pre-update feature snapshots ($x_{\text{before}}$) and writes immutable training examples containing $(p, \Delta, x_{\text{before}}, \text{student\_id}, \text{concept\_id}, \text{model\_version})$.
* **How It Was Built:** Python service classes that interface with storage repository abstractions.
* **Purpose:** Ensures raw answers are processed reliably into both updated states and reproducible training records.
* **How to Test:** Run `pytest backend/tests/test_session_complete.py backend/tests/test_answers_api.py`.

---

### Module 3: Study Scheduler Engine (`backend/scheduler/`)
* **What Was Built:**
  - `priority.py`: Calculates multi-factor priority scores:
    $$\text{Priority} = w_{\text{urgency}} \cdot (1 - \hat{p}) + w_{\text{subject}} \cdot S_w + w_{\text{exam}} \cdot e^{-\lambda \cdot d_{\text{exam}}}$$
  - `candidate_selector.py`: Categorizes concepts into `OVERDUE` ($\hat{p} < 0.7$), `DUE_SOON` ($0.7 \le \hat{p} < 0.85$), and `HEALTHY` ($\hat{p} \ge 0.85$).
  - `plan_generator.py`: Fits prioritized concepts into available daily time budgets (e.g. 30, 45, or 60 minutes), balancing urgent reviews (10–15 min) with new learning slots (15–20 min), and projects 7-day revision plans.
* **How It Was Built:** Python scheduling logic utilizing priority sorting and time-budget allocation.
* **Purpose:** Converts passive memory estimates into actionable, prioritized daily study tasks for the student.
* **How to Test:** Run `pytest backend/tests/test_scheduler.py`.

---

### Module 4: ML Operations, Model Registry & Student Simulator (`backend/ml/`, `backend/jobs/`)
* **What Was Built:**
  - `dataset_builder.py`: Extracts stored `TrainingRecord` rows, applies data quality filters, and constructs train/validation/test matrices.
  - `model_registry.py`: Versioned storage for model weights ($\theta$), feature specifications, training metadata, and active pointer tracking.
  - `promotion.py`: Enforces promotion criteria (candidate model must improve validation MAE/RMSE over the baseline by at least $\epsilon = 0.01$ without regressions).
  - `simulator.py`: Synthetic student cohort simulator modeling forgetting curves, knowledge states, and quiz interactions across 30–90 virtual days.
  - `training_job.py` & `monitoring_job.py`: Batch operational jobs for scheduled training and drift monitoring.
* **How It Was Built:** ML pipeline scripts integrated with repository interfaces.
* **Purpose:** Enables systematic, safe weight optimization from collected student data.
* **How to Test:** Run `pytest backend/tests/test_registry.py backend/tests/test_simulator.py backend/tests/test_jobs_admin.py`.

---

### Module 5: Storage Layer & Repositories (`backend/repositories/`, `backend/app/models/`)
* **What Was Built:**
  - `repositories/base.py`: Abstract interfaces for `UnitOfWork`, `ConceptStateRepository`, `AttemptRepository`, `TrainingRecordRepository`, `ModelVersionRepository`, and `SessionRepository`.
  - `repositories/memory.py`: In-memory thread-safe repository for unit testing and fast benchmarking.
  - `repositories/postgres.py`: SQLAlchemy implementation supporting PostgreSQL and SQLite.
  - `app/models/models.py`: Relational models: `User`, `UserSettings`, `Subject`, `Topic`, `Material`, `Concept`, `Question`, `Session`, `Attempt`, `ConceptState`, `TrainingRecord`, `ModelVersion`.
  - `alembic/versions/b0038fb276f4_create_hlr_persistence_tables.py`: Database migration script.
* **How It Was Built:** SQLAlchemy 2.0 ORM with Alembic schema migrations.
* **Purpose:** Enforces data integrity, event idempotency (`event_id` constraint), and historical auditability.
* **How to Test:** Run `pytest backend/tests/test_repositories.py`.

---

### Module 6: Backend API Layer (`backend/main.py`, `backend/app/routers/`)
* **What Was Built:**
  - FastAPI application with dual-compatibility dispatching for both persistent database entities and in-memory test benchmarks.
  - Core endpoints implemented:
    - `POST /api/materials`: Upload study materials with Google Gemini AI question generation.
    - `GET /api/concepts`: List concepts with real-time half-life and recall estimates.
    - `GET /api/questions`: Retrieve quiz questions for specific concepts.
    - `POST /api/quizzes/start`: Start a quiz session.
    - `POST /api/sessions/{id}/answers`: Record answer attempts idempotently.
    - `POST /api/sessions/{id}/complete`: Finalize session and trigger HLR state updates.
    - `GET /api/dashboard`: Student summary metrics and retention status.
    - `GET /api/plan/today` & `GET /api/plan/week`: Retrieve study schedules.
    - `GET /api/concepts/{id}/curve`: Retrieve 30-day forgetting curve coordinate points.
    - `GET /api/concepts/{id}/learning-state`: Detailed HLR mathematical state.
    - `GET /api/health`: Health check and system status.
    - `POST /api/admin/training/run` & `POST /api/admin/monitoring/run`: Admin batch triggers.
  - `app/services/quiz_gen.py`: Google Gemini AI question generator with structured fallback.
* **How It Was Built:** FastAPI, Pydantic v2 schemas, and dependency injection.
* **Purpose:** Coordinates HTTP requests, runs application logic, and interfaces with the HLR and scheduler engines.
* **How to Test:** Run `pytest backend/tests/test_api.py backend/tests/test_hlr.py backend/tests/e2e/test_hlr_closed_loop.py`.

---

### Module 7: Frontend Application (`frontend/src/`)
* **What Was Built:**
  - `main.jsx`: Full Single Page Application (SPA) with:
    - **Dashboard**: Metric cards for retention health, overdue items, and study progress.
    - **Concept Explorer**: Filterable concepts with real-time recall bars and half-life badges.
    - **Interactive Forgetting Curve**: Dynamic SVG/Canvas chart displaying retention decay curves and review thresholds.
    - **Quiz Runner**: Interactive quiz interface with immediate answer feedback and session completion.
    - **Study Plan**: Prioritized daily study slots with time allocations.
    - **Material Uploader**: AI-powered study material upload with quiz generation.
    - **Settings**: Configuration for daily study minutes, subject priorities, and student profile switching.
  - `hlr.js`: Client-side mirrored HLR calculation functions (`calculateHalfLife`, `calculateRecallProbability`, `calculateReviewDate`, `generateForgettingCurvePoints`).
  - `hlr.test.js`: Vitest test suite running 58 assertions against cross-language test vectors (`hlr_test_vectors.json`).
* **How It Was Built:** React 18, Vite, Vanilla CSS design system with responsive layouts and dark mode.
* **Purpose:** Provides students with a modern, responsive interface for learning, self-assessment, and schedule management.
* **How to Test:** Run `npx vitest run` in `frontend/`.

---

## 3. How to Test the Entire System

### Summary of Test Suites

| Test Suite | Command | Number of Tests | Purpose |
| :--- | :--- | :---: | :--- |
| **Self-Checking Terminal Script** | `python backend/demo_hlr.py` | **26 Checks** | Instant terminal validation of math, sessions, and plans |
| **Full Backend Pytest** | `pytest backend/tests -v` | **157 Tests** | Complete coverage of HLR, DB, API, and E2E simulation |
| **Frontend Unit Tests** | `npx vitest run` | **58 Tests** | Cross-language parity test of `hlr.js` with Python |
| **Frontend Production Build** | `npm run build` | **Build Check** | Validates compilation and asset bundling |

### Step-by-Step Testing Commands

1. **Terminal Quick Check (1 second):**
   ```powershell
   cd c:\Users\USER\FocusFlow\backend
   ..\.venv\Scripts\python demo_hlr.py
   ```
   *Expect: Exit code 0, all 26 checks passed.*

2. **Full Backend Pytest Suite:**
   ```powershell
   cd c:\Users\USER\FocusFlow\backend
   ..\.venv\Scripts\pytest -q
   ```
   *Expect: `157 passed in ~90s`.*

3. **Frontend Unit Tests:**
   ```powershell
   cd c:\Users\USER\FocusFlow\frontend
   npx vitest run
   ```
   *Expect: `58 passed in ~180ms`.*

4. **Verify Live Application in Browser:**
   - Ensure backend is running: `http://127.0.0.1:8000/api/health`
   - Open frontend: `http://127.0.0.1:5173`
   - Test flow: Select a student $\to$ View Dashboard $\to$ Open Concept Explorer $\to$ Inspect Forgetting Curve $\to$ Start a Quiz $\to$ Submit answers $\to$ Verify updated recall and study plan.

---

## 4. Pending Implementations from the Master Architecture Plan

The core mathematical, computational, algorithmic, and functional layers are complete. Below is a structured overview of what remains to be implemented to fulfill all aspects of the master plan:

### 1. Frontend Modernization & Component Architecture
- **TypeScript Conversion**: Migrate `main.jsx` into modular TypeScript files (`Dashboard.tsx`, `QuizRunner.tsx`, `ConceptExplorer.tsx`, `StudyPlan.tsx`).
- **Tailwind CSS & shadcn/ui**: Replace custom CSS in `styles.css` with Tailwind utility classes and accessible shadcn/ui primitives (dialogs, cards, progress bars).
- **Server State Management**: Introduce TanStack Query (React Query) for automated query caching, refetching, and optimistic UI updates on answer submissions.

### 2. Production Authentication & User Identity
- **JWT / Supabase Auth**: Replace the development `X-Student-Id` header with full JSON Web Token (JWT) or Supabase authentication.
- **User Registration & Security**: Add user signup, password hashing (bcrypt), password reset flows, and authorization guards separating students from administrators.

### 3. Automated Asynchronous Background Workers
- **Cron / Asynchronous Scheduling**: Move `training_job.py` and `monitoring_job.py` from manual HTTP endpoints to background workers using Celery, APScheduler, or Cloud Scheduler.
- **Model Drift Alerting**: Implement automated alerting (via Slack/webhook/email) when model calibration (ECE) or prediction errors exceed acceptable thresholds.

### 4. Monorepo Reorganization & Deployment Packaging
- **Monorepo Directory Layout**: Reorganize the project into the suggested monorepo layout:
  ```
  apps/web/        (Vite + React frontend)
  apps/api/        (FastAPI backend)
  packages/shared/ (Shared TypeScript interfaces & schemas)
  infra/docker/    (Docker compose & Dockerfiles)
  ```
- **Playwright End-to-End Browser Tests**: Implement automated browser tests covering the full student journey.
- **Production Cloud Deployment**: Configure deployment manifests for Vercel/Netlify (frontend) and Render/Fly.io (backend), along with GitHub Actions CI/CD workflows.

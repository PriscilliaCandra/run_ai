# Design and Evaluation of an AI-Based Personalized Running Training Recommendation System

> **Academic Thesis Prototype**  
> Master of Information Technology (S2) — BINUS University  
> **Topic:** Hybrid Decision-Support System for Endurance Running (Rule-Based Physiology + Modular Large Language Model)

---

## 1. Research Overview & Problem Statement

Recreational runners frequently struggle with injury risk, overtraining, and poor goal attainment due to generic, static running plans found online. Conversely, unconstrained Generative AI / Large Language Models (LLMs) often hallucinate unsafe weekly volume spikes, inappropriate workout pacing, or physiologically flawed schedules.

This research prototype designs and evaluates a **Hybrid AI Architecture**:
1. **Deterministic Rule-Based Component:** Enforces established exercise physiology principles (Jack Daniels VDOT formulas, Stephen Seiler's 80/20 polarized training distribution, and the ≤10% safe weekly mileage increment rule).
2. **Modular LLM Component:** Personalizes the training plan by enriching structured workouts with context-aware warm-ups, step-by-step executions, cognitive pacing cues, and injury limitation adaptations.
3. **Research Evaluation Module:** Quantifies system effectiveness via 1–5 Likert scale instruments assessing *Personalization*, *Perceived Usefulness*, *Clarity*, and *Confidence in Following the Plan*.

---

## 2. System Architecture

```text
User / Runner Profile Input
           │
           ▼
[ React 19 + Vite + Tailwind CSS Frontend ]
           │
      (HTTP POST /api/plans/generate)
           ▼
[ FastAPI Backend Engine ]
           │
           ├─► 1. Runner Profile Validation (Pydantic)
           │      • Validates pace formats (MM:SS), distance bounds, realistic targets
           │
           ├─► 2. Rule-Based Physiological Engine
           │      • Jack Daniels VDOT formula calculation from 5K PB
           │      • Individualized pace zones (Easy, Tempo, Interval, Repetition)
           │      • 80/20 Polarized volume distribution & Long run cap (≤30% volume)
           │      • Safe periodization progression (≤10% weekly increase + cutback deloads)
           │
           ├─► 3. Modular LLM Personalization Service
           │      • Strict prompt constraints preserving physiological parameters
           │      • Supports Google Gemini, OpenAI, or Offline Heuristic Synthesizer
           │
           ├─► 4. SQLite Database Persistence
           │      • Anonymous runner profile (no PII stored)
           │      • Full JSON storage of Rule-Based Baseline vs AI-Personalized Plan
           │      • Evaluation Likert responses & qualitative comments
           │
           ▼
[ Frontend Visualization & Evaluation Dashboard ]
   • Interactive Weekly Calendar / Workout Cards
   • Baseline vs AI Plan Side-by-Side Comparison Toggle
   • Transparent "Why Was This Plan Generated?" Explainability Matrix
   • 1–5 Likert Evaluation Form & Live Statistical Analytics
```

---

## 3. Physiological Formulas (For Thesis Chapter 3)

### Jack Daniels VDOT Formulation
Given race distance $d$ (meters) and finish time $t$ (minutes):

$$\text{Velocity } v = \frac{d}{t} \quad (\text{m/min})$$

$$\text{VO}_2 = -4.60 + 0.182258 \cdot v + 0.000104 \cdot v^2$$

$$\% \text{VO}_2\max = 0.8 + 0.1894393 \cdot e^{-0.012778 \cdot t} + 0.2989558 \cdot e^{-0.1932605 \cdot t}$$

$$\text{VDOT} = \frac{\text{VO}_2}{\% \text{VO}_2\max}$$

Training paces are derived by inverting the quadratic curve at specific physiological zones:
- **Easy Aerobic (E):** $65\% - 74\% \text{ VO}_2\max$ (Capillary density, fat oxidation)
- **Threshold / Tempo (T):** $88\% \text{ VO}_2\max$ (Lactate clearance threshold)
- **Interval (I):** $98\% \text{ VO}_2\max$ (Cardiorespiratory stroke volume)

---

## 4. Database Schema (SQLite)

- **`runner_profiles`**: Anonymous runner profiles with fields `id` (UUID), `age`, `gender`, `experience_level`, `pb_5k`, `pb_10k`, `target_race_distance`, `target_race_time`, `current_weekly_mileage`, `training_days_per_week`, `preferred_training_days`, `plan_duration_weeks`, `injury_limitations`, `easy_run_pace`, `created_at`.
- **`training_plans`**: Generated plans with fields `id`, `runner_profile_id` (FK), `user_id` (FK, **nullable** -- NULL for an anonymous research plan, set for a consumer's own plan; see Section 8), `calculated_vdot`, `target_pace`, `rule_based_plan_json` (Text), `ai_plan_json` (Text), `explainability_summary` (Text), `ai_model_used`, `created_at`.
- **`plan_evaluations`**: Academic survey results with fields `id`, `training_plan_id` (FK), `personalization_score` (1-5), `usefulness_score` (1-5), `clarity_score` (1-5), `confidence_score` (1-5), `comments` (Text), `created_at`. Deliberately has no `user_id` -- research evaluations stay anonymous even for a logged-in consumer user.
- **`users` / `user_profiles` / `sessions` / `password_reset_tokens`**: consumer account tables, added in Phase 1 and fully described in Section 8. Schema is managed by Alembic (`backend/alembic/`) going forward, not `Base.metadata.create_all()`.

---

## 5. Quick Start Instructions (Local Execution)

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm

---

### Step 1: Start the Backend (FastAPI)

1. Open a terminal in `d:/research s2/backend`:
   ```powershell
   cd "d:/research s2/backend"
   ```

2. (Optional) Configure an LLM API key in `.env`:
   ```bash
   cp .env.example .env
   ```
   *Note: If you do not provide an API key, the prototype automatically uses its built-in Rule-Constrained AI Synthesis Fallback, meaning it runs 100% offline out-of-the-box!*

3. Install dependencies, apply database migrations, and run the automated backend test suite (pytest):
   ```powershell
   pip install -r requirements.txt
   alembic upgrade head
   pytest
   ```
   *`alembic upgrade head` is idempotent -- safe to run every time you pull new changes. It never drops or rewrites existing data (see Section 8.2). The pytest suite runs entirely against a private temporary SQLite database created per test run — it never reads or writes `running_research.db`.*

4. Launch the FastAPI server:
   ```powershell
   python -m uvicorn app.main:app --reload --port 8000
   ```
   *The interactive Swagger API documentation will be available at: `http://127.0.0.1:8000/docs`*

---

### Step 2: Start the Frontend (React + Vite)

1. Open a second terminal in `d:/research s2/frontend`:
   ```powershell
   cd "d:/research s2/frontend"
   ```

2. Launch the Vite development server:
   ```powershell
   npm run dev
   ```

3. Open your browser at:
   ```text
   http://localhost:5173
   ```

---

## 6. How to Use the Prototype for Thesis Evaluation

1. **Load Pre-Set Scenario:** On the *New Plan* page, click **"Load S2 Research Example"** to automatically populate the canonical test profile (Age 21, Intermediate, 5K PB 24:56, Target 5K 23:00, 25 km/wk, 4 days/wk, mild knee limitation).
2. **Generate Plan:** Click **"Generate Personalized Training Plan"**. The system executes the hybrid pipeline in < 1 second.
3. **Compare Plans:** On the *Plan Result* page, toggle between:
   - **✨ AI-Personalized Plan:** Review enriched warm-ups, step-by-step executions, and customized injury guidance.
   - **📐 Rule-Based Baseline:** Review the unaugmented mathematical Jack Daniels baseline.
4. **Inspect Explainability:** Scroll down to **"Why Was This Plan Generated?"** to review the explainability matrix for your thesis presentation.
5. **Submit Evaluation:** Click **"Evaluate This Plan"** to record Likert scale ratings (1 to 5) and qualitative feedback.
6. **Export Data:** Navigate to **"Survey Stats"** and click **"Export Research JSON"** to download the aggregated evaluation dataset for Chapter 4 analysis.

---

## 7. Research Reproducibility

This section documents what a reader of the thesis (or another researcher) needs in order to understand exactly what the system computed and reproduce the results.

### 7.1 Software Architecture

```
Runner Profile Input (validated by Pydantic)
        │
        ▼
Rule-Based Physiological Engine  (deterministic — app/rules/)
   VDOT → training pace zones → target race pace →
   weekly volume allocation (80/20 split, ≤30% long-run cap) →
   safe periodization progression (≤8-10%/week, cutback + taper weeks)
        │
        ▼
LLM Personalization Layer  (app/ai/)
   Sends the rule-based baseline + runner profile to Gemini/OpenAI (if configured),
   OR uses the built-in deterministic offline synthesizer (default, no API key needed)
        │
        ▼
Server-Side Validation  (app/ai/validator.py)
   Every AI-generated plan is checked against the rule-based baseline before
   it is trusted: workout count, workout type, distance, pace, intensity zone,
   weekly mileage, and rest/training day counts must all match. Any mismatch,
   schema error, or malformed JSON discards the AI output and falls back to
   the offline synthesizer. Raw LLM output is never returned to the client.
        │
        ▼
SQLite Persistence (anonymous) → REST API → React Frontend → Likert Evaluation
```

**Rule-Based Baseline** = the deterministic reference system. Given the same runner profile, it always produces the same VDOT, pace zones, and weekly plan.
**AI-Personalized Plan** = the LLM-enhanced version of that same baseline. It may reword, explain, and add warm-up/cooldown/pacing guidance, but it is mathematically constrained to the numbers the rule-based engine already computed — the validator rejects anything else.

### 7.2 Input Parameters

Collected via `RunnerProfileCreate` ([backend/app/schemas.py](backend/app/schemas.py)): age, gender, experience level, 5K personal best (MM:SS), optional 10K personal best (MM:SS), target race distance (5K/10K/Half Marathon), target race time, current weekly mileage (km), training days per week (1-7), preferred training days, plan duration (4-24 weeks), optional injury/limitation notes, and current easy-run pace. All time fields are validated as strict `MM:SS`.

### 7.3 Rule-Based Constraints

Implemented in [backend/app/rules/vdot.py](backend/app/rules/vdot.py) and [backend/app/rules/generator.py](backend/app/rules/generator.py):
- VDOT via the Daniels-Gilbert formula from the 5K personal best.
- Training pace zones (Easy 65-74%, Marathon 80%, Threshold 88%, Interval 98%, Repetition 105% of VDOT-equivalent velocity).
- Week 1 volume matches the runner's reported current weekly mileage (no acute spike).
- Long run capped at ~30% of weekly volume (bounded by a per-distance ceiling and a 4km floor).
- Weekly progression capped at ~8-10% per week, with a scheduled cutback (deload) week roughly every 4 weeks and a taper before race week.
- Single-training-day profiles are handled as one comprehensive aerobic session rather than being forced into a separate quality-workout day.

These are **prototype design heuristics**, not universally validated scientific laws — they are documented here so the thesis can cite them precisely as implemented, rather than as a general claim about exercise science.

### 7.4 AI Personalization Process

See [backend/app/ai/prompts.py](backend/app/ai/prompts.py), [backend/app/ai/llm_service.py](backend/app/ai/llm_service.py), and [backend/app/ai/validator.py](backend/app/ai/validator.py). The LLM is instructed to personalize only textual fields (warm-up/cooldown protocols, execution cues, pacing guidance, injury adaptation notes, and the coaching narrative) and to leave every numeric/structural field untouched. The validator then independently re-checks that this instruction was actually followed before the response is ever persisted or returned to the frontend.

### 7.5 Evaluation Dimensions

Four 1-5 Likert dimensions, collected separately for the Rule-Based Baseline and the AI-Personalized Plan via `evaluated_plan_type` ([backend/app/models.py](backend/app/models.py)):
1. Personalization
2. Perceived Usefulness
3. Clarity of workouts and paces
4. Confidence in following the plan

### 7.6 Statistical Metrics

`GET /api/evaluations/stats` ([backend/app/routes/evaluation_routes.py](backend/app/routes/evaluation_routes.py)) returns, **separately for each plan type** (never combined into one score):
- Sample size (N)
- Mean, median, and standard deviation per dimension
- A per-group overall mean across the 4 dimensions

Standard deviation is reported as `null` when N < 2 (undefined for a single observation), rather than a misleading `0.0`. The API never computes or exposes a combined "AI vs Rule-Based" score — any comparison between the two groups is left to the researcher's own statistical analysis of the exported data.

### 7.7 Running the Tests

```powershell
cd backend
pytest            # run once
pytest -v         # verbose, per-test output
```
The suite (`backend/tests/`) uses a private temporary SQLite database created fresh per test (see `tests/conftest.py`) and never touches `running_research.db`. Running it multiple times produces the same results every time.

### 7.8 Running the Application

See [Section 5](#5-quick-start-instructions-local-execution) above: `uvicorn app.main:app --reload --port 8000` for the backend, `npm run dev` for the frontend (`http://localhost:5173`).

### 7.9 Exporting Evaluation Data

On the **Survey Stats** page, click **"Export Research JSON"** to download the current `GET /api/evaluations/stats` payload (N/mean/median/SD per dimension for both plan types, plus recent qualitative comments) as a timestamped `.json` file for import into statistical software (e.g. R, SPSS, pandas) for Chapter 4 analysis.

---

## 8. Authentication Architecture & Security (Phase 1)

Phase 1 adds a multi-user consumer foundation on top of the research prototype. The research flow above is completely unchanged and requires no account; this section documents the new, separate authentication system. Full rationale and audit trail: [`PRODUCT_READINESS_AUDIT.md`](PRODUCT_READINESS_AUDIT.md) and `PHASE_1_REPORT.md`.

### 8.1 Identity Model

`users` (auth identity: email, password hash, display name) is deliberately separate from `user_profiles` (running-specific data) and from the anonymous research `runner_profiles` table. A consumer account is never linked to anonymous research submissions; the two datasets cannot be joined.

### 8.2 Database Migrations

Schema is managed by **Alembic** (`backend/alembic/`), not `Base.metadata.create_all()` (which can create tables but can't safely alter existing ones). Two migrations exist:
- `0001_baseline_research_schema` -- documents the schema that already existed (`runner_profiles`, `training_plans`, `plan_evaluations`); the live database was **stamped** to this revision (bookkeeping only, no DDL executed against existing data).
- `0002_add_auth_and_ownership` -- purely additive: creates `users`, `user_profiles`, `sessions`, `password_reset_tokens`, and adds a **nullable** `user_id` column to `training_plans`. Every existing research row keeps `user_id = NULL` and was verified byte-for-byte unchanged (row counts and content) before and after migration.

Run `alembic upgrade head` after pulling new migrations. Never run a destructive migration (`downgrade`) against a database with real data without a fresh backup.

### 8.3 Authentication Flow

- **Register** (`POST /api/auth/register`): email (normalized to lowercase, unique), password (Argon2-hashed via `argon2-cffi`; never plaintext or reversibly encrypted), display name (a pseudonym is fine -- no legal name required). Also logs the user in immediately.
- **Login** (`POST /api/auth/login`): returns the exact same generic error ("Invalid email or password.") whether the email doesn't exist or the password is wrong, so the endpoint never reveals which one it was.
- **Session**: an opaque, cryptographically random token (`secrets.token_urlsafe(32)`) is set in an **httpOnly, SameSite=Lax** cookie. Only a **SHA-256 hash** of the token is ever stored, in a `sessions` table with `expires_at`/`revoked_at`. The raw token exists only in the browser's cookie jar and is never recoverable from the database.
- **Logout** (`POST /api/auth/logout`): revokes the session **server-side** (`revoked_at = now()`), not just clears the cookie -- a stolen cookie stops working immediately after logout.
- **Password reset**: `POST /api/auth/forgot-password` always returns the same generic response regardless of whether the email exists. A random token is hashed and stored with a short expiry (default 30 min, `PASSWORD_RESET_TOKEN_TTL_MINUTES`); the raw token is **never** included in any API response. No real email provider is integrated yet -- `app/auth/email_service.py` logs the reset link server-side in a clearly-labeled dev-mode fallback rather than pretending to send an email. `POST /api/auth/reset-password` enforces single-use (`used_at`) and expiry, and revokes **every** existing session for that user on success.

### 8.4 Authorization / Ownership

- `training_plans.user_id` is **nullable**: `NULL` = an anonymous research plan (unchanged behavior, reachable without login); set = a consumer's own plan.
- `GET /api/plans/{id}`: an anonymous plan stays open to anyone (preserving the research flow exactly). A user-owned plan is only returned to that same authenticated user -- anyone else, including another logged-in user, gets the same generic `404 Training plan not found` a nonexistent ID would return, so the endpoint never confirms an ID belongs to someone else.
- `GET /api/plans` (recent list) now **excludes** user-owned plans entirely, so it can never be used to enumerate other users' plans.
- `POST /api/plans/generate` derives `user_id` **only** from the authenticated session (`get_optional_current_user`) -- a client-supplied `user_id` in a request body is never honored anywhere in the API.
- `GET/PATCH /api/users/me/profile` always operates on the session's own user; there is no way to address another user's profile by ID.
- Verified by a mandatory two-user test (`tests/test_authorization.py`) and a manual run against the live application with two real accounts (see `PHASE_1_REPORT.md`).

### 8.5 CSRF Strategy (documented, not claimed "fully secure" in isolation)

Because authentication uses cookies, CSRF is addressed with two layers of defense-in-depth:
1. The session cookie is `SameSite=Lax`, which already blocks the cookie from being attached to most cross-site state-changing requests.
2. `app/core/csrf.py` additionally requires that any `POST/PUT/PATCH/DELETE` request **carrying the session cookie** present an `Origin` (or `Referer`) header matching a configured allowed origin (`ALLOWED_ORIGINS`); otherwise it's rejected with `403`. A cross-site page cannot forge this header to our origin.

This is an appropriate strategy for this same-site SPA + API architecture, not a claim that the system is immune to every CSRF variant under every possible configuration.

### 8.6 Rate Limiting

Applied to login, registration, password-reset requests, and plan generation (which can invoke a paid LLM). Backed by `slowapi` (in-memory, single-process -- appropriate for MVP scale; move to a shared backend like Redis only when running multiple API instances). All limits are read from `app/config.py` / environment variables (`RATE_LIMIT_LOGIN`, `RATE_LIMIT_REGISTER`, `RATE_LIMIT_PASSWORD_RESET`, `RATE_LIMIT_PLAN_GENERATION` -- see `.env.example`), never hardcoded; changing them takes effect on the next process start. Plan generation is keyed by authenticated user when logged in, falling back to IP for anonymous/research requests, so one account can't exhaust a shared IP's quota and vice versa.

### 8.7 Error Handling

A global exception handler (`app/core/errors.py`) converts FastAPI/Pydantic validation errors into a friendly, field-labeled message instead of exposing the raw validation payload, and converts any unhandled exception into a generic `"An unexpected error occurred."` response. Full details (including the original validation errors and full tracebacks) are always logged server-side, never sent to the client -- API keys, stack traces, SQL errors, and internal file paths are never part of an API response.

### 8.8 Secrets

`GEMINI_API_KEY`/`OPENAI_API_KEY` remain server-side only (read via `app/config.py`, never sent to the frontend). `.env` is git-ignored (see the root `.gitignore`); `.env.example` documents every variable name with no real values. `SESSION_COOKIE_SECURE` must be set to `true` in any real (HTTPS) deployment -- it defaults to `false` only so local HTTP development keeps working.

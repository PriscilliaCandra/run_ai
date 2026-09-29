# Phase 2 Technical Design — Dashboard, Workout Logging & History

**Date:** 2026-09-29
**Status:** DESIGN ONLY. No application code, database, migration, or dependency was changed to produce this document. See Section 24 ("Final Safety Verification") at the end.

---

## 1. Executive Summary

Phase 1 turned the anonymous research prototype into a multi-user foundation: accounts, sessions, ownership, and a routing skeleton with placeholder pages at `/dashboard`, `/plans`, `/plans/new`, `/plans/:id`. Phase 2 fills in the first loop of the actual product: **a dashboard, manual workout logging, workout history, and basic statistics** — the minimum needed to start the retention loop `PLAN → FOLLOW → LOG WORKOUT → SEE PROGRESS`.

Two new tables are proposed: `workout_logs` (actual, user-logged activity) and `training_plan_workouts` (scheduled/planned workouts, materialized from the existing plan-generation JSON). These are kept **strictly separate** — a scheduled workout and a completed workout are different concepts with different lifecycles, linked later (Phase 3) by an optional foreign key, never merged into one record.

Nothing in the research flow (`/research/*`, rule engine, AI validator, evaluation system) is touched. Every new endpoint follows the exact ownership pattern already established in Phase 1 (`get_current_user` dependency, ownership-scoped queries, generic 404 for cross-user access).

---

## 2. Current Architecture Findings

Read before designing anything, specifically to avoid inventing a schema that doesn't match reality:

- **`backend/app/models.py`**: `User` (auth identity) and `UserProfile` (consumer runner profile: age, experience_level, pb_5k, pb_10k, target_race_distance, target_race_time, current_weekly_mileage, training_days_per_week, injury_limitations, easy_run_pace) already exist and are correctly separated from the anonymous `RunnerProfile`. `TrainingPlan` has a nullable `user_id`, but **no `start_date` and no `status` column** — a consumer plan today has no lifecycle state.
- **`backend/app/rules/generator.py`**: `generate_rule_based_plan()` returns `week_1_plan.workouts` — a fully detailed list of 7 `WorkoutItem`s (day, workout_type, distance_km, pace_target, intensity_zone, recovery_instruction, purpose) — **but only for week 1**. `progression_schedule` (weeks 1..N) only carries `{week_number, target_mileage_km, phase, focus_note}` — a single target number per week, with **no day-by-day breakdown for week 2 onward**. This is the single most important finding for the `training_plan_workouts` design (Section 6).
- **`backend/app/ai/llm_service.py`**: the AI-personalized plan has the same 7-workout structure as `week_1_plan`, plus `warmup_cooldown`/`workout_execution` text and `coach_overview`/`personalized_insights`. It is validated against the rule-based baseline (`app/ai/validator.py`) before being trusted, and is stored as `ai_plan_json` alongside `rule_based_plan_json` on `TrainingPlan`.
- **`backend/app/routes/plan_routes.py` / `profile_routes.py`**: the ownership pattern to reuse everywhere in Phase 2: `Depends(get_current_user)` for protected routes, `Depends(get_optional_current_user)` where anonymous access must be preserved, ownership-scoped `.filter(Model.user_id == current_user.id)`, and a **generic 404** (never 403) when a resource exists but belongs to someone else.
- **`backend/alembic/`**: two migrations exist (`0001_baseline`, `0002_add_auth`). The pattern to follow for Phase 2: additive-only, nullable-first for any new column on an existing table, named FK constraints for SQLite batch mode.
- **`backend/tests/`**: 79 tests, all passing, split into research tests (`test_rule_engine.py`, `test_llm_validation.py`, `test_evaluation.py`, parts of `test_api.py`) and Phase 1 auth/ownership tests (`test_auth.py`, `test_authorization.py`, `test_password_reset.py`, `test_rate_limiting.py`, `test_csrf.py`, `test_profile.py`). `tests/conftest.py`'s isolated-temp-database pattern and `tests/factories.py`'s helpers are the pattern to extend, not replace.
- **Frontend**: `react-router-dom` is wired up (`App.jsx`), `/dashboard`/`/plans*` are `PhaseTwoPlaceholderPage` behind `ProtectedRoute`, `ConsumerLayout` provides the header/nav shell, and `components/ui/{Button,Badge,StatusMessage}` plus the `inputClass`/`labelClass` convention (from `CreatePlanPage.jsx`/`ProfilePage.jsx`) are the reusable design system to build on.

---

## 3. Database Schema Proposal

Two new tables, plus two additive nullable columns on the existing `training_plans` table. Nothing existing is altered destructively.

### 3.1 `workout_logs` (new)

```
workout_logs
  id                  VARCHAR(36)  PK
  user_id             VARCHAR(36)  FK -> users.id, NOT NULL, indexed
  workout_date        DATE         NOT NULL            -- calendar date, no time-of-day (see 14.3)
  distance_meters     INTEGER      NOT NULL            -- see 14.1 for why meters, not km-float
  duration_seconds    INTEGER      NOT NULL
  workout_type        VARCHAR(20)  NOT NULL            -- controlled vocabulary, see 5.1
  avg_heart_rate      INTEGER      NULL
  max_heart_rate      INTEGER      NULL
  cadence_spm         INTEGER      NULL
  elevation_gain_m    INTEGER      NULL
  rpe                 INTEGER      NULL                -- 1-10, see 5.1 (NOT the research 1-5 Likert scale)
  notes               TEXT         NULL
  training_plan_workout_id  VARCHAR(36)  FK -> training_plan_workouts.id, NULL  -- Phase 3 link, unused in Phase 2 (see Section 21)
  created_at          DATETIME     NOT NULL (server default now)
  updated_at          DATETIME     NOT NULL (server default now, on update now)
  deleted_at          DATETIME     NULL                -- soft delete, see 14.4

  INDEX ix_workout_logs_user_date (user_id, workout_date)
  INDEX ix_workout_logs_user_deleted (user_id, deleted_at)
```

**Pace is never a stored column.** It is derived at read time: `pace_sec_per_km = duration_seconds / (distance_meters / 1000.0)`, computed in the Pydantic response schema, never persisted. This mirrors the live-pace-preview pattern already used in `CreatePlanPage.jsx` and avoids a stored value ever disagreeing with its inputs.

### 3.2 `training_plan_workouts` (new)

```
training_plan_workouts
  id                  VARCHAR(36)  PK
  training_plan_id    VARCHAR(36)  FK -> training_plans.id, NOT NULL, indexed
  week_number         INTEGER      NOT NULL
  day_of_week         VARCHAR(10)  NOT NULL            -- "Monday".."Sunday", matches WorkoutItem.day today
  workout_type        VARCHAR(30)  NOT NULL            -- verbatim from the plan JSON (e.g. "Interval Training")
  distance_meters     INTEGER      NOT NULL
  pace_target         VARCHAR(40)  NOT NULL            -- verbatim string, e.g. "05:15 - 05:30 /km" (see 14.1 note)
  intensity_zone      VARCHAR(60)  NOT NULL
  purpose             TEXT         NOT NULL
  created_at          DATETIME     NOT NULL (server default now)

  INDEX ix_tpw_plan_week (training_plan_id, week_number)
  UNIQUE (training_plan_id, week_number, day_of_week)
```

No `updated_at`/`deleted_at`: a scheduled workout is a derived snapshot of the plan JSON at generation time, not something a user edits directly (editing "the plan" is a bigger, separate feature — out of scope for Phase 2, see Section 22).

**Why both a normalized table AND the existing JSON, not one or the other:**
- `rule_based_plan_json` / `ai_plan_json` remain the **authoritative source of truth** — they already carry the AI's personalized text (`workout_execution`, `warmup_cooldown`, `coach_overview`), the full explainability matrix, and are what the research evaluation flow depends on. Rewriting the research flow to read from a normalized table would touch research-critical code for no benefit — explicitly against this phase's constraints.
- A normalized table is what Phase 2's dashboard ("today's scheduled workout") and Phase 3's "log against a scheduled workout" need — querying "what's scheduled for this user today" by parsing a JSON blob on every dashboard request does not scale and is awkward to index/filter/join.
- **Critical constraint from Section 2's finding:** because the generator only produces full daily detail for **week 1**, `training_plan_workouts` is populated **only for week 1** (7 rows) at plan-creation time. Weeks 2+ have no per-day detail to materialize yet — extending the rule engine to generate real multi-week daily schedules is explicitly **out of scope for Phase 2** (it is rule-engine/generator work, arguably a "Phase 2.5" or early-Phase-3 prerequisite, not a Phase 2 dashboard/logging concern). The dashboard's "today's workout" therefore only resolves correctly during week 1 of a plan in Phase 2 — see Section 9's explicit behavior spec and Section 23's open question.
- `training_plan_workouts` is populated **only for consumer-owned plans** (`training_plans.user_id IS NOT NULL`). Anonymous research plans never get rows here — zero new writes are triggered by the existing `/research/*` flow.

### 3.3 Additive columns on `training_plans`

```
ALTER TABLE training_plans ADD COLUMN start_date DATE NULL;
ALTER TABLE training_plans ADD COLUMN status VARCHAR(20) NULL;
                                        -- 'draft' | 'active' | 'completed' | 'archived'
```

Both nullable so every existing row (anonymous and the few Phase-1-era consumer test plans) remains valid with `NULL`. `status` is only meaningful for consumer plans; anonymous research plans simply never set it (the API layer never reads/writes it for the research routes).

**Is `training_plans.user_id` alone sufficient? No.** It answers "who owns this plan" but not "when does it start" (needed for "today's scheduled workout" and week-number math) or "is this the user's current plan" (needed for the dashboard to know which plan to show, once a user can have more than one). Both additive columns above are the minimum needed; no other new column on `training_plans` is proposed.

---

## 4. Entity Relationships

```
users (1) ──── (1) user_profiles
users (1) ──── (N) training_plans [nullable FK -- NULL = anonymous research plan]
users (1) ──── (N) workout_logs
training_plans (1) ──── (N) training_plan_workouts   [consumer plans only]
training_plan_workouts (1) ──── (0..N) workout_logs  [nullable FK, UNUSED until Phase 3]

runner_profiles (1) ──── (N) training_plans [existing, anonymous, unchanged]
training_plans (1) ──── (N) plan_evaluations [existing, anonymous, unchanged -- no user_id anywhere in this branch]
```

The research branch (`runner_profiles` → `training_plans` → `plan_evaluations`) and the consumer branch (`users` → `training_plans` → `training_plan_workouts`/`workout_logs`) share only the `training_plans` table, disambiguated by `user_id IS NULL` vs `IS NOT NULL` — exactly the pattern Phase 1 already established and verified.

---

## 5. Workout Model (`workout_logs`)

### 5.1 Controlled Vocabulary for `workout_type`

Recommended enum: `EASY, LONG_RUN, TEMPO, INTERVAL, RECOVERY, RACE, OTHER`.

`OTHER` is kept: manual logging inevitably has edge cases (a hybrid session, a mis-planned day, cross-training mistakenly logged) and a closed enum with no escape hatch either blocks the user or causes miscategorized data. It's the single most defensible "keep it" among the choices reviewed.

**Open question flagged, not decided here:** the rule engine's plan output uses different display strings ("Easy Aerobic Run", "Interval Training", "Long Run", "Tempo Run", "Rest & Recovery" — see `app/rules/generator.py`). For Phase 3's planned-vs-actual comparison to work, these vocabularies will eventually need to line up (either the log's enum maps to the plan's strings, or vice versa). This does not block Phase 2 — `workout_logs` and `training_plan_workouts` are not compared to each other yet — but it is called out now so Phase 3 doesn't discover the mismatch late. See Section 23.

### 5.2 Validation Ranges

| Field | Rule |
|---|---|
| `workout_date` | Required; not in the future beyond today (server date); no lower bound (a user should be able to backfill old runs) |
| `distance_meters` | Required; `100 <= distance_meters <= 300_000` (100m .. 300km, generously covers everything from a short shakeout to an ultramarathon; rejects obvious typos like entering meters where km was meant) |
| `duration_seconds` | Required; `60 <= duration_seconds <= 172_800` (1 minute .. 48 hours) |
| `avg_heart_rate` / `max_heart_rate` | Optional; `30 <= value <= 250` bpm; if both given, `avg_heart_rate <= max_heart_rate` |
| `cadence_spm` | Optional; `100 <= value <= 250` |
| `elevation_gain_m` | Optional; `0 <= value <= 10_000` |
| `rpe` | Optional; integer `1..10` (Borg CR10 scale — **explicitly a different scale from the research evaluation's 1-5 Likert**, and labeled as such in the UI to avoid confusion) |
| `notes` | Optional; max length 2000 chars |
| `workout_type` | Required; must be one of the 7 enum values |

All of the above are enforced **server-side** (Pydantic validators in the new schema, mirroring the existing pattern in `app/schemas.py`/`app/auth/schemas.py`), never client-only. The combination checks explicitly called out in the Phase 2 brief (`distance <= 0`, `duration <= 0`, impossible HR, impossible cadence, RPE out of range) are all covered by the ranges above.

### 5.3 Date vs. Datetime, Timezone

`workout_date` is a plain **DATE**, not a datetime — see Section 14.3 for the full reasoning. Phase 2 does not track per-user timezone; the date is stored exactly as the user picks it in a date field, with no UTC conversion. This is a deliberate MVP simplification, flagged as an open question in Section 23, not a silent gap.

### 5.4 Soft Delete

`deleted_at` nullable timestamp. `DELETE /api/workouts/{id}` sets it rather than removing the row. Every read query (history list, dashboard aggregation, detail fetch) filters `deleted_at IS NULL` by default. Nothing hard-deletes a workout log in Phase 2.

### 5.5 Ownership

`user_id` is set **only** from `get_current_user()` at creation time, exactly like `TrainingPlan.user_id` in Phase 1. It is never accepted from the client body. See Section 13 for the explicit bad/good example already specified in the brief, confirmed as the pattern to follow.

---

## 6. Training Plan Workout Model (`training_plan_workouts`)

Already specified in Section 3.2. To restate the key design decision plainly: **this table is a materialized, read-oriented snapshot of week 1 of a consumer plan's JSON, not a new authoring surface.** Nothing in Phase 2 lets a user edit an individual scheduled workout's distance/pace directly — that would fork it from the plan JSON and create a data-integrity question (which one is "the plan"?) that's better resolved deliberately in a later phase if ever needed.

Populated once, at the moment a plan is generated for an authenticated user (in the same request/transaction as `POST /api/plans/generate` — no separate endpoint needed to create these rows). If plan generation is ever retried or a plan is regenerated, the old plan's `training_plan_workouts` rows are untouched (a new plan gets its own new rows) — no update-in-place semantics needed in Phase 2.

---

## 7. User Profile Boundaries

Clarifying which data belongs where, per the brief's explicit request. No changes to any of the three tables are proposed here — this section is documentation of what already exists plus where the two NEW concepts (a logged workout, a plan's lifecycle) belong.

| Concept | Table | Rationale |
|---|---|---|
| Age, experience level, PBs, target race/time, weekly mileage baseline, training days/week, injury notes | `user_profiles` (existing) | Describes the **runner**, independent of any single plan or workout — used to *generate* plans. |
| A specific workout's distance, duration, HR, cadence, RPE, notes | `workout_logs` (new) | Describes a **single completed event** — never duplicated into the profile. |
| Generated plan content, target pace, VDOT, start date, status | `training_plans` (existing + 2 new columns) | Describes **one plan instance** — a snapshot of what was generated when, not the runner's ongoing characteristics. |
| A single scheduled day within a plan | `training_plan_workouts` (new) | Describes **one planned session** — distinct from both the profile and an actual log. |

No field is proposed to exist in more than one of these tables. `current_weekly_mileage` on `user_profiles` is the runner's *self-reported baseline* used as generation input; it is never overwritten automatically from `workout_logs` aggregates in Phase 2 (that kind of feedback loop is explicitly Phase 3/4 territory — see Section 21).

---

## 8. API Specification

All endpoints below require authentication (`Depends(get_current_user)`) unless noted, follow the existing `/api` prefix, use Pydantic request/response models (never expose SQLAlchemy models directly), and use the same generic-404-for-cross-user-access pattern already implemented in `plan_routes.py`.

### 8.1 Workouts

| Method | Path | Auth | Body | Response | Notes |
|---|---|---|---|---|---|
| `POST` | `/api/workouts` | required | `WorkoutLogCreate` (date, distance_meters, duration_seconds, workout_type, + optional fields) | `201` `WorkoutLogResponse` (includes computed `pace_sec_per_km`) | `user_id` from session only |
| `GET` | `/api/workouts` | required | query params: `date_from`, `date_to`, `workout_type`, `page`, `page_size` (default 20, max 100) | `200` `{items: [WorkoutLogResponse], total, page, page_size}` | Scoped to current user; excludes soft-deleted |
| `GET` | `/api/workouts/{id}` | required | — | `200` `WorkoutLogResponse` or `404` | 404 (not 403) if owned by someone else or soft-deleted |
| `PATCH` | `/api/workouts/{id}` | required | `WorkoutLogUpdate` (all fields optional, partial update) | `200` `WorkoutLogResponse` | Same ownership rule as GET |
| `DELETE` | `/api/workouts/{id}` | required | — | `204` | Soft delete (`deleted_at = now()`); same ownership rule |

### 8.2 Dashboard

| Method | Path | Auth | Response |
|---|---|---|---|
| `GET` | `/api/dashboard/summary` | required | `DashboardSummaryResponse` — see Section 9.4 for exact shape |

### 8.3 Profile

**Already implemented in Phase 1** — `GET /api/auth/me` (identity) and `GET`/`PATCH /api/users/me/profile` (runner profile). No Phase 2 change needed; listed here only to confirm the brief's "Profile: GET/PATCH /users/me" requirement is already satisfied by the existing split, and to avoid accidentally re-designing it.

### 8.4 Plans (Phase 2 additions only)

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/plans/mine` | required | Lists the current user's own plans (new — today's `GET /api/plans` deliberately excludes owned plans and only lists anonymous research plans; a separate path avoids changing that existing endpoint's behavior or contract) |
| `GET` | `/api/plans/{id}/workouts` | required (ownership) | Returns the plan's `training_plan_workouts` rows (week 1 only, per Section 6) |

`POST /api/plans/generate` and `GET /api/plans/{id}` are **unchanged** — Phase 1 already made them ownership-aware and optional-auth. Phase 2 additionally writes `training_plan_workouts` rows inside `generate_plan()` when `current_user` is present, and sets the new `start_date`/`status` columns (`status='active'`, `start_date=today` by default — see open question in Section 23 about whether a `draft` review step is wanted instead).

---

## 9. Dashboard Specification

### 9.1 Contents (Phase 2 only)

- Greeting with the user's `display_name`
- Current active plan summary (target race, week X of Y, if one exists)
- Today's scheduled workout (only resolvable during week 1 of a plan — see 9.3)
- "Log Workout" call to action (always present)
- This week's totals: distance, run count (Section 10)
- Recent activity: last 5 `workout_logs`
- A simple linear progress indicator (`current week / total weeks`) — a plain progress bar, not a "score"

### 9.2 Explicitly Excluded

Social feed, leaderboards, GPS maps, AI chatbot, subscriptions/payments, Garmin/Strava integration, any predictive or "fitness score" metric — matches the brief's non-goals exactly (see also Section 22).

### 9.3 Behavior Matrix

| State | Dashboard shows |
|---|---|
| No plan, no workout history | Greeting + empty-state card: "Create your first training plan" (links to `/plans/new`) + "Log a workout" CTA (a user can log runs even before generating a plan) |
| Plan exists, no workouts logged | Greeting + plan summary + today's scheduled workout (if in week 1) + "This week: 0 runs, 0 km" + empty-state for recent activity |
| Plan exists (week 2+), no workouts logged | Same as above, but today's scheduled workout shows a clear **"Detailed daily workouts aren't available past week 1 yet"** message instead of guessing — never fabricates a workout that wasn't actually generated |
| Workouts logged, no active plan | Greeting + "This week"/"recent activity" populate normally + empty-state for the plan card: "No active plan — create one" |
| Both present | Full dashboard as in 9.1 |

### 9.4 `DashboardSummaryResponse` shape

```json
{
  "display_name": "string",
  "active_plan": {
    "plan_id": "uuid",
    "target_race_distance": "5K",
    "target_pace_per_km": "04:36",
    "current_week": 2,
    "total_weeks": 8,
    "today_scheduled_workout": { "...WorkoutItem fields...": "..." } | null
  } | null,
  "this_week": { "total_distance_km": 12.4, "run_count": 3, "total_duration_seconds": 5400 },
  "recent_activities": [ "...WorkoutLogResponse...": "..." ],
  "has_any_workout_history": true
}
```

---

## 10. Workout Logging UX

### 10.1 Form Fields

**Required:** date, distance (km input, converted to meters server-side), duration (see 10.3 for input UX), workout type (select, controlled vocabulary from 5.1).
**Optional:** avg HR, max HR, cadence, elevation gain, RPE (1-10 slider or button-row, reusing the Likert-button visual pattern from `EvaluationPage.jsx` but explicitly labeled "RPE (1-10)" to avoid any visual confusion with the research 1-5 Likert scale), notes.

### 10.2 Units

Distance entered in **kilometers** (matches every existing UI convention in the app — `CreatePlanPage`, `ProfilePage`), converted to `distance_meters` at the API boundary. Elevation in meters. HR in bpm. Cadence in steps per minute (not strides per minute) — labeled explicitly.

### 10.3 Duration Input

Recommend **two number inputs (hours optional, minutes, seconds)** or a single `HH:MM:SS` / `MM:SS` text field reusing the exact parsing helper pattern (`parse_time_to_seconds`) already in `app/schemas.py` — for consistency, reuse that same MM:SS/HH:MM:SS convention rather than inventing a new one, both server-side (a new validator following the same regex pattern) and client-side (the same input affordance runners already see for `pb_5k`/`target_race_time`).

### 10.4 Pace Display

Never an input. Computed and shown live as the user types distance/duration (mirrors `CreatePlanPage.jsx`'s `liveTargetPace` `useMemo` pattern exactly), and shown again on the saved workout card/detail/history row from the server-computed value.

### 10.5 Edit / Delete / Confirmation

- Edit: same form, pre-filled, `PATCH`.
- Delete: soft delete, with a confirmation dialog (reuse a simple inline confirm, e.g. "Delete this workout? This can't be undone from the app." — technically recoverable at the DB level via `deleted_at`, but the UI should not promise undo since Phase 2 has no "trash/restore" UI).
- Save feedback: reuse the `saved` checkmark pattern already implemented in `ProfilePage.jsx`.

---

## 11. Workout History UX

- Chronological list (newest first), grouped by date, each row: date, workout-type badge (reuse `components/ui/Badge`), distance, duration, computed pace, RPE if present.
- Click-through to a detail view (full fields + notes + edit/delete actions).
- Filters: date range (from/to date pickers) and workout type (multi-select or single-select dropdown) — both implemented as query params on `GET /api/workouts`, not client-side filtering of an unbounded list.
- Pagination: default page size 20, matches the "don't overengineer" instruction — no infinite scroll or virtualized list needed at this scale.

---

## 12. Statistics Definitions

Computed by `GET /api/dashboard/summary` (this week) and a to-be-confirmed `GET /api/workouts/stats?period=month` (see Section 23 — whether monthly stats get their own endpoint or a query param on the same dashboard endpoint is an open, low-stakes decision).

| Metric | Definition |
|---|---|
| This week / this month boundary | **ISO calendar week (Monday-Sunday)** and **calendar month**, computed on the stored `workout_date` with no timezone conversion (see 5.3/14.3) |
| Total distance | Sum of `distance_meters` for non-deleted workouts in the period, converted to km for display |
| Number of runs | Count of non-deleted workout rows in the period (a `RACE`-type entry **counts** — flagged as an adjustable default in Section 23) |
| Total duration | Sum of `duration_seconds` in the period |
| Average pace | `total_duration_seconds / (total_distance_meters / 1000)` — a **volume-weighted** average, never an unweighted average of each workout's individual pace (averaging rates naively is mathematically misleading and explicitly flagged as a mistake to avoid in the brief) |
| Deleted workouts | Always excluded from every statistic |

**Explicitly not computed, per the brief's non-goals:** any "performance score," "fitness score," AI-derived score, better/worse ranking, or predictive race-time estimate. Phase 2 statistics are purely descriptive sums/counts/averages of what the user logged.

---

## 13. Security Model

Phase 2 introduces no new authentication mechanism — it reuses Phase 1's session/cookie/CSRF/rate-limiting infrastructure exactly.

- **Ownership**: every new endpoint uses `Depends(get_current_user)` and filters every query by `user_id == current_user.id`. A request body **never** contains `user_id` — the brief's own bad/good example is exactly the pattern already enforced in Phase 1's `plan_routes.py`/`profile_routes.py`, and every new Pydantic `*Create`/`*Update` schema in Phase 2 omits `user_id` entirely (it cannot be mass-assigned because it's not a field on the schema at all, not merely "ignored").
- **IDOR**: `GET/PATCH/DELETE /api/workouts/{id}` return the same generic 404 for "doesn't exist" and "belongs to someone else," exactly matching `GET /api/plans/{id}`'s behavior. This needs its own two-user test, mirroring `test_authorization.py`'s mandatory pattern.
- **CSRF**: the existing Origin-check middleware already covers `POST/PATCH/DELETE` on any path when the session cookie is present — no new CSRF work needed, it applies automatically to `/api/workouts/*`.
- **Rate limiting**: workout writes are cheap (no LLM call) but still deserve a sane ceiling against scripted abuse. Recommend a new **`RATE_LIMIT_WORKOUT_WRITE`** (suggested default `60/hour` per user) applied to `POST`/`PATCH`/`DELETE /api/workouts*`, following the exact `slowapi` + `settings.RATE_LIMIT_*` pattern from Phase 1. `GET` endpoints are not rate-limited beyond normal server capacity, consistent with how `GET /api/plans/{id}` isn't limited today.
- **Validation**: every range in Section 5.2 is enforced server-side via Pydantic, never trusted from client-side-only validation.
- **Error handling**: reuses the existing global exception handlers (`app/core/errors.py`) — no new leakage surface introduced by new endpoints, since they raise the same `HTTPException`/`RequestValidationError` types already handled globally.
- **Soft deletion**: excluding `deleted_at IS NOT NULL` rows from every read path also has a security dimension — a "deleted" workout must not leak back into history/dashboard aggregates, and must not become readable by anyone once deleted (an already-owned resource's `GET` after delete should also 404, treated identically to a nonexistent one).
- **Mass assignment**: `WorkoutLogUpdate` (PATCH schema) uses `exclude_unset=True` semantics exactly like `UserProfileUpsert` in Phase 1, so an omitted field is never accidentally nulled out.

---

## 14. Data Integrity

### 14.1 Distance: integer meters, not float km

**Recommendation: store `distance_meters` as `INTEGER`, not `distance_km` as `FLOAT`.** Rationale:
- Phase 2 introduces **aggregation** (weekly/monthly sums) for the first time in a user-facing, statistics-driven context. Summing many IEEE-754 doubles (e.g. repeatedly adding values like `5.2`, which isn't exactly representable in binary floating point) can accumulate small representation errors. Summing integers is always exact.
- This mirrors how most fitness platforms store distance internally (meters), and converting to km for display (`/ 1000`, rounded to 1-2 decimals) is a trivial, controlled operation at the presentation layer.
- This is a deliberate, narrow deviation from the existing research JSON's `distance_km: float` convention (used in `WorkoutItem`/`RunnerProfile`) — that convention is untouched and unaffected, since `workout_logs` is an entirely new, separate table with no shared code path. `training_plan_workouts.distance_meters` uses the same integer-meters convention for consistency between the two new tables, converting from the plan JSON's float km at materialization time.
- Duration is stored as `INTEGER` seconds for the same reason (and already matches `parse_time_to_seconds`'s existing return type in `app/schemas.py`).

### 14.2 Other numeric fields

Heart rate, cadence, elevation gain, and RPE are all naturally whole numbers for manual entry — stored as `INTEGER`, no floating point involved at all.

### 14.3 Date vs. Datetime, Timezone

`workout_date` is a plain `DATE`. **No timezone conversion is performed anywhere in Phase 2** — the date the user selects in the form is stored verbatim and is the same date used for all week/month boundary calculations (pure calendar-date arithmetic, never datetime-with-timezone arithmetic). This sidesteps an entire class of "which day does this fall on near midnight" timezone bugs by never introducing timezone-sensitive datetime logic into the statistics path. The tradeoff — a runner who travels across timezones might see a workout "on the wrong day" relative to their new local time — is accepted as a reasonable MVP simplification and flagged explicitly in Section 23, not silently swept aside.

### 14.4 Soft Delete, Foreign Keys, Cascade

- `workout_logs.deleted_at` (nullable) is the only soft-delete column introduced. `training_plan_workouts` has no soft delete (see Section 6 — it's a derived snapshot, not directly user-editable).
- Foreign keys: `workout_logs.user_id → users.id`, `workout_logs.training_plan_workout_id → training_plan_workouts.id` (nullable, unused until Phase 3), `training_plan_workouts.training_plan_id → training_plans.id`.
- Cascade: deleting a `User` should cascade-delete their `workout_logs` (consistent with the existing `User.profile`/`sessions`/`reset_tokens` `cascade="all, delete-orphan"` relationships already defined in `app/models.py`). Deleting a `TrainingPlan` should cascade-delete its `training_plan_workouts`. Neither cascade ever reaches `plan_evaluations`/`runner_profiles` — those remain anonymous and untouched by any consumer-side deletion.
- Indexes: `(user_id, workout_date)` and `(user_id, deleted_at)` on `workout_logs`; `(training_plan_id, week_number)` and a uniqueness constraint on `(training_plan_id, week_number, day_of_week)` on `training_plan_workouts` (prevents accidentally materializing the same scheduled day twice).

### 14.5 Migration Safety / Backward Compatibility

All changes are additive: two new tables, two new nullable columns. No existing column type changes, no existing row rewrites, no destructive operation. See Section 15 for the full migration plan.

---

## 15. Migration Strategy (design only — not executed)

Proposed single migration, `0003_add_workout_logging`, following the exact pattern of `0002_add_auth_and_ownership`:

1. `op.create_table("training_plan_workouts", ...)` with the columns from Section 3.2, a named FK to `training_plans.id`, a composite index, and a unique constraint.
2. `op.create_table("workout_logs", ...)` with the columns from Section 3.1, named FKs to `users.id` and `training_plan_workouts.id` (nullable), and the two indexes from 14.4.
3. `with op.batch_alter_table("training_plans") as batch_op:` → `add_column("start_date", Date, nullable=True)`, `add_column("status", String(20), nullable=True)` — using **named** constraints as required for SQLite batch mode (learned the hard way in `0002`).

**Rollback (`downgrade()`)**: drops the two new tables and the two new columns, in reverse dependency order — symmetric with `0002`'s downgrade. Rollback would only be exercised in a dev/staging environment; it is not intended to be run against a production database with real workout data without a fresh backup, exactly like the Phase 1 guidance.

**Production DB safety procedure (to follow when this is actually implemented and approved):**
1. Back up `running_research.db` (timestamped copy, git-ignored) — same procedure as Phase 1.
2. Rehearse the migration on a throwaway copy of the real database first.
3. Verify row counts and content of `runner_profiles`/`training_plans`/`plan_evaluations` are byte-identical before and after, exactly as done for `0002`.
4. Only then run `alembic upgrade head` against the real database.

**Research tables are not touched by this migration at all** — no column is added to `runner_profiles` or `plan_evaluations`.

---

## 16. Test Strategy

Backend (pytest, extending `tests/conftest.py`'s isolated-temp-database fixture and `tests/factories.py`'s helpers — never touching the real `running_research.db`, exactly like every existing test):

**`test_workouts.py` (new):**
- Create: valid workout succeeds and returns computed pace
- Validation: rejects `distance <= 0`, `duration <= 0`, out-of-range HR/cadence/RPE, invalid `workout_type`, future date
- Read own workout: `GET /api/workouts/{id}` succeeds for the owner
- Update own workout: `PATCH` partial update only touches sent fields (same pattern as `test_profile.py`'s partial-PATCH test)
- Delete own workout: soft-deletes, subsequent `GET` on the same ID returns 404
- **Cannot read/update/delete another user's workout** — the mandatory two-user pattern from `test_authorization.py`, repeated for workouts
- Deleted workouts excluded from `GET /api/workouts` (history) and from dashboard aggregates
- Pace is calculated correctly for a range of distance/duration combinations, including edge values

**`test_dashboard.py` (new):**
- Requires authentication (401 if not logged in)
- Empty state: new user with no plan and no workouts gets the documented empty-state shape, not an error
- Weekly totals: correct sum/count for a fixture of workouts spanning a week boundary
- Monthly totals: correct sum/count spanning a month boundary
- Deleted workouts excluded from both weekly and monthly totals
- A workout logged exactly on a week/month boundary date lands in the correct bucket (a specific test for the date-boundary logic in Section 14.3)

**`test_plans.py` (extended, not replacing existing plan tests):**
- A consumer plan generated while authenticated gets `training_plan_workouts` rows for week 1 (7 rows, correct `day_of_week`/`workout_type`/`distance_meters`)
- An anonymous research plan generated with no session gets **zero** `training_plan_workouts` rows — explicit regression test proving the research flow is unaffected
- `GET /api/plans/{id}/workouts` ownership-scoped exactly like `GET /api/plans/{id}`

**Regression:** the full existing suite (79 tests: 43 research + 36 Phase 1) must continue to pass unmodified. No existing test file's assertions are weakened to accommodate Phase 2.

**Frontend / manual verification (once implemented):** the same three-viewport (desktop/tablet/mobile) + four-state (loading/empty/error/populated) matrix already applied during the UI polish pass, specifically exercised against: dashboard in all four states from Section 9.3, the workout log form's validation messages, and the history list's filters/pagination at mobile width.

---

## 17. Privacy Considerations

- `workout_logs` are **user-owned personal data** — distance, duration, HR, location-adjacent metadata (none stored yet, see Section 18) are all data the user generated about their own body/activity.
- **No automatic copying** of `workout_logs`/`user_profiles`/consumer `training_plans` into the anonymous research tables (`runner_profiles`, `plan_evaluations`). If research participation is ever offered to logged-in consumer users, it must be an **explicit, separate opt-in** flow that creates a genuinely anonymous research record (a new `runner_profiles` row, not a reference to the user's account) — consistent with the Phase 1 report's Section 8.1 identity-separation principle and the original audit's Section 17.
- Account deletion (a Phase 2-or-later feature, not built yet) should cascade-delete/anonymize `workout_logs` along with the rest of the user's data — see Section 14.4's cascade design, which is ready for that when it's built.

---

## 18. Future Garmin/Strava Compatibility (assessment only, nothing added)

**Recommendation: postpone `source`, `external_activity_id`, `imported_at` entirely.** No such fields are added to `workout_logs` in this design. Reasoning: these are meaningful only once a specific integration is actually being built, at which point the exact fields needed depend on which provider's data model is being mapped (Garmin's and Strava's activity schemas differ in non-trivial ways). Adding speculative columns now would be exactly the "field added because another app might need it" anti-pattern the brief warns against. When an integration is actually scoped (explicitly listed as "Later" in the original product audit), adding `source VARCHAR(20) NULL DEFAULT 'manual'`, `external_activity_id VARCHAR(100) NULL`, `imported_at DATETIME NULL` is a simple, low-risk additive migration at that time — nothing about today's schema blocks it.

---

## 19. Phase 3 Compatibility

How Phase 2's structures enable, without implementing, the Phase 3 loop `planned → actual → planned vs actual → adherence → future personalization context`:

1. **`training_plan_workouts`** already represents "planned" as its own first-class row (Section 6), distinct from `workout_logs`'s "actual."
2. **`workout_logs.training_plan_workout_id`** (nullable FK, defined now, unused now) is the exact join key Phase 3 needs to let a user say "this is the run I did for Tuesday's scheduled tempo session" — the column exists from day one so no migration is needed later just to add the link, only the UI/logic to populate and use it.
3. Once populated, "planned vs actual" is a simple join + diff (`training_plan_workouts.distance_meters` vs `workout_logs.distance_meters`, target pace vs actual pace) — no new schema required, purely a Phase 3 API/UI feature.
4. **Adherence** (% of scheduled workouts actually logged) is computable the same way — count `training_plan_workouts` rows with a matching `workout_logs` row vs. total scheduled — again no new schema, a Phase 3 query.
5. **Future personalization context** (Phase 3/4): adherence %, recent RPE trend, and recent pace trend are all derivable from `workout_logs` alone (no plan link needed for these three specifically). Per the original audit's explicit safety rule (repeated here because it still applies): this data may only ever flow into the **existing rule-engine-first, LLM-second, validator-third pipeline** as additional read-only context for the *next* plan regeneration — never as an automatic, silent single-workout-triggered mutation of an existing plan.

Nothing above is implemented in Phase 2. The column and table structure simply avoids a future migration being needed just to establish the link.

---

## 20. Explicit Non-Goals (Phase 2)

Matching the brief precisely, restated here as a checklist so implementation doesn't scope-creep:
- No Garmin, Strava, Apple Health, or Google Health Connect integration
- No GPS tracking or live tracking
- No social feed, followers, challenges, or leaderboards
- No payments or subscriptions
- No "fitness score," AI score, predictive race-time estimate, or any better/worse ranking
- No adaptive/automatic training plan adjustment
- No editing of individual scheduled workouts (`training_plan_workouts` is read-only/derived in Phase 2)
- No multi-week detailed schedule generation (rule-engine extension is out of scope — see Section 3.2)
- No new UI framework, state management library, or charting library beyond what's minimally needed for a plain progress bar (a simple `<div>` width-percentage bar, exactly like `PlanResultPage.jsx`'s existing progression bars — no new dependency)
- No PostgreSQL, Redis, background job queue, or microservice split

---

## 21. Open Questions / Decisions Requiring Approval

1. **New plan default status**: should a freshly generated consumer plan start as `'active'` immediately (current recommendation, matches today's no-review-step UX) or `'draft'` until the user explicitly confirms/starts it? Affects whether a `POST /api/plans/{id}/activate`-style endpoint is needed in Phase 2 or can wait.
2. **Timezone handling** (Section 14.3): accept the no-timezone, plain-calendar-date simplification for Phase 2, or invest in per-user timezone storage now? Recommendation: accept the simplification; revisit only if real users report boundary issues.
3. **Do races count toward "number of runs" / "total distance"** in weekly/monthly stats (Section 12)? Recommendation: yes, with the option to add a stats filter later if this proves confusing in practice.
4. **Distance storage as integer meters** (Section 14.1) vs. keeping `distance_km: float` for consistency with the existing research JSON convention: recommendation is integer meters for `workout_logs`/`training_plan_workouts` specifically, for the aggregation-precision reason given; needs explicit sign-off since it's a deliberate deviation from the existing convention.
5. **Monthly statistics endpoint shape**: a separate `GET /api/workouts/stats?period=month` vs. folding it into `GET /api/dashboard/summary` with a query param. Low-stakes; recommendation is a separate endpoint so the dashboard response stays small and fast, but either works.
6. **RPE scale (1-10) placement in the UI**: confirm the recommendation to visually and textually distinguish it from the research 1-5 Likert scale is sufficient, or whether a different scale (e.g. Borg 6-20) is preferred for closer alignment with exercise-science literature.
7. **Workout-type vocabulary alignment** between the rule engine's plan-generation strings and the new `workout_logs` enum (Section 5.1): defer reconciliation to Phase 3 (when it actually matters for planned-vs-actual matching), or normalize now for future-proofing? Recommendation: defer — normalizing now touches rule-engine-adjacent code for no Phase 2 benefit.

---

## 22. Recommended Implementation Order (for Phase 2, once approved)

1. Migration `0003_add_workout_logging` (tables + columns), rehearsed on a DB copy first, applied only after explicit approval.
2. `WorkoutLog`, `TrainingPlanWorkout` SQLAlchemy models; `start_date`/`status` added to `TrainingPlan`.
3. Pydantic schemas (`WorkoutLogCreate`, `WorkoutLogUpdate`, `WorkoutLogResponse` with computed pace; `TrainingPlanWorkoutResponse`).
4. `app/routes/workout_routes.py` (full CRUD, ownership-scoped, rate-limited writes).
5. Materialize `training_plan_workouts` inside the existing `generate_plan()` handler for authenticated requests only (small, additive change to `plan_routes.py`, not a rewrite).
6. `app/routes/dashboard_routes.py` (`GET /api/dashboard/summary`).
7. Backend tests (Section 16) — written alongside each piece above, not after.
8. Frontend: `api.js` additions → `DashboardPage.jsx` → `LogWorkoutPage.jsx` → `HistoryPage.jsx` (+ detail/edit) → wire into the existing placeholder routes in `App.jsx`, replacing `PhaseTwoPlaceholderPage` usages one at a time.
9. Manual cross-viewport verification (Section 16) before calling Phase 2 done.

---

## 23. Frontend Routing, Responsive Design & Error Handling (brief cross-reference)

- **Information architecture**: `Dashboard | Plans | History | Profile` as the primary consumer nav (replacing the current placeholder-only `ConsumerLayout` nav), consistent with the brief's suggestion. Mobile keeps the existing hamburger-drawer pattern from `ConsumerLayout.jsx` (already responsive) rather than inventing a bottom tab bar — reusing what already works is preferred over the brief's alternative "Home/Plans/Log/History/Profile" bottom-nav suggestion, unless a strong mobile-UX reason emerges during implementation.
- `/research/*` is **not** touched or redesigned by any of this.
- **Reuse, not reinvent**: `Button`, `Badge`, `StatusMessage` (`LoadingState`/`EmptyState`/`ErrorState`), the `inputClass`/`labelClass` convention, and `ProtectedRoute` are all reused as-is for every new Phase 2 page.
- **Error messages** (user-facing, never exposing internals):

  | Situation | Message |
  |---|---|
  | Invalid workout data | Field-specific, friendly (reuses the existing `app/core/errors.py` validation-to-friendly-message pipeline from Phase 1 automatically) |
  | Workout not found / not yours | "This workout couldn't be found." (identical generic wording to the existing plan-not-found case) |
  | Unauthorized / expired session | Redirect to `/login` via the existing `ProtectedRoute`, with a "Please log in again to continue." toast/banner rather than a raw 401 |
  | Failed dashboard/history request | Reuses `ErrorState` component with a "Try Again" action, exactly like `EvaluationStatsPage.jsx`'s existing pattern |
  | Network error | Same `ErrorState`, generic "Could not reach the server" message (already implemented in `StatusMessage.jsx`'s `ErrorState` for the `Failed to fetch` case) |

---

## 24. Phase 2 Acceptance Criteria

Concrete and testable — Phase 2 is considered done when all of the following hold:

1. A logged-in user can create a workout log with required fields (date, distance, duration, type) and it is persisted with a correctly server-computed pace never entered by the user.
2. Submitting a workout with `distance <= 0`, `duration <= 0`, out-of-range HR/cadence/RPE, or an invalid `workout_type` is rejected with a friendly, field-specific error — never a raw validation payload.
3. A user can view, edit, and soft-delete their own workout; a soft-deleted workout disappears from history and all statistics immediately.
4. **User B cannot read, update, or delete User A's workout** by ID (404, not 403, not a 200 with someone else's data) — proven by an automated test, mirroring the mandatory Phase 1 IDOR test.
5. The dashboard renders correctly (per the Section 9.3 matrix) in all four combinations of {plan exists / doesn't} × {workouts exist / don't}, with no error thrown in any combination.
6. Weekly and monthly statistics match a hand-computed expectation for a known fixture set of workouts, including at least one workout dated exactly on a week/month boundary.
7. A consumer plan generated while authenticated produces exactly 7 `training_plan_workouts` rows (week 1); an anonymous research plan generated with no session produces **zero** such rows.
8. `GET /api/plans/{id}/workouts` is ownership-scoped exactly like `GET /api/plans/{id}` (same generic-404 behavior for a non-owned or nonexistent plan).
9. All 79 pre-existing tests continue to pass unmodified, plus all new Phase 2 tests pass.
10. The dashboard, workout log form, and history list are usable without horizontal overflow or unreadable text at 375px, 768px, and 1440px viewport widths.
11. No new endpoint accepts a client-supplied `user_id`, `owner_id`, or equivalent field anywhere in its request schema.
12. The research flow (`/research/*`) is manually re-verified end-to-end (generate → evaluate → stats) and shows zero behavioral change from before Phase 2.

---

## Final Safety Verification

Performed immediately before finishing this document:

```
$ git status --short
?? PHASE_2_DESIGN.md

$ git diff --stat
(empty output -- no tracked file has any modification)

$ git log --oneline
717faca Document Phase 1 authentication architecture and final report
8ffb72c Phase 1: multi-user authentication, authorization, and security foundation
732f4b3 Initial commit: baseline research prototype before Phase 1
```

- **No application code was changed.** The only filesystem change made during this task is the creation of this new, untracked file, `PHASE_2_DESIGN.md` (hence it appearing as `??` in `git status`). `git diff --stat` against every already-tracked file is empty -- zero lines changed in any existing file. Nothing has been staged or committed.
- **No database was changed.** No `sqlite3`/ORM write command was executed; `running_research.db` was not opened for writing at any point in this task.
- **No migration was executed.** No `alembic` command was run.
- **No dependency was installed.** No `pip install`/`npm install` command was run.
- **Research logic remains untouched** — `app/rules/`, `app/ai/`, `app/routes/evaluation_routes.py`, and every research-facing frontend page were only *read*, never edited.

No unexpected modification occurred. **STOP — awaiting approval before any Phase 2 implementation.**

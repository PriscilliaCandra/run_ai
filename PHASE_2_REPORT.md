# Phase 2 Implementation Report

**Feature scope:** Workout logging, dashboard, and consumer training-plan lifecycle for the RunAI consumer product, built on top of the Phase 1 authentication/authorization foundation.

**Status:** COMPLETE. All 15 in-scope items implemented and verified. No Phase 3 work (Garmin/Strava, adaptive training, social, payments, etc.) was started. This report distinguishes what was actually **IMPLEMENTED** from what was explicitly **DEFERRED** — nothing below is claimed that was not verified working.

---

## 1. Files Changed

### Backend — new files
- `backend/alembic/versions/0003_add_workout_logging.py` — migration
- `backend/app/workouts/__init__.py`
- `backend/app/workouts/schemas.py` — Pydantic schemas, pace calculation
- `backend/app/workouts/service.py` — plan-lifecycle and materialization helpers
- `backend/app/routes/workout_routes.py` — workout CRUD API
- `backend/app/routes/dashboard_routes.py` — dashboard summary API
- `backend/tests/test_workouts.py` (20 tests)
- `backend/tests/test_dashboard.py` (11 tests)
- `backend/tests/test_plan_lifecycle.py` (9 tests)

### Backend — modified files
- `backend/app/models.py` — `TrainingPlanWorkout`, `WorkoutLog` models; `TrainingPlan.start_date`/`status`; relationships
- `backend/app/routes/plan_routes.py` — consumer plan lifecycle in `generate_plan()`; new `GET /plans/mine`, `GET /plans/{plan_id}/workouts`
- `backend/app/main.py` — registered `workout_routes`, `dashboard_routes`
- `backend/app/config.py` — `RATE_LIMIT_WORKOUT_WRITE` setting
- `backend/.env.example` — documented the new rate-limit variable
- `backend/tests/factories.py` — `make_workout_payload()` helper
- `.gitignore` — added `backend/running_research.db.PRE_PHASE2_BACKUP_*` (the existing `*.db` pattern does not match timestamped backup filenames, same gap fixed for Phase 1)

### Frontend — new files
- `frontend/src/utils/workout.js` — workout type labels, duration/pace parsing and formatting
- `frontend/src/components/WorkoutForm.jsx` — shared create/edit form
- `frontend/src/pages/LogWorkoutPage.jsx`
- `frontend/src/pages/WorkoutDetailPage.jsx` (view/edit/delete)
- `frontend/src/pages/HistoryPage.jsx` (filters + pagination)
- `frontend/src/pages/DashboardPage.jsx`
- `frontend/src/pages/PlansPage.jsx`
- `frontend/src/pages/PlanNewPage.jsx`
- `frontend/src/pages/PlanDetailConsumerPage.jsx`

### Frontend — modified files
- `frontend/src/api.js` — workout/dashboard/consumer-plan API calls
- `frontend/src/App.jsx` — real routes replacing all placeholder pages
- `frontend/src/layouts/ConsumerLayout.jsx` — Dashboard/Plans/History/Profile navigation
- `frontend/src/pages/PhaseTwoPlaceholderPage.jsx` — **deleted** (confirmed unreferenced via grep before removal)

**Diff summary:** 11 tracked files changed (285 insertions, 99 deletions) + 15 new tracked files. No changes to any research-only module (`app/rules/`, `app/ai/llm_service.py` core logic, `ResearchApp.jsx`, or anything under `frontend/src/research*`).

---

## 2. Migration Details

Revision `0003_workout_logging` (`down_revision = "0002_add_auth"`):
- Creates `training_plan_workouts` (7 columns + metadata, FK to `training_plans`, unique constraint on `(training_plan_id, week_number, day_of_week)`, index on `(training_plan_id, week_number)`)
- Creates `workout_logs` (user-owned, FK to `users` and nullable FK to `training_plan_workouts`, indexes on `(user_id, workout_date)` and `(user_id, deleted_at)`)
- `op.batch_alter_table("training_plans")` adds nullable `start_date` (Date) and `status` (String(20)) columns
- All FKs given explicit names (`fk_tpw_training_plan_id`, `fk_workout_logs_user_id`, `fk_workout_logs_tpw_id`) to avoid the SQLite batch-mode "Constraint must have a name" failure encountered in Phase 1
- Full symmetric `downgrade()` provided

**Safety procedure followed exactly as specified:**
1. Backed up real DB → `backend/running_research.db.PRE_PHASE2_BACKUP_20260929_092659` (gitignored)
2. Copied DB → `phase2_migration_test.db`
3. Ran `alembic upgrade head` against the **copy** only
4. Verified row counts identical before/after on the copy: `runner_profiles=11, training_plans=11, plan_evaluations=9, users=4, user_profiles=4, sessions=5, password_reset_tokens=0`
5. Verified row *content* (spot-checked research plan JSON fields unchanged)
6. Ran the full test suite (isolated temp DBs — never touched the real or copy DB)
7. Only then ran `alembic upgrade head` against the real `running_research.db`, re-verified identical pre-existing counts plus two new empty tables

---

## 3. Database Schema Implemented

```
training_plan_workouts
  id (PK), training_plan_id (FK), week_number, day_of_week,
  workout_type, distance_meters (INT), pace_target, intensity_zone,
  purpose, created_at
  UNIQUE(training_plan_id, week_number, day_of_week)

workout_logs
  id (PK), user_id (FK), workout_date (DATE), distance_meters (INT),
  duration_seconds (INT), workout_type, avg_heart_rate, max_heart_rate,
  cadence_spm, elevation_gain_m, rpe (1-10 INT), notes,
  training_plan_workout_id (nullable FK), created_at, updated_at, deleted_at

training_plans (existing table, extended)
  + start_date (DATE, nullable), status (VARCHAR(20), nullable)
```

Per the approved decisions: distances are `INTEGER distance_meters` (not float km); existing research JSON `distance_km` fields were **not** touched; `workout_date` is a plain `DATE` with no timezone handling anywhere in Phase 2.

---

## 4. API Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/workouts` | required | Create a workout log |
| GET | `/api/workouts` | required | List own workouts, paginated, filterable by `date_from`/`date_to`/`workout_type` |
| GET | `/api/workouts/{id}` | required | Get one own workout |
| PATCH | `/api/workouts/{id}` | required | Partial update of own workout |
| DELETE | `/api/workouts/{id}` | required | Soft-delete own workout |
| GET | `/api/dashboard/summary` | required | Week/month totals, active plan, today's scheduled workout, recent activity |
| GET | `/api/plans/mine` | required | List the caller's own consumer plans |
| GET | `/api/plans/{plan_id}/workouts` | optional* | Week-1 scheduled workouts for a plan |

*`GET /api/plans/{plan_id}/workouts` uses `get_optional_current_user` because it must stay open for anonymous research plans, exactly mirroring the existing `GET /api/plans/{plan_id}` ownership contract.

Existing `POST /api/plans` (`generate_plan`) gained consumer-only lifecycle side effects gated on `if current_user:` — zero behavior change for anonymous calls.

---

## 5. Authentication / Authorization

- Every new endpoint requires `get_current_user` except the plan-workouts read endpoint, which reuses the existing dual-mode pattern.
- No new session, cookie, or CSRF mechanism was introduced — Phase 2 endpoints ride entirely on the Phase 1 foundation (httpOnly session cookie, Origin-check CSRF middleware, Argon2 password hashing).
- Workout write endpoints are rate-limited via `RATE_LIMIT_WORKOUT_WRITE` (default `60/hour`), reusing the existing `slowapi` limiter and the test suite's existing rate-limit-disable fixture.

---

## 6. Workout Ownership (Critical Security Requirement)

The requirement — that `workout_logs.training_plan_workout_id` must never allow cross-user linking — is enforced by `_resolve_owned_training_plan_workout()` in [workout_routes.py](backend/app/routes/workout_routes.py:23), which performs a server-side SQL JOIN `TrainingPlanWorkout → TrainingPlan` and filters on `TrainingPlan.user_id == current_user.id`. It is called on both create and update (only when `training_plan_workout_id` is present in the update payload). A non-existent ID and another user's ID return the **identical** generic `400 Invalid training_plan_workout_id.` — never distinguished, so existence is never leaked.

`workout.user_id` is always taken from `current_user.id` server-side; it is not a field on `WorkoutLogCreate`, so a client cannot submit it at all (`test_client_supplied_user_id_is_not_a_field_on_the_create_schema`).

Workout read/update/delete use `_get_owned_workout_or_404()`, filtering by `user_id == current_user.id` and `deleted_at IS NULL`, returning a generic 404 for both "doesn't exist" and "belongs to another user" (`test_user_a_workout_not_readable_updatable_or_deletable_by_user_b`, verified passing).

Verified live in the browser: workouts created/edited/deleted through the UI only ever operate on the logged-in user's own data; no ownership leak was observed in any manual test.

---

## 7. Dashboard Behavior

- **This Week / This Month** totals computed via `_period_totals()`: distance, run count, total duration, and a **volume-weighted** average pace (`total_duration_seconds / (total_distance_meters/1000)`), never a naive per-workout average. Verified live: after logging 5km@4:00/km-equivalent test data the aggregation matched the weighted formula, and a dedicated unit test (`test_average_pace_is_volume_weighted_not_averaged_per_workout`) locks this in.
- Week boundary = Monday–Sunday (`today - timedelta(days=today.weekday())`); month boundary = calendar month. Pure date arithmetic, no timezone conversion.
- Race-type workouts count toward run count, distance, and duration (approved decision #5) — no special-casing excludes them.
- No separate monthly-statistics endpoint was created; `this_month` is folded directly into `/api/dashboard/summary`, per approved decision #6.
- "Today's scheduled workout" is only ever populated when `current_week == 1` (i.e., week-1 detail actually exists) — for any later week, `week1_detail_available: false` is returned and the frontend shows an explicit limitation notice instead of fabricating data.

**Live browser verification (mobile, tablet, desktop):**
- Empty state (no plan, no workouts): confirmed — greeting, zeroed stat grid, "Create a Training Plan" CTA.
- Plan + no workouts: confirmed — Week 1 of 8, target pace, today's scheduled Interval workout for the current date (Tuesday, 2026-09-29).
- Plan + workouts: confirmed — This Week showed `10.0 km / 1 run / 50m / 05:00 /km` after logging a matching workout; Recent Activity listed it.

---

## 8. training_plan_workouts Behavior

`materialize_week_one()` in [service.py](backend/app/workouts/service.py) reads only `rule_plan["week_1_plan"]["workouts"]` (the only part of the rule engine's output with full daily detail) and creates exactly 7 rows per consumer plan, converting `distance_km` → `distance_meters` via `round(km * 1000)`. Weeks 2+ are **never** fabricated — `progression_schedule` only carries a single summary mileage number per week, which is insufficient for daily materialization, so it is deliberately left alone. The rule engine itself was not modified.

Verified: `test_plan_lifecycle.py` — anonymous plans create zero rows; consumer plans create exactly 7, covering all 7 weekdays. Live browser test: generating a consumer plan produced a full 7-day Week 1 Schedule on `/plans/{id}`.

---

## 9. Week-1 Limitation

This is a deliberate, disclosed limitation, not a bug: `training_plan_workouts` only ever contains week 1. Weeks 2 and beyond have no per-day detail in the data model yet. The dashboard and plan-detail pages both handle this explicitly (`week1_detail_available` flag; plan detail page text: *"Full multi-week daily schedules are coming in a future update."*). `test_dashboard.py::test_week1_limitation_...` manually advances a plan's `start_date` to simulate week 3 and confirms no workout is fabricated.

---

## 10. Security

- Generic 404 (never 403) on all ownership checks — existence is never leaked (Phase 1 pattern, reused consistently).
- `training_plan_workout_id` ownership is re-validated on every write, never trusted from the client (Section 6).
- All workout mutations require authentication; no anonymous write path exists anywhere in Phase 2.
- Soft delete only — `DELETE /api/workouts/{id}` never issues a physical row deletion; all reads/aggregates filter `deleted_at IS NULL`.
- Rate limiting applied to all workout write endpoints.
- No new attack surface introduced in the CSRF/session layer; Phase 2 endpoints are ordinary session-cookie-authenticated JSON routes under the existing Origin-check middleware.

---

## 11. Tests

**122 passed, 0 failed** (79 pre-existing Phase 0/1 tests + 43 new), run three times consecutively during implementation and once more just now as final confirmation — all green, no flakiness observed.

New coverage: `test_workouts.py` (20 — validation, pace calc, CRUD, ownership/IDOR, cross-user training_plan_workout linking), `test_dashboard.py` (11 — auth, empty/plan/workout states, week-1 limitation, week/month boundaries, deleted-workout exclusion, volume-weighted pace), `test_plan_lifecycle.py` (9 — materialization, single-active-plan archiving, cross-user isolation, `/plans/mine` and `/plans/{id}/workouts` ownership).

Tests run against isolated temp SQLite databases (`conftest.py` redirect), never the real research DB. Real DB row counts were confirmed unchanged by test runs (`workout_logs=0, training_plan_workouts=0` immediately after a full suite run, before any manual browser testing began).

---

## 12. Browser Verification

Performed live against the running dev server (not just described) at three viewports.

**Mobile (375px):** register → dashboard (empty state) → log workout (create) → history (shows entry, correct pace) → workout detail → edit (distance 5→8km, pace server-recalculated 05:00→03:08/km) → delete (inline confirm, soft-delete, disappears from history) → create plan (profile pre-fill confirmed) → plan detail (full week-1 schedule rendered) → dashboard-with-plan (today's scheduled workout shown) → new workout → dashboard-with-workouts (stats aggregated correctly) → history filter (Tempo filter → correctly empty; reset → item reappears) → logout (redirected to `/login` via `ProtectedRoute`, expected behavior) → login (redirected back to originally-requested page) → hard reload (session persisted, stayed on `/dashboard`).

**Tablet (768px) / Desktop (1440px):** dashboard, plans list, plan detail, history re-checked — no horizontal overflow at either width (confirmed via `scrollWidth <= innerWidth`, and cross-checked element bounding boxes against a screenshot rendering artifact that initially looked like overflow but was not).

**No horizontal overflow** at any viewport (measured, not eyeballed). **No raw/unhandled API errors** observed during any flow. **No ownership leaks** — every workout/plan operation only ever touched the logged-in test user's own data.

**Console errors:** a large batch of `Invalid hook call` / `useAuth must be used within an AuthProvider` / stale-module errors appeared when querying the long-lived browser tab's accumulated console buffer. These were confirmed to be **historical**, not current: reproduced only on the original tab (open since early in this session, spanning an earlier Vite dependency re-optimization and the `PhaseTwoPlaceholderPage.jsx` deletion, both already fixed by a documented dev-server restart), and **absent entirely** on a brand-new tab loading the same `/dashboard` URL fresh. This was verified directly rather than assumed.

---

## 13. Research Regression Verification

Ran the full anonymous research flow manually end-to-end after all Phase 2 code changes:
1. **Generate** (`/research`, "Load S2 Research Example" → Generate): rule-based VDOT (38.4), pace zones, explainability matrix, and AI-personalized plan all rendered identically to pre-Phase-2 behavior.
2. **Evaluate**: submitted a Likert 1–5 evaluation for the AI-personalized plan; confirmed "Evaluation Recorded... stored in the research database under the `ai_personalized` category."
3. **Statistics**: `/research` analytics dashboard showed the evaluation count increment from 9 → 10 total evaluations (exactly the one new submission), with correct N=5/N=5 split, means/medians/SDs recalculated correctly, and qualitative comments intact.

Zero behavioral change detected in any research-only code path (rule engine, AI service, evaluation scoring, statistics aggregation). `plan_routes.py`'s only change to the anonymous path is that `generate_plan()`'s consumer-lifecycle block is gated behind `if current_user:`, which is `None` for every anonymous research call.

---

## 14. Git Status

```
$ git status --short
 M .gitignore
 M backend/.env.example
 M backend/app/config.py
 M backend/app/main.py
 M backend/app/models.py
 M backend/app/routes/plan_routes.py
 M backend/tests/factories.py
 M frontend/src/App.jsx
 M frontend/src/api.js
 M frontend/src/layouts/ConsumerLayout.jsx
 D frontend/src/pages/PhaseTwoPlaceholderPage.jsx
?? backend/alembic/versions/0003_add_workout_logging.py
?? backend/app/routes/dashboard_routes.py
?? backend/app/routes/workout_routes.py
?? backend/app/workouts/
?? backend/tests/test_dashboard.py
?? backend/tests/test_plan_lifecycle.py
?? backend/tests/test_workouts.py
?? frontend/src/components/WorkoutForm.jsx
?? frontend/src/pages/DashboardPage.jsx
?? frontend/src/pages/HistoryPage.jsx
?? frontend/src/pages/LogWorkoutPage.jsx
?? frontend/src/pages/PlanDetailConsumerPage.jsx
?? frontend/src/pages/PlanNewPage.jsx
?? frontend/src/pages/PlansPage.jsx
?? frontend/src/pages/WorkoutDetailPage.jsx
?? frontend/src/utils/
```

11 files changed, 285 insertions(+), 99 deletions(-) on tracked files, plus the new files above. No `.env`, `*.db`, backup file, `node_modules`, or `dist` artifact appears in the status — all correctly ignored. No secrets present in any diff.

Nothing was committed yet — commit is deferred pending your review of this report (matching the "review before commit" cadence of prior phases; let me know if you'd like it committed as-is).

---

## 15. Known Limitations

- **Week-1-only scheduled detail** (Section 9) — by design, not a bug; Phase 3 candidate.
- **Workout-type vocabulary** is not normalized against the research rule engine's own workout-type strings, per approved decision #8 — the two systems use independently-defined enums today.
- **RPE** is stored as a plain 1–10 integer labeled "RPE (Rate of Perceived Exertion), 1–10" with an explicit UI hint that it is *not* the same scale as the research Likert evaluation — no cross-mapping exists between the two.
- **Pagination** was verified functionally (query params, page/page_size, total count) via the API and via the history page's filter behavior, but was not exercised with more than one page of real data in the live browser session (only one workout existed at a time in each test iteration).
- **No monthly-statistics UI** was built (this_month is computed server-side but not yet surfaced in a widget) — deliberately deferred per approved decision #6 since the frontend doesn't yet need it.
- Race distance/target for a consumer plan is read from `active_plan_row.profile.target_race_distance`; if a `RunnerProfile` row is ever missing for a plan, this falls back to `"N/A"` (not currently reachable via the UI, since `PlanNewPage` always creates a profile-backed plan).

---

## 16. Phase 3 Recommendations

(Not started, not scoped for approval here — listed only as forward-looking observations.)
- Multi-week daily schedule materialization (would require extending the rule engine's `progression_schedule` output, which Phase 2 explicitly did not touch).
- Workout-type vocabulary reconciliation between consumer logging and the research rule engine.
- Monthly/trend statistics UI surfacing the already-computed `this_month` data.
- Wearable integrations (Garmin/Strava/Apple Health/Google Health Connect) — explicitly out of scope until separately approved.
- Scheduled-workout editing (currently read-only, week-1-only).

---

## STOP

Phase 2 is complete and verified as described above. Per your instructions, work stops here: no Phase 3 features, no wearable integrations, no adaptive training logic have been started. Awaiting your review and further approval before any additional work begins.

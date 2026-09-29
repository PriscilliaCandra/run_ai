# Phase 4 Design — Progress & Training Insights

**Date:** 2026-09-29
**Status:** DESIGN ONLY. No application code, frontend code, test, migration, database, dependency file, README, or Git history was changed to produce this document. See the Git status note at the end.

---

## 1. Objective

Give a logged-in consumer a simple, honest view of their own logged training over the last few weeks — how much they ran, how many days they logged, and at most one or two plain-language observations about the trend — computed entirely deterministically from data that already exists (`workout_logs`), with **zero LLM calls, zero scores, zero predictions, and zero automatic effect on any training plan.**

Phase 4 is a **read-only aggregation and presentation layer** on top of Phases 2–3. It adds exactly one new backend endpoint and one new Dashboard section. It does not touch the rule engine, the AI personalization pipeline, the research flow, or the plan-generation/lifecycle code in any way.

---

## 2. Scope

### 2.1 Must Have

1. **Weekly volume trend** — total distance, total duration, run count, volume-weighted average pace, and logged-days count, bucketed by ISO calendar week (Monday–Sunday), for a caller-specified number of trailing weeks (default 8).
2. **Weekly logging-consistency**, expressed as `logged_days_count` (a plain count, `COUNT(DISTINCT workout_date)` per week) — the primary long-term consistency signal, independent of any training plan.
3. A **small, deterministic, template-based set of observation sentences** (at most 2), generated server-side from fixed, documented thresholds — never a free-text or LLM-generated sentence.
4. A **Dashboard "Progress" section** presenting the above, mobile-first, visually simple, with defined empty/loading/error states.

### 2.2 Deferred

- Pace-by-workout-type trend and any pace *comparison* observation (e.g. "your easy pace is faster") — the per-week volume-weighted pace number itself is Must-have (§5), but judging or comparing it across periods is deferred (§7 explains why).
- Personal-bests / PR display against `RACE`-type logs or against `user_profiles.pb_5k`/`pb_10k` — no PR logic of any kind is designed or implied here (§8 of the discovery report's Nice-to-have list).
- Long-run-distance trend (max single-workout distance per week).
- Plan-scoped week-1 completion *history* across multiple past plans (a compact "your first week, past plans" view) — Phase 3's existing single-plan week-1 completion count is unchanged and is not extended into a Phase 4 feature.
- A user-facing control to change the trend window length (no range picker in the Must-have UI; the backend parameter exists for API flexibility and testability, not because the Must-have frontend calls it with anything but the default).
- Any materialized/cached aggregate table (§12).

### 2.3 Out of Scope (restated as commitments)

Injury diagnosis, overtraining/readiness/fatigue conclusions, VO2max estimation beyond the existing `calculated_vdot` the rule engine already produces, race prediction, "ready/not ready" verdicts, any single "fitness score," automatic plan adaptation, autonomous AI coaching, user rankings, leaderboards, gamification (streaks, badges, pressure language). None of these appear anywhere in this document, and none are implied by any metric or sentence defined below.

---

## 3. Existing Data Sources

Re-confirmed against the actual current code (`backend/app/models.py`, `backend/app/workouts/service.py`, `backend/app/routes/dashboard_routes.py`) at commit `0573a31`, not assumed from memory:

| Source | Fields Phase 4 reads | Notes |
|---|---|---|
| `workout_logs` (`WorkoutLog`) | `user_id`, `workout_date` (plain `DATE`), `distance_meters`, `duration_seconds`, `workout_type`, `deleted_at` | The **only** table this feature queries. Already has `Index("ix_workout_logs_user_date", "user_id", "workout_date")` — exactly the composite index this feature's query pattern needs; no new index required. |
| `training_plan_workouts` / `training_plans` | *(not read by this feature)* | Deliberately **not** used — Phase 4's consistency metric is logging-frequency-based (`workout_logs` only), precisely because `training_plan_workouts` only ever materializes week 1 of whichever plan was active and cannot support a multi-week trend (Phase 3's known limitation, re-confirmed, not re-litigated here). |
| `user_profiles` | *(not read by this feature)* | Not needed for the Must-have slice; would only become relevant for the deferred personal-bests feature. |

No other table is touched. No research table (`runner_profiles`, `plan_evaluations`) is read or referenced anywhere in this design.

---

## 4. Weekly Window Semantics

- **Calendar convention**: ISO calendar week, **Monday–Sunday**, identical to the existing `week_start = today - timedelta(days=today.weekday())` computation already in `dashboard_routes.py`'s `get_dashboard_summary()`. No new date-math convention is introduced.
- **"Today"**: `date.today()` — the server's local date, exactly as every existing dashboard/workout computation already does (`dashboard_routes.py`, `workouts/service.py`). No timezone conversion, no per-user timezone model. This is a direct reuse of the existing project-wide convention, not a new one.
- **Current week is always included**, even though it is necessarily partial (today is somewhere inside it). It is always the **last** element of the returned `weeks` array (see ordering below).
- **Ordering: oldest week first, current week last.** Rationale: a trend array is naturally rendered left-to-right as a chart/sparkline with time increasing to the right, matching how the backend computes it (looping forward from `range_start` to `today`) and letting the frontend map the array directly onto bars with zero reordering.
- **Exactly N buckets are returned** for `?weeks=N` (§7 defines N's bounds/default). No bucket is ever skipped, merged, or omitted — an empty week is still a full bucket (§5).
- **Not a rolling 7-day window.** Every bucket boundary is a fixed Monday 00:00 → Sunday 23:59 calendar week; "last 8 weeks" means the 8 calendar weeks ending with the one containing today, not "the last 56 days."
- **`is_current_week` field**: **yes, included**, a plain boolean on every bucket. Because the current week is, by construction, the only bucket that can ever be partial (no bucket for a future week is ever produced), `is_current_week: true` is unambiguous shorthand for "this week's numbers are necessarily incomplete — today has not finished yet." No separate `is_partial` field is needed; the two would always be identical, so only one is exposed to avoid the frontend needing to reconcile two fields that can never disagree.

---

## 5. Metric Definitions

All computed over `workout_logs` rows where `user_id = current_user.id`, `deleted_at IS NULL`, `workout_date` within the bucket's `[week_start, week_end]`, inclusive. Reuses the exact formulas already implemented and tested in `_period_totals()` (`dashboard_routes.py`) — not new math.

| Metric | Definition |
|---|---|
| `total_distance_km` | `round(sum(distance_meters) / 1000.0, 2)`. `0.0` for an empty week — never `null`. |
| `total_duration_seconds` | `sum(duration_seconds)`, integer. `0` for an empty week. |
| `run_count` | `count(*)` of matching rows. `0` for an empty week. |
| `logged_days_count` | `count(DISTINCT workout_date)` of matching rows. Always `<= run_count` (two same-day runs count as one logged day). `0` for an empty week. |
| `average_pace_display` | Volume-weighted: `total_duration_seconds / (total_distance_meters / 1000.0)`, formatted via the existing `format_seconds_to_pace()` helper, e.g. `"07:15 /km"`. **`null` whenever `total_distance_meters == 0`** (empty week or a week with only zero-distance entries) — never a divide-by-zero, never a fabricated `"00:00 /km"`. Never an unweighted average of individual workouts' paces (same rule as Phase 2's `test_average_pace_is_volume_weighted_not_averaged_per_workout`). |

**Inclusion rules, all explicit and non-negotiable**:
- Soft-deleted workouts (`deleted_at IS NOT NULL`) are **always excluded** — no exception anywhere in this feature.
- Workouts with **no `training_plan_workout_id`** (standalone logs) **count fully** toward every metric above — Phase 4 does not distinguish plan-linked from standalone workouts at all.
- `RACE`-type workouts **count fully** toward every metric above — no separate bucket, no exclusion, matching the existing Phase 2 decision that races are real training volume.
- No aggregate value is ever persisted to any table. Every number above is recomputed from raw `workout_logs` rows on every request.

---

## 6. Observation Rules

The most safety-sensitive part of this design; every rule below is fully deterministic and independently unit-testable with a hand-computed fixture.

### 6.1 Fixed internal lookback (independent of the `?weeks=` query parameter)

Observations always compare two fixed, non-overlapping 3-week windows drawn from the **most recently fully-completed weeks**, deliberately excluding the current (partial) week from both windows:

- **Recent window**: the 3 calendar weeks immediately before the current week (i.e., current-week-minus-1, -2, -3).
- **Prior window**: the 3 calendar weeks immediately before the recent window (current-week-minus-4, -5, -6).

This requires the backend to have fetched at least 7 weeks of bucketed data (current week + 6 preceding weeks) regardless of what `?weeks=` was requested for the chart (§7/§8 define how one single query still satisfies this).

### 6.2 Observation 1 — Weekly volume trend

- **Input metrics**: `total_distance_km` per week (from §5), summed across each 3-week window → `recent_total_km`, `prior_total_km`.
- **Minimum sample requirement (eligibility gate, both must hold)**:
  - `sum(run_count)` across the recent window `>= 2`, **and**
  - `sum(run_count)` across the prior window `>= 2`, **and**
  - `prior_total_km >= 5.0` (a fixed floor so a tiny prior baseline — e.g. 0.5 km — cannot produce a triple-digit "percent increase").
- If the gate fails, **no volume observation is generated** — this is not an error condition, it is simply "not enough data yet," and the frontend receives no entry for it (§6.4).
- **Comparison**: `percent_change = (recent_total_km - prior_total_km) / prior_total_km * 100`, computed from the raw (unrounded) sums, not from display-rounded values, to avoid a rounding artifact flipping the threshold decision.
- **Threshold**:
  - `percent_change >= 10` → **increased**
  - `percent_change <= -10` → **decreased**
  - otherwise (between -10 and +10, inclusive of neither being triggered) → **no observation** ("essentially unchanged" is deliberately not reported as its own sentence — silence is the correct signal here, not a third templated sentence).
- **Sentence templates** (no embedded numbers, by design — see §6.5):
  - Increase: *"Your weekly running distance has increased over the last 3 weeks compared to the 3 weeks before that."*
  - Decrease: *"Your weekly running distance has decreased over the last 3 weeks compared to the 3 weeks before that."*

### 6.3 Observation 2 — Logging-consistency trend

- **Input metrics**: `logged_days_count` per week, summed across each 3-week window → `recent_days_total`, `prior_days_total` (each naturally in `0..21`).
- **Minimum sample requirement (eligibility gate)**: `prior_days_total >= 3` (at least some real logging history in the earlier window — a prior window of zero or one logged day is too sparse a baseline to compare against).
- **Comparison**: `day_difference = recent_days_total - prior_days_total` (a plain integer difference, not a percentage — avoids any divide-by-zero and is trivially easy to reason about and test).
- **Threshold**:
  - `day_difference >= 2` → **more often**
  - `day_difference <= -2` → **less often**
  - otherwise (`-1, 0, +1`) → **no observation**.
- **Sentence templates**:
  - More often: *"You've logged workouts on more days over the last 3 weeks compared to the 3 weeks before that."*
  - Less often: *"You've logged workouts on fewer days over the last 3 weeks compared to the 3 weeks before that."*

### 6.4 Insufficient data

There is no separate "insufficient data" flag or sentence. Each observation's own eligibility gate (§6.2/§6.3) already organically produces the correct behavior: a brand-new account, or one with a sparse or zero-activity prior window, simply fails the gate and that observation is omitted from the response. The frontend never needs to distinguish "we checked and there's no trend" from "we didn't have enough data to check" — both are represented identically by the observation's absence.

### 6.5 Rounding / no embedded numbers

Sentences never quote a specific number (no "+23%", no "5 more days"). This is a deliberate choice: it keeps the sentence honest and non-overstating ("increased" is a true, minimal claim; a quoted percentage invites over-interpretation of what is still a fairly noisy recreational-running signal) and it entirely sidesteps needing to define a rounding/formatting convention *inside* the sentence text. The underlying weekly numbers used to compute eligibility and direction are still available to the frontend as plain per-week figures in the `weeks` array (§7) if a future phase wants to show them alongside the sentence.

### 6.6 Maximum count and ordering

- **Maximum 2 observations** are ever returned, matching the two observation types defined above — there is currently no third type, so the cap and the type count are numerically identical today.
- **Fixed priority order when both are eligible**: Volume trend (§6.2) is always listed before Consistency trend (§6.3). This ordering is a hardcoded convention for this document; if a future phase adds a third observation type, that phase must explicitly extend this ordered list rather than leaving order undefined.
- **Tie/no-change behavior**: explicitly defined per observation above (§6.2/§6.3's "otherwise" branches) — never a silent default, always an explicit "no observation for this type" outcome.

### 6.7 What this section deliberately never does

No medical, physiological, predictive, or performance-quality claim. No word like "better," "worse," "improving," "good," or "bad" appears in any template — only neutral, directional, descriptive language ("increased," "decreased," "more often," "fewer days"), matching the existing Phase 3 UX convention of never phrasing something as a judgment (e.g. "Not logged" instead of "Missed").

---

## 7. API Design

**Single new endpoint, reusing every existing pattern — no other endpoint is added.**

```
GET /api/dashboard/progress?weeks=8
```

| Aspect | Decision |
|---|---|
| **Method / route** | `GET /api/dashboard/progress` (new router function in `dashboard_routes.py`, same router/prefix as the existing `/api/dashboard/summary`) |
| **Query parameter** | `weeks: int = Query(8, ge=1, le=26)` — default **8**, minimum **1**, maximum **26** (roughly 6 months; a fixed, generous but bounded ceiling, matching the existing `page_size: int = Query(20, ge=1, le=100)` convention in `workout_routes.py`). |
| **Invalid input** | Handled entirely by FastAPI/Pydantic's existing `Query(..., ge=..., le=...)` validation, which already produces the same `422` shape as every other bounded query parameter in this codebase (e.g. `list_workouts`'s `page_size`) — no new validation code needed. |
| **Auth** | Required: `Depends(get_current_user)`, identical to `/api/dashboard/summary`. |
| **Ownership** | The single SQL query (§12) filters `WorkoutLog.user_id == current_user.id` directly in the `WHERE` clause — never filtered after fetching. No client-supplied `user_id`, ownership ID, or arbitrary identifier is accepted anywhere in this endpoint (its only input is the bounded integer `weeks`). |
| **Deleted-workout filtering** | `WorkoutLog.deleted_at.is_(None)` in the same query. |
| **Observations: backend or frontend?** | **Backend.** Centralizes the rules in one testable Python module, matches the explicit recommendation, and prevents the frontend from ever needing to reimplement (or subtly drift from) the thresholds in §6. |
| **Response shape** | See below. |

```json
{
  "weeks": [
    {
      "week_start": "2026-08-10",
      "week_end": "2026-08-16",
      "is_current_week": false,
      "total_distance_km": 12.4,
      "total_duration_seconds": 5400,
      "run_count": 3,
      "logged_days_count": 3,
      "average_pace_display": "07:15 /km"
    },
    {
      "week_start": "2026-09-28",
      "week_end": "2026-10-04",
      "is_current_week": true,
      "total_distance_km": 0.0,
      "total_duration_seconds": 0,
      "run_count": 0,
      "logged_days_count": 0,
      "average_pace_display": null
    }
  ],
  "observations": [
    "Your weekly running distance has increased over the last 3 weeks compared to the 3 weeks before that."
  ]
}
```

- `weeks` always has exactly `weeks` (the query parameter) entries, oldest first, current week last, **every** entry present even if all-zero (§4/§5).
- `observations` is a plain array of 0, 1, or 2 strings (§6.6), always present as a key (an empty array, not `null`, when nothing is eligible).

---

## 8. Backend Architecture

- **New Pydantic schemas** in `app/workouts/schemas.py`: `WeeklyProgressBucket` (the object shape inside `weeks`) and `ProgressResponse` (`weeks: List[WeeklyProgressBucket]`, `observations: List[str]`). Purely additive — no existing schema is modified.
- **New pure functions** in `app/workouts/service.py` (the existing home for workout-domain business logic, alongside `scheduled_date_for`/`derive_completion_status` from Phase 3):
  - `bucket_weekly_totals(rows: List[WorkoutLog], range_start: date, num_weeks: int) -> List[WeeklyProgressBucket]` — pure, given already-fetched rows and a start date, returns exactly `num_weeks` buckets, oldest first. Fully unit-testable with a hand-built list of fake `WorkoutLog`-shaped objects, no database needed.
  - `generate_observations(buckets: List[WeeklyProgressBucket]) -> List[str]` — pure, given the last 7 buckets (current + 6 back), applies §6's rules and returns 0–2 strings. Fully unit-testable with hand-picked numeric fixtures — no database, no HTTP layer.
- **New route handler** in `app/routes/dashboard_routes.py`:
  1. Compute `current_week_start` exactly as `get_dashboard_summary()` already does.
  2. `fetch_span_weeks = max(weeks, 7)` (7 = the fixed observation lookback from §6.1; guarantees a single query always has enough data for observations regardless of the requested `weeks`).
  3. One query: all non-deleted `WorkoutLog` rows for `current_user.id` with `workout_date` in `[current_week_start - (fetch_span_weeks - 1) * 7 days, current_week_start + 6 days]`.
  4. `all_buckets = bucket_weekly_totals(rows, range_start, fetch_span_weeks)`.
  5. `observations = generate_observations(all_buckets[-7:])` (the trailing 7 buckets — current + 6 back — always present because of step 2's guarantee).
  6. Response `weeks = all_buckets[-weeks:]` (the trailing `weeks` buckets the caller actually asked for), `observations = observations`.
- **No existing function is modified.** `_period_totals()`, `get_dashboard_summary()`, and every Phase 2/3 route/schema are left exactly as they are. This endpoint is purely additive, callable independently.

---

## 9. Frontend / UX Design

**New component**: a `ProgressSection` (or similarly named) block added to `DashboardPage.jsx`, positioned **below** the existing "This Week" stat grid and "Training Plan" card (neither of which is modified) — Phase 4 is a distinct, separate section, not a rework of what Phases 2–3 already built.

**Content** (deliberately small, per the brief):
- A row of `weeks` (8 by default) simple bars — plain `<div>` height-percentage bars exactly like the existing plan-progress bar pattern already used in `DashboardPage.jsx`/`PlanResultPage.jsx`, **no new charting dependency**. Each bar represents one week's `total_distance_km`; the current (rightmost) bar is visually marked as partial (e.g. a lighter shade or a dashed outline) using the `is_current_week` field — never silently presented as if it were a complete week.
- Below the chart: `"{logged_days_count} days logged this week"` for the current week's bucket — a single plain-text line, not a new "Stat" tile grid (avoiding duplicating the existing "This Week" grid's "Runs" tile).
- At most 2 observation sentences, plain text, no icon implying judgment (no up/down arrow colored green/red — that itself would smuggle in a "good/bad" framing; a neutral bullet or plain paragraph is used instead).
- **Nothing else.** No duration/pace tile is added to this section by default — `average_pace_display` per week exists in the API response for a future phase to use, but the Must-have UI does not surface a second numeric grid here, to keep the section small per the explicit instruction to avoid an "analytics dashboard."

**States**:
- **Loading**: reuse the existing `LoadingState` component, exactly as every other Phase 2/3 section does.
- **Empty** (zero workouts ever logged): reuse `EmptyState`, message *"Log a few workouts to start seeing your progress here."* — no chart, no observations, no zero-bars rendered (an all-zero chart for a brand-new user adds visual noise with no information).
- **Populated, but zero observations eligible**: the chart renders normally; the observations area is simply omitted (no "not enough data" placeholder text — consistent with §6.4's decision that absence is itself the signal).
- **Error**: reuse `ErrorState` with a "Try Again" action, identical to every other dashboard section's existing error handling.

**Explicitly not present anywhere in this section**: streak counters, badges, a numeric "score" of any kind, color-coded up/down judgment arrows, comparisons to other users, or any "level"/"tier" language.

**Responsive behavior**:
- **375px**: the bar row must fit without horizontal scroll or overflow — bars shrink in width (not in count; all `weeks` bars still render, just narrower) using the same flex/grid-based approach already used for the plan-progress bar and stat grids elsewhere in `DashboardPage.jsx`. Text wraps normally; no fixed pixel widths.
- **768px / 1440px**: same component, simply more horizontal room per bar — no structural change, no new breakpoint-specific layout, consistent with how the rest of the Dashboard already scales.
- Verified the same way every prior phase was verified: `scrollWidth <= innerWidth` measured directly in-browser at all three widths, not eyeballed from a screenshot (Phase 2/3's own documented lesson about screenshot-capture artifacts).

---

## 10. Research Isolation

- **Files this feature touches**: `app/workouts/schemas.py` (additive schemas), `app/workouts/service.py` (additive pure functions), `app/routes/dashboard_routes.py` (one new route handler), `frontend/src/pages/DashboardPage.jsx` (one new section). **Nothing else.**
- **Files this feature explicitly does not touch, at all**: `app/rules/` (VDOT, pace zones, periodization), `app/ai/` (LLM service, validator, prompts), `app/routes/evaluation_routes.py`, `app/schemas.py`'s research-facing models (`RunnerProfileCreate`, `WorkoutItem`, `PlanGenerationResponse`), and every `/research/*` frontend page.
- **Structural guarantee, not just a promise**: `GET /api/dashboard/progress` requires `get_current_user` (a valid authenticated session). An anonymous research plan has no associated `User` and no session — it is categorically unreachable through this endpoint. Separately, anonymous research submissions have no concept of a "logged workout" at all (`workout_logs.user_id` is `NOT NULL` by schema, and research plans never create `WorkoutLog` rows) — there is no research data of any kind that this query could ever accidentally include, even in principle.
- **Verification commitment for implementation time** (not performed now, since this is a design document): re-run the research flow end-to-end (generate → evaluate → statistics) exactly as done for Phases 1–3, and confirm `git diff --stat` against `app/rules/`, `app/ai/`, `evaluation_routes.py` is empty, before calling Phase 4 implementation complete.

---

## 11. Security & Ownership

- Same authentication mechanism as every existing consumer endpoint — no new session, cookie, or token type.
- Same ownership pattern as every existing endpoint — `user_id` is taken exclusively from `current_user.id` (derived from the session), never from any request input. This endpoint's only client input is the bounded integer `weeks`; there is no field anywhere a client could even attempt to smuggle a foreign `user_id` through.
- Same CSRF posture as today: this is a `GET` request, so it is not subject to the existing Origin-check middleware (which only guards state-changing methods) — consistent with every other `GET` in this codebase.
- Same rate-limiting posture as `GET /api/dashboard/summary` and `GET /api/workouts`: **not** independently rate-limited, since it performs no LLM call and no write — consistent with the existing project's rule that only LLM-backed or mutating endpoints carry a dedicated limit.
- Mandatory two-user ownership test (§13) is a hard requirement before this is considered done, mirroring the mandatory pattern from every prior phase.

---

## 12. Performance

- **Exactly one database query per request**, described precisely in §8 step 3 — never more, regardless of the `weeks` value chosen within its bounds.
- The existing composite index `ix_workout_logs_user_date (user_id, workout_date)` already covers this query's `WHERE user_id = ? AND workout_date BETWEEN ? AND ?` access pattern exactly — **no new index is proposed.**
- Bucketing (§8 step 4) and observation generation (§8 step 5) are pure in-memory Python operations over at most `26 weeks * (a recreational user's realistic weekly run count, typically 1–7)` rows — trivially fast at this scale.
- **No aggregation table, cache, background job, or materialized view is introduced.** The repository has not demonstrated any need for one (this is a brand-new feature with zero production traffic history to justify pre-optimizing), and computing on read keeps the numbers always-correct with no rollup-vs-source-of-truth drift risk — the same philosophy Phase 2 already chose for `_period_totals()`. This should only be revisited if real usage data later shows a measurable latency problem.

---

## 13. Testing Strategy

Proposed new file: `backend/tests/test_progress.py` (a dedicated file, matching the precedent set by Phase 3's `test_workout_linking.py` rather than overloading `test_dashboard.py`).

**Unit tests (pure functions, no HTTP/DB needed)**:
1. `bucket_weekly_totals`: given a fixed list of fake workout rows spanning exactly one ISO week (Monday–Sunday), returns one correctly-summed bucket.
2. `bucket_weekly_totals`: a workout dated exactly on a Sunday vs. the following Monday lands in the correct, different bucket (week boundary test, mirroring Phase 2's existing boundary test).
3. `bucket_weekly_totals`: a window spanning a month boundary (e.g. Jan 29 – Feb 4) buckets correctly.
4. `bucket_weekly_totals`: a window spanning a year boundary (e.g. Dec 29 – Jan 4) buckets correctly.
5. `bucket_weekly_totals`: the current (today's) week bucket is correctly marked `is_current_week=True` and is always the last bucket returned.
6. `bucket_weekly_totals`: an empty week (zero matching rows) returns `total_distance_km=0.0, total_duration_seconds=0, run_count=0, logged_days_count=0, average_pace_display=None` — not a missing bucket, not an exception.
7. Volume-weighted pace: a week with two unequal-distance workouts (e.g. 5 km @ 4:00/km and 15 km @ 6:00/km) produces the correct weighted result (5:30/km), not the naive unweighted average (5:00/km) — same style as Phase 2's existing pace test.
8. `logged_days_count`: two workouts on the same calendar date count as 1 logged day, not 2.
9. Standalone workouts (`training_plan_workout_id IS NULL`) and `RACE`-type workouts both count fully toward every metric — explicit regression-style assertions.
10. `generate_observations`: a fixture with `>= 10%` volume increase and both windows meeting the run-count gate → exactly the "increased" sentence.
11. `generate_observations`: symmetric case → "decreased" sentence.
12. `generate_observations`: a change strictly between -10% and +10% → no volume observation.
13. `generate_observations`: prior window total distance below the 5.0 km floor → no volume observation even if the percentage would otherwise qualify.
14. `generate_observations`: recent or prior window run count below 2 → no volume observation.
15. `generate_observations`: logging-consistency "more often" / "fewer days" / no-observation cases, mirroring 10–12 with the day-count thresholds.
16. `generate_observations`: both observations eligible simultaneously → both returned, in the fixed order (volume first).
17. `generate_observations`: brand-new account / all-zero history → empty list, no exception.

**API tests** (`TestClient`, real (test) database):
18. `GET /api/dashboard/progress` requires authentication → `401` when not logged in.
19. Default `weeks=8` returns exactly 8 buckets.
20. `weeks=1` and `weeks=26` (boundary values) both succeed; `weeks=0` and `weeks=27` both return `422`.
21. Deleted workouts (soft-deleted via the existing `DELETE /api/workouts/{id}`) are excluded from every bucket they would otherwise have appeared in.
22. A fixture of 7+ weeks of known workout data produces a hand-computed, exact expected JSON response (buckets and observations both) — at least one full end-to-end fixture test, not only isolated unit tests.
23. Zero-workout new user → all buckets zero-valued, `observations: []`, `200` (never an error).

**Ownership (mandatory)**:
24. User B's workouts never appear in User A's `GET /api/dashboard/progress` response — direct two-user test mirroring `test_user_a_workout_not_readable_updatable_or_deletable_by_user_b`.

**Regression**:
25. Full existing suite (150 tests as of commit `0573a31`) continues to pass unmodified.
26. The anonymous research flow (`generate → evaluate → statistics`) is manually re-verified end-to-end with zero behavioral change, exactly as performed for every prior phase.

**Frontend** (manual, three-viewport, matching the established project ritual):
27. Empty state, populated state (with and without eligible observations), and error state all render correctly at 375px / 768px / 1440px with no horizontal overflow (`scrollWidth <= innerWidth`, measured, not eyeballed) and no new console errors.

Every metric in §5 and every threshold in §6 has at least one test above with a hand-computable expected value — nothing is "tested" only by eyeballing output.

---

## 14. Acceptance Criteria

Each statement below is objectively checkable — pass or fail, no subjective wording:

1. `GET /api/dashboard/progress?weeks=8` returns exactly 8 bucket objects, oldest first, current week last.
2. Every bucket object contains all 7 documented fields (`week_start`, `week_end`, `is_current_week`, `total_distance_km`, `total_duration_seconds`, `run_count`, `logged_days_count`, `average_pace_display`); no field is ever omitted.
3. For a week with `run_count == 0`, `average_pace_display` is exactly `null` and `total_distance_km`/`total_duration_seconds`/`logged_days_count` are exactly `0`/`0`/`0`.
4. `weeks=0` and `weeks=27` both return HTTP `422`; `weeks=1` and `weeks=26` both return HTTP `200`.
5. A soft-deleted workout (`deleted_at IS NOT NULL`) never contributes to any bucket's totals, verified by an automated test that deletes a workout and re-fetches the endpoint.
6. A hand-computed fixture of exactly 7 weeks of known workout data produces byte-for-byte the expected JSON for both `weeks` and `observations`.
7. The volume observation appears if and only if `percent_change >= 10` or `<= -10` **and** both windows have `run_count >= 2` **and** `prior_total_km >= 5.0`; verified by at least 4 automated tests covering each boundary independently.
8. The consistency observation appears if and only if `day_difference >= 2` or `<= -2` **and** `prior_days_total >= 3`; verified by at least 3 automated tests.
9. `observations` never contains more than 2 entries, and when both are eligible, the volume sentence always precedes the consistency sentence.
10. No sentence template contains a numeral, a comparative-quality word ("better," "worse," "good," "bad"), or a medical/predictive term.
11. `GET /api/dashboard/progress` returns `401` with no session cookie.
12. An automated two-user test proves User B's workout data never appears in User A's response.
13. `git diff --stat` against `app/rules/`, `app/ai/`, and `app/routes/evaluation_routes.py` is empty at the time Phase 4 implementation is declared complete.
14. All 150 pre-existing tests (as of `0573a31`) pass unmodified, plus every new test in §13 passes.
15. The research flow (generate → evaluate → statistics) is manually re-verified end-to-end with zero behavioral change.
16. The Dashboard's new Progress section renders with zero horizontal overflow (`scrollWidth <= innerWidth`, measured) at 375px, 768px, and 1440px.
17. No new npm or pip dependency appears in `package.json`/`requirements.txt`.
18. No new Alembic migration file exists beyond `0003_add_workout_logging.py` unless a schema change was separately proposed and approved (none is proposed by this document).

---

## 15. Future AI Boundary

Phase 4 stops at the "Deterministic Aggregation" step below and goes no further. This is restated exactly as scoped, for the avoidance of doubt at implementation time:

```
Raw Workout Data (workout_logs — Phases 2/3, unchanged)
        ↓
Deterministic Aggregation  ← PHASE 4 STOPS HERE
   weekly volume, weekly logged-days, §6's two fixed observation rules
        ↓
   [FUTURE PHASE ONLY] Rules / Safety Context
   (the existing, unmodified rule engine's own constraints: VDOT,
   80/20 split, ≤10%/week progression, long-run cap)
        ↓
   [FUTURE PHASE ONLY] LLM Personalization — text only, same constraint
   already enforced today: the LLM cannot set any physiological number
        ↓
   [FUTURE PHASE ONLY] Server Validation — same numeric/structural
   re-check pattern as the existing app/ai/validator.py
        ↓
   [FUTURE PHASE ONLY] User Confirmation — shown, never silently applied
        ↓
   [FUTURE PHASE ONLY] New Plan / New Version
```

**NEVER AUTOMATIC, restated as an absolute rule**: a workout log — logging it, editing it, or deleting it — must never, in Phase 4 or any future phase, automatically modify an existing `training_plans` row. Nothing in this design writes to `training_plans` or `training_plan_workouts` anywhere; `GET /api/dashboard/progress` is read-only by construction (a `GET` handler with no `db.add`/`db.commit` of anything).

The only thing Phase 4 produces that a future phase *could* eventually feed into the box above is the same weekly aggregate numbers already defined in §5 — as **read-only context**, never as a trigger.

---

## 16. Implementation Order

1. `app/workouts/schemas.py`: add `WeeklyProgressBucket`, `ProgressResponse` (additive only).
2. `app/workouts/service.py`: add `bucket_weekly_totals()` and `generate_observations()` as pure functions; unit-test both in isolation (§13 items 1–17) before wiring up any route.
3. `app/routes/dashboard_routes.py`: add the `GET /api/dashboard/progress` handler per §8; add API-level tests (§13 items 18–24).
4. Run the full existing suite (150 tests) to confirm zero regression; re-verify the research flow manually.
5. Frontend: add the new Progress section to `DashboardPage.jsx` per §9; no other page is touched.
6. Manual three-viewport verification (§13 item 27).
7. Final `git diff --stat` check against `app/rules/`/`app/ai/`/`evaluation_routes.py` confirming emptiness, then compile the Phase 4 implementation report following the same format as `PHASE_2_REPORT.md`.

---

## 17. Open Questions

None. Every decision point raised in the implementation-approval request (weekly window semantics, "today"/timezone handling, volume metric definitions, empty-week representation, observation thresholds/rounding/ordering, consistency wording, pace handling, personal-bests deferral, plan-linked-completion boundary, API shape/bounds/ownership, performance approach, frontend scope, research isolation, security, and the future-AI boundary) has been resolved explicitly above using the existing architecture's own established conventions, rather than left open.

One item is noted for completeness, though it does not block implementation: whether a future phase should let the user adjust the trend window length via a UI control (§2.2 defers this) is a product-polish decision, not a technical unknown — the backend's `weeks` parameter already supports it whenever it's wanted.

---

## Design Status

**DESIGN COMPLETE — WAITING FOR IMPLEMENTATION APPROVAL**

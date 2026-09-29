# Phase 5 Discovery — Multi-Week Training Plans

**Date:** 2026-09-29
**Source of truth:** actual repository state at commit `7c34963` (Phase 4). Every claim below was verified by reading the current code, not by trusting prior phase reports. Where this prompt's assumptions differ from what the code actually does, the discrepancy is called out explicitly rather than silently resolved.
**Status:** DISCOVERY / DESIGN ONLY. No application code, test, migration, database, or dependency was changed to produce this document.

---

## 1. Executive Summary

The single most important finding of this discovery: **the Phase 3/4 scheduling, linking, completion-derivation, and progress infrastructure was already built week-agnostically.** `_resolve_owned_training_plan_workout`, `_get_owned_workout_or_404`, `build_enriched_tpw_response`, `derive_completion_status`, `is_rest_day`, `bucket_weekly_totals`, and `generate_observations` contain **zero** hardcoded assumption that only week 1 exists — they operate on whatever `TrainingPlanWorkout`/`WorkoutLog` rows are actually present. The `training_plan_workouts` table's own schema (`week_number INTEGER`, unique on `(training_plan_id, week_number, day_of_week)`) already fully supports any number of weeks. `GET /api/plans/{id}/workouts` already returns **every** row for a plan with no week filter at all.

What is genuinely week-1-only today is narrower than it first appears:
1. The **rule engine** (`app/rules/generator.py`) only calls its own per-week workout distributor (`distribute_workouts_across_week()`) **once**, for week 1.
2. The **materialization helper** (`materialize_week_one()`) only ever writes week 1's rows.
3. Two **route-level gates** explicitly hardcode `week_number == 1` / `current_week == 1` (`dashboard_routes.py`), purely because no other week's rows exist yet — not because the surrounding architecture requires it.
4. The **AI personalization pipeline** (`app/ai/prompts.py`, `app/ai/schemas.py`, `app/ai/validator.py`) is shaped around a single week's 7 workouts end-to-end, and the consumer frontend (`PlanNewPage.jsx`) hardcodes `plan_duration_weeks: 8` with no UI to change it, despite the backend already validating `4 <= plan_duration_weeks <= 24`.

**Recommendation (detailed in §5–§7):** extend the deterministic rule engine to produce full daily detail for every week by looping its *already-generic* `distribute_workouts_across_week()` function over `progression_schedule`'s per-week mileage figures — a bounded, deterministic, non-AI change — and materialize every week's rows into the existing `training_plan_workouts` table at generation time (same table, same columns, **zero schema change**). Leave `app/ai/` completely untouched for Phase 5: weeks 2+ get lean, rule-based fields (type/distance/pace/intensity/purpose) with no AI-generated prose, reusing the exact rendering pattern already proven by `DashboardPage.jsx`'s `TodayWorkoutCard`. This keeps the AI pipeline's cost, validation surface, and risk exactly as they are today.

---

## 2. Current Architecture

Verified by reading the actual files at `7c34963`:

- **`backend/app/models.py`**: `TrainingPlan` (`id, runner_profile_id, user_id [nullable], start_date [nullable], status [nullable, free-text VARCHAR(20)], calculated_vdot, target_pace, rule_based_plan_json, ai_plan_json, explainability_summary, ai_model_used, created_at`), `TrainingPlanWorkout` (`id, training_plan_id, week_number, day_of_week, workout_type, distance_meters, pace_target, intensity_zone, purpose, created_at`, unique on `(training_plan_id, week_number, day_of_week)`), `WorkoutLog` (`id, user_id [NOT NULL, FK to users], workout_date, distance_meters, duration_seconds, workout_type, ..., training_plan_workout_id [nullable], deleted_at`). No `plan_duration_weeks`/`total_weeks` column exists anywhere — duration is only ever derived from `len(rule_based_plan_json["progression_schedule"])`.
- **`backend/app/rules/generator.py`**: `distribute_workouts_across_week(profile, paces, target_pace_str, weekly_mileage)` is a **generic, already-reusable** per-week distributor (long-run day, quality day, easy days, rest days, 80/20 split) — it is called exactly **once** today, for week 1, using `profile.current_weekly_mileage`. `generate_weekly_progression_summary()` separately produces `progression_schedule`: a list of `{week_number, target_mileage_km, phase, focus_note}` for every week — a single target number per week, **no day-by-day breakdown**, and **already handles any `total_weeks` correctly** (deload every 4th week, taper on the last 1-2 weeks).
- **`backend/app/ai/{prompts,llm_service,schemas,validator}.py`**: `build_user_prompt()` sends only `rule_plan["week_1_plan"]` to the LLM; the requested/returned JSON schema (`AIPersonalizedPlan`) is a flat 7-workout list with no week dimension; `validate_ai_plan()` checks that list against `week_1_plan` only; `generate_offline_ai_plan()` (the deterministic fallback) likewise only ever templates `rule_plan["week_1_plan"]["workouts"]`. The entire AI layer is architecturally single-week.
- **`backend/app/workouts/service.py`**: `materialize_week_one()` hardcodes `week_number=1` and reads only `rule_plan["week_1_plan"]["workouts"]`. `scheduled_date_for(plan_start_date, day_of_week)` maps a weekday name to a date within the **first** 7-day window only (no week offset parameter exists). `archive_previous_active_plans`, `is_rest_day`, `derive_completion_status`, `build_enriched_tpw_response`, `bucket_weekly_totals`, `generate_observations` are all week-number-agnostic.
- **`backend/app/routes/plan_routes.py`**: `generate_plan()` calls `materialize_week_one()` unconditionally for authenticated requests. `get_plan_workouts()` (`GET /api/plans/{id}/workouts`) has **no week filter** — `db.query(TrainingPlanWorkout).filter(TrainingPlanWorkout.training_plan_id == plan_id)` returns every row for the plan regardless of `week_number`, ordered by `(week_number, id)`. This endpoint already works for multi-week data with zero backend change.
- **`backend/app/routes/dashboard_routes.py`**: computes `current_week = min(max(1, (today - plan_start).days // 7 + 1), total_weeks)` — already correct for any `total_weeks`. But then gates everything behind `week1_detail_available = (current_week == 1)` and queries `TrainingPlanWorkout.week_number == 1` explicitly — these two lines are the **only** places that actively prevent week 2+ from ever being shown, and only because no such rows exist to show.
- **Frontend `PlanNewPage.jsx`**: `plan_duration_weeks: 8` is a hardcoded literal in the initial form state; there is no input field for it anywhere in the consumer UI, unlike the research `CreatePlanPage.jsx`, which does expose a duration selector.
- **Frontend `PlanDetailConsumerPage.jsx`**: renders week-1 cards from **two** sources simultaneously — `plan.ai_personalized_plan.workouts` (the rich, AI-text JSON, week-1-shaped only) for the card content, merged by `day_of_week` string with `fetchPlanWorkouts(id)`'s enriched `TrainingPlanWorkoutResponse` array for completion badges/CTA/planned-vs-actual. For weeks 2+, the first source will not exist (the JSON has no such data unless the AI layer is extended — see §1) — only the second, lean source will.
- **Frontend `DashboardPage.jsx`**: `TodayWorkoutCard` already renders `WorkoutCard` from a **lean** object (`{day, workout_type, distance_km, pace_target, intensity_zone, purpose}` — no `warmup_cooldown`/`workout_execution`) — proving `WorkoutCard` already degrades gracefully without AI prose. This is the exact rendering pattern Plan Detail's week 2+ view can reuse.

---

## 3. Current Week-1 Limitation

**Root cause, precisely**: it is **not** a database limitation and **not** a "materialization vs. JSON" architecture choice — it is that **the rule engine itself only ever generates one week's worth of daily-detail workouts.** `progression_schedule` proves the engine already computes a safe per-week mileage target for every week of the plan; it simply never converts that number into actual scheduled workouts (day placement, quality/long-run/easy split) for anything past week 1.

Answering the prompt's specific investigation questions directly:

| Question | Answer |
|---|---|
| Where is the generated plan stored? | `training_plans.rule_based_plan_json` / `.ai_plan_json` (full JSON blobs), plus normalized `training_plan_workouts` rows for week 1 only. |
| What does the plan JSON contain? | `vdot`, `target_pace_per_km`, `paces`, `week_1_plan` (7 fully-detailed workouts), `progression_schedule` (mileage-only per week), `explainability`. |
| Do weeks 2+ already exist in the stored JSON? | **No** — only a single target mileage number per week, no day-by-day breakdown, no workout types, no paces. |
| Is only the DB materialization week-1-only, or the generator too? | **Both.** The generator's reusable per-week function is only invoked once; the materialization helper only reads `week_1_plan`. |
| Does the AI prompt have enough information for multi-week detail? | **No** — it is sent only `week_1_plan` and its response schema has no week dimension. Extending this is a real, separate change (§7). |
| How does `training_plan_workouts` get populated? | `materialize_week_one()`, called once inside `generate_plan()` for authenticated requests only. |
| How is `day_of_week` represented? | A weekday name string (`"Monday"`..`"Sunday"`), verbatim from the rule engine's `WorkoutItem.day`. |
| How are scheduled dates derived? | `scheduled_date_for(plan_start_date, day_of_week)` — maps a weekday name to the one date within `[start_date, start_date+6]` matching that name. **Only handles the first week today** — no week offset. |
| How is `start_date` used? | Set to `date.today()` at generation time for consumer plans only (`plan_routes.py`); anonymous research plans never set it. |
| How is plan duration represented? | Not stored as its own field — derived as `len(progression_schedule)` wherever needed (`dashboard_routes.py`). |
| How do archived/active plans work? | `TrainingPlan.status` is a free-text column; code only ever writes `'active'` or `'archived'` (see §9 — **no `'draft'` or `'completed'` value is ever set anywhere in the current codebase**, contrary to this prompt's assumption of a 4-state lifecycle). |
| How do actual workout logs link to scheduled workouts? | `workout_logs.training_plan_workout_id` (nullable FK), ownership-verified server-side by `_resolve_owned_training_plan_workout()` — entirely week-number-agnostic already. |

**Data classification, as requested:**
1. **Already available**: per-week mileage targets (`progression_schedule`), the reusable per-week distribution algorithm, the full `training_plan_workouts` schema, week-agnostic linking/completion/progress code, `start_date`, ownership patterns.
2. **Must be generated**: per-week day-by-day workout detail (type, distance, pace, intensity, purpose) for weeks 2 through N — a deterministic rule-engine extension.
3. **Must be persisted**: the generated weeks 2+ rows, into the existing `training_plan_workouts` table (no new table, no new column).
4. **Must only be derived, never stored**: `scheduled_date` for every week (generalizing the existing pure function with a week offset), `completion_status` (already derived, unchanged), "is this plan finished" (§9 — recommended as derived, not a new stored status).

---

## 4. Existing Data Model

`training_plan_workouts` already has everything needed for week number, calendar day, workout type, planned distance, pace target, intensity, and purpose — these are its existing columns, already populated correctly for week 1, and require **no schema change** to hold the same data for weeks 2+.

Reviewing each candidate additional field the prompt asks me to consider, against a concrete Phase 5 use case:

| Candidate field | Concrete Phase 5 use case? | Recommendation |
|---|---|---|
| Scheduled date persisted vs. derived | Currently derived (`scheduled_date_for`); a week-number-aware version of the same pure function still fully covers multi-week — no use case forces persistence. | Keep derived. No new column. |
| Workout order (within a day) | No Phase 5 feature ever needs more than one workout per `(plan, week, day)` — the existing unique constraint already assumes exactly one. | Not needed. |
| Workout duration | Nothing in the rule engine computes a target *duration* today (only distance + pace, from which a duration is inferable but never asked for) — no consumer feature in this discovery's Must-have needs it. | Not needed for Phase 5. |
| Interval structure (reps/sets) | `pace_target` already carries this as a string today (e.g. `"04:49 /km (Reps) / Easy Jog (Rest)"`) for week 1; extending to weeks 2+ reuses the same string convention. | No new field — reuse the existing string pattern. |
| Warm-up/cool-down, notes/instructions | These exist **only** in the AI-plan JSON today, not in `training_plan_workouts` at all (confirmed: the table has no such columns even for week 1). Adding them would require the AI layer extension explicitly deferred in §1/§7. | Not needed for Must-have; a Nice-to-have only if the AI layer is later extended (§19). |
| Target HR / target RPE | No existing rule-engine output computes either. Would be a new physiological claim with no deterministic source — out of scope per the prompt's own safety boundary. | Not needed; would require inventing new rule-engine logic, which is not requested. |
| Workout completion status (stored) | Already explicitly rejected by the Phase 3 decision (derived, never stored) and reconfirmed as correct in this discovery (§12) — no reason to reverse it. | Not needed — stays derived. |

**Conclusion for §5's core question: Phase 5's schema needs are exactly zero new columns and zero new tables.** The only required code changes are to the *generation and query logic* that populates/reads the existing schema (§6 elaborates).

---

## 5. Plan Duration Recommendation

The backend already validates `plan_duration_weeks` in the range **4–24** (`app/schemas.py`, `RunnerProfileCreate.plan_duration_weeks: int = Field(..., ge=4, le=24)`) — this is not a new decision to make, it is an existing, already-enforced constraint the consumer UI simply doesn't expose.

Comparing the options neutrally:

| Option | Fit for this codebase |
|---|---|
| 4 weeks | Matches nothing in the existing `generate_weekly_progression_summary()` phase logic particularly well (deload every 4 weeks + taper needs at least ~6 weeks to show its own structure meaningfully); very short for a real training block. |
| 6 weeks | Workable, but still barely exercises the deload-every-4th-week logic more than once. |
| **8 weeks** | **Already the consumer default today** (hardcoded), already the value used in every Phase 2–4 test fixture and every manual verification session in this project's history, long enough to exercise deload + taper at least once, short enough to keep `training_plan_workouts` row counts trivial (§16), and matches the canonical S2 research example profile used throughout this project's own testing. |
| 12 weeks | A reasonable "serious half-marathon block" length; no existing code path currently exercises it. |
| 16 weeks | Explicitly offered as an option in the **research** `CreatePlanPage.jsx` today — but not in the consumer flow. |
| User-selected (4–24, free choice) | Technically already possible since the backend already validates this exact range; only the consumer frontend needs a form field. |

**Recommendation**: keep **8 weeks as the consumer default** (preserving all existing behavior, tests, and the established S2 example profile exactly as-is), and add a **user-selectable duration control to `PlanNewPage.jsx`** bounded to the existing backend range (4–24), mirroring the research form's own already-proven duration selector pattern rather than inventing a new one. This requires no backend change at all (the validation already exists) — only a frontend form field, classified as Must-have in §19 since "navigate Week 1, Week 2, Week 3..." is meaningless if every plan is silently forced to exactly 8 weeks with no way to reason about why.

---

## 6. Multi-Week Schedule Architecture

The concrete, deterministic change to `app/rules/generator.py`:

```
for week in progression_schedule:                       # existing, unchanged
    workouts = distribute_workouts_across_week(          # existing function, reused as-is
        profile=profile,
        paces=paces,                                     # existing, unchanged
        target_pace_str=target_pace_str,                  # existing, unchanged
        weekly_mileage=week["target_mileage_km"],          # NEW: each week's own target, not just week 1's
    )
    # -> full day-by-day detail for THIS week, same shape as week_1_plan.workouts today
```

This reuses `distribute_workouts_across_week()` completely unchanged in its internals (long-run day selection, quality-day placement, 80/20 split, single-training-day fallback, injury-note handling) — it already accepts `weekly_mileage` as a parameter; today it is simply never called with anything other than `profile.current_weekly_mileage`. The output shape for every week is identical to today's `week_1_plan.workouts` shape.

**Two open engineering choices, both resolved here rather than left open:**
1. **Does day placement stay identical across all weeks, or vary?** Recommendation: **identical day-of-week placement across the whole plan** (same long-run day, same quality day, same rest days every week) — this matches real-world training-plan conventions (a runner's schedule is typically a repeating weekly template with increasing volume, not a shuffled schedule), is simpler to reason about and test, and requires no new state beyond what `distribute_workouts_across_week()` already computes per call.
2. **Does the AI layer get extended to personalize every week?** Recommendation: **no, not in Phase 5** (§1, §7, §19) — weeks 2+ carry only the deterministic rule-based fields already present in `training_plan_workouts`'s existing schema (type/distance/pace/intensity/purpose), with no `warmup_cooldown`/`workout_execution` text. This keeps `app/ai/` at zero diff for Phase 5, per the explicit instruction to avoid unnecessary AI-pipeline risk, and defers the (real, but separate) work of extending the LLM prompt/schema/validator to a later phase if wanted.

---

## 7. Plan JSON vs Normalized Workout Rows

Evaluating the three options against this codebase's actual constraints:

- **Option A (materialize everything from a JSON that already contains it)**: not actually available — the JSON does not contain multi-week daily detail today, and won't unless the AI/rule-engine output shape is also extended to carry it. Discussed here for completeness but not recommended as the Phase 5 mechanism.
- **Option B (derive scheduled workouts dynamically from JSON on every read, no normalized rows for weeks 2+)**: would require every read path (Dashboard, Plan Detail, linking, completion) to parse `rule_based_plan_json`'s `progression_schedule` and re-run `distribute_workouts_across_week()` on the fly to reconstruct "what was scheduled" — this recomputation could silently drift from what was originally materialized for week 1 (different code paths, different determinism guarantees over time as the rule engine evolves), directly creating the **two-competing-sources-of-truth** problem the prompt explicitly warns against. It would also make `workout_logs.training_plan_workout_id` impossible to keep working exactly as it does today, since there would be no stable row `id` to link against for weeks 2+ unless one were synthesized and never persisted (fragile).
- **Option C (JSON is the generation-time record; `training_plan_workouts` is the single normalized scheduling source of truth for every week)**: **this is already the existing architecture for week 1**, verified in §2 — `training_plan_workouts` is the only table the Dashboard, Plan Detail's completion/linking logic, `workout_routes.py`'s ownership checks, and `bucket_weekly_totals`/`generate_observations` ever query for "what's scheduled." The JSON remains what it already is: an immutable record of exactly what was generated (used today for week 1's rich AI text and the explainability matrix) — never re-derived or re-queried for scheduling decisions.

**Recommendation: Option C, extended uniformly to every week — exactly the pattern already in production for week 1, not a new architecture.** `training_plan_workouts` stays the **only** source of truth for "what is scheduled," for every week; the JSON stays the **only** source of truth for "what was originally generated/shown," exactly matching its existing role. No competing source of truth is introduced because none exists today for week 1, and extending the identical pattern to weeks 2+ does not create one.

Comparison against the prompt's specific criteria, briefly, since Option C is the clear winner on every axis already established by the existing week-1 implementation:
- **Consistency**: one row per scheduled day, generated once, never recomputed — same guarantee week 1 already has.
- **Queryability**: plain indexed SQL (`ix_tpw_plan_week`), no JSON parsing in any hot path.
- **Ownership/security**: the existing `TrainingPlanWorkout → TrainingPlan → TrainingPlan.user_id` chain and `_resolve_owned_training_plan_workout()` need zero change — they already join through this exact table.
- **Planned-vs-actual linking**: `workout_logs.training_plan_workout_id` already points at stable normalized rows — unaffected by adding more of them.
- **Editing/versioning**: neither is introduced (§9) — `training_plan_workouts` remains read-only/derived-at-generation-time, exactly as today.
- **Future AI adaptation**: a future adaptive phase reads the same normalized rows as read-only context (§10) — no new integration surface.
- **Performance/migration complexity**: additive-only, bounded row counts (§16), no new table.
- **Testability**: the exact same test patterns already used for week 1 (`test_plan_lifecycle.py`) extend directly to "week 1 AND week 2 AND ... week N."

---

## 8. Existing Plan Compatibility

Phase 5 must not disturb any plan that already exists in the real database with only week-1 rows. Evaluating the prompt's candidate approaches:

- **Old plans remain week-1-only** (no retroactive materialization): **recommended.** A plan's `training_plan_workouts` rows are generated once, at `generate_plan()` time, using that request's `progression_schedule`; there is no scheduled job or lazy trigger that ever revisits an already-generated plan. This is already true today (regenerating logic never touches an old plan's rows) and Phase 5 does not need to add any migration or backfill step to preserve it — it is the natural, zero-effort consequence of materialization happening only inside `generate_plan()`.
- **Only newly created consumer plans become multi-week**: this **is** the natural consequence of the recommendation above, not a separate mechanism to build — no version flag, no feature flag, no conditional logic is needed. A plan generated before the Phase 5 code change simply has 7 rows (week 1 only); a plan generated after has `total_weeks * 7` rows. Both shapes coexist correctly under the exact same read paths, because those read paths already only ever ask "what rows exist for this plan/week," never "how many weeks should exist."
- **Explicit plan migration** (a script that materializes weeks 2+ for existing plans): **not recommended.** This would require re-running `distribute_workouts_across_week()` for a plan's *original* profile at a date long after generation, and would retroactively create schedule rows for calendar dates that have already passed — precisely the "fabricate historical Week 2+ workouts for old plans" the prompt explicitly warns against. No user consented to or saw this schedule at the time; presenting it now as if it always existed would be dishonest about what actually happened.
- **Lazy materialization for future weeks** (generate week N's rows only when the user first navigates to week N): considered and **rejected** for Must-have — it reintroduces exactly the "recompute on read" risk Option B (§7) already rejected, for no benefit once row counts are confirmed trivial (§16). Simpler to materialize everything at generation time.

**Existing linked workout logs, active plans, archived plans, anonymous research plans** — verified against the actual code, all are unaffected:
- Linked `workout_logs` continue to resolve through the same `training_plan_workout_id` FK regardless of whether the plan is old (week-1-only) or new (multi-week) — the join doesn't care how many other rows exist for the plan.
- An old **active** plan simply continues to show only its 7 existing rows; `current_week` may compute to a value >1 for it (e.g., a plan generated 3 weeks ago), in which case (post-Phase-5) the dashboard's "does data exist for `current_week`" check correctly finds nothing and falls back to the existing "not available" messaging — exactly the same honest behavior Phase 3 already built for "week 2+ of an old plan," just now also correctly covering "week 2+ of an old plan under the Phase 5 code," which is the same case.
- An old **archived** plan's historical links remain readable exactly as the Phase 3 rule already guarantees (§9) — nothing about materialization state affects that.
- **Anonymous research plans** never call `materialize_week_one()`/its Phase 5 successor at all (`if current_user:` gate in `generate_plan()`) — zero change, zero rows, exactly as today.

---

## 9. Plan Lifecycle

**Correcting a prompt assumption against the actual code**: there is no existing `draft` → `active` → `completed` → `archived` four-state lifecycle anywhere in this codebase. `TrainingPlan.status` is a free-text column; the only two values any code path ever writes are `'active'` and `'archived'`. There is no "create a plan in draft, then activate it" flow — `generate_plan()` sets `status='active'` immediately and unconditionally for every authenticated request. There is no `'completed'` value, no completion trigger, and no manual "archive this plan" action independent of generating a new one — the **only** way an active plan ever becomes archived today is `archive_previous_active_plans()`, called as a side effect of generating a *different* new plan.

**Phase 5 lifecycle design, built on the actual current model rather than the assumed one:**

| Action | Current behavior | Phase 5 recommendation |
|---|---|---|
| Creating a plan | Sets `status='active'`, `start_date=today`, materializes week 1 | Unchanged, except materialization now covers every week |
| Activating / starting a plan | Does not exist as a separate step — creation *is* activation | Keep as-is; no "draft" step is introduced (no Must-have use case requires one) |
| Completing a plan | Does not exist; a plan whose weeks have all elapsed simply keeps showing its last clamped week forever | **Recommended as derived, not stored**: compute `is_finished = today > start_date + total_weeks*7 days` wherever `current_week` is already computed, and surface it in the UI (§11) as a simple banner — no new `status` value, no migration, consistent with "prefer derived state" (Phase 3's own established principle) |
| Archiving a plan | Only as a side effect of generating a new plan | Keep as the only mechanism for Must-have (§19) — an explicit standalone "archive without replacing" action is a Nice-to-have with no clear use case yet (why would a user want zero active plan?) |
| Creating another plan | Archives the previous active plan, starts a new one | Unchanged |
| Changing "the" active plan | Not a distinct concept from "creating another plan" | Unchanged — there is no UI or API path to reactivate an archived plan, and none is proposed |
| Future scheduled workouts when a plan is archived | Their rows are untouched (never deleted); they simply stop being "the" active plan's schedule | Unchanged — multi-week materialization doesn't change this, since archiving never touches `training_plan_workouts` rows today and shouldn't start to |
| Historical actual-workout links after archiving | Remain fully readable (Phase 3 decision, `test_existing_historical_link_to_now_archived_plan_remains_readable`) | **Preserved exactly, no change.** New links to an archived plan's schedule continue to be rejected (`_reject_if_archived`) — this Phase 3 rule is untouched by materializing more weeks, since the guard operates on `TrainingPlan.status`, not on which week a `TrainingPlanWorkout` belongs to. |

No contradictory behavior is introduced: the archived-plan-linking rule from Phase 3 applies identically to a week-1 row or a week-6 row of an archived plan — the guard checks the *plan's* status, not the *row's* week number.

---

## 10. Scheduling Semantics

- **`scheduled_date` derivation, generalized**: `scheduled_date_for(plan_start_date, day_of_week)` becomes `scheduled_date_for(plan_start_date, week_number, day_of_week)`, adding exactly one term: `plan_start_date + timedelta(weeks=week_number - 1) + offset`, where `offset` is the same `(target_idx - plan_start_date.weekday()) % 7` already computed today. Week 1's behavior is byte-identical to today (the added term is zero when `week_number == 1`).
- **Rest days**: already represented today (`workout_type` containing "Rest", `distance_meters=0`) and already excluded from completion-status tracking (`is_rest_day()`) — this extends to every week with no change, since `is_rest_day()` only inspects the `workout_type` string, never the week number.
- **Does week 1 start exactly on `start_date`?** Yes, unchanged — `start_date` is always `date.today()` at generation time, and week 1's 7 rows always span `[start_date, start_date+6]`.
- **Must `start_date` be a specific weekday?** No — confirmed by the existing `scheduled_date_for` formula, which already correctly handles `start_date` falling on any weekday (proven by the Phase 3 boundary tests for Monday/mid-week/Sunday starts). This property is preserved unchanged for every subsequent week.
- **Can users choose a preferred start weekday?** Not proposed for Phase 5 — no existing field captures this, no Must-have use case requires it (a plan already starts "today," which is what a user expects when they click "Generate Plan"), and inventing one would be exactly the kind of speculative field the prompt warns against adding without a concrete use case.
- **How are races scheduled?** Unchanged — the existing generator already places a `"Race Week & Taper"` phase on the final week via `generate_weekly_progression_summary()`; once weeks 2+ get real day-by-day detail, the final week's long-run/quality day placement follows the same `distribute_workouts_across_week()` logic as every other week (the taper reduces the *mileage target* fed into that function, not the day-placement algorithm itself). No new "race day" concept or field is introduced.
- **Past/future workout classification**: unchanged — already exactly `derive_completion_status(scheduled_for, today, has_active_log)`'s existing three-way logic (`scheduled`/`completed`/`missed`), which is already week-number-agnostic.
- **Persisted vs. derived**: `scheduled_date` stays derived (never a stored column), consistent with the existing Phase 3 decision and this discovery's own §4 conclusion that no new persisted field is justified.

No new timezone complexity is introduced anywhere — every calculation remains plain-`date` arithmetic on the server's local date, exactly as every prior phase has maintained.

---

## 11. API Design

**No new endpoint is required.** Re-stated from §2/§7: `GET /api/plans/{plan_id}/workouts` already returns every `training_plan_workouts` row for a plan with no week filter, ordered by `(week_number, id)` — this already serves "view Week 1, Week 2, Week 3..." with zero backend change once multiple weeks' rows exist.

| Existing endpoint | Change needed for Phase 5? |
|---|---|
| `POST /api/plans/generate` | Internal only: call the new full-plan materialization function instead of `materialize_week_one()`. No request/response shape change. |
| `GET /api/plans/{plan_id}` | None. |
| `GET /api/plans/{plan_id}/workouts` | None — already multi-week-capable (§2, §7). |
| `GET /api/plans/mine` | None. |
| `GET /api/dashboard/summary` | **Yes, but only removing an artificial restriction**: replace the hardcoded `TrainingPlanWorkout.week_number == 1` query and `week1_detail_available = (current_week == 1)` gate with the actual `current_week` value, computed exactly as today. Response field names are **unchanged** (`week1_detail_available`, `week1_completed_count`, `week1_total_loggable_count` keep their existing names for backward compatibility with the already-shipped frontend, even though they now mean "current week" rather than literally "week 1" — see Open Questions, §20, for whether renaming these fields is worth a breaking change). |
| `GET /api/dashboard/progress` | None — already operates purely on `workout_logs`, entirely independent of plan week structure. |
| `POST/GET/PATCH/DELETE /api/workouts*` | None — linking/unlinking/ownership already week-agnostic. |

**Optional query-parameter enhancement (Nice-to-have, not Must-have)**: `GET /api/plans/{plan_id}/workouts?week=N` to fetch a single week's rows, useful only if a plan's total row count ever became large enough to matter (§16 shows it never does within the existing 4–24 week bound) or if a future frontend wanted to lazy-load weeks. Not recommended for Must-have — avoid the redundant endpoint surface the prompt explicitly warns against when the existing unfiltered response is already small.

No proposed change accepts a client-supplied `user_id`, ownership identifier, or arbitrary week number as an authority — `week` (if ever added) would only ever filter an already-ownership-scoped query, never widen it.

---

## 12. Frontend / UX Design

- **Dashboard**: unchanged in structure — "Today's Workout" already generalizes correctly once the `dashboard_routes.py` restriction (§11) is lifted, since `TodayWorkoutCard` already renders from the lean `TrainingPlanWorkoutResponse` shape with no assumption about which week it came from. The existing "Up next" preview and week-1 completion count (renamed conceptually to "current week," §11) both already use logic that generalizes without any component rewrite.
- **Plan Detail**: add a **week selector** (a simple row of tabs or a dropdown, "Week 1 / Week 2 / ... / Week N") above the existing workout-card grid. For the **currently selected week**, fetch is already covered by the existing `fetchPlanWorkouts(id)` call (no new request per week needed — the whole plan's schedule comes back in one call, per §11's row-count analysis in §16); the frontend simply filters the already-fetched array by `week_number` client-side. Week 1 keeps its existing rich rendering (JSON-backed `WorkoutCard` with AI text, merged with completion data exactly as today); weeks 2+ render the same `WorkoutCard` component fed the lean `TrainingPlanWorkoutResponse` fields directly (day/type/distance/pace/intensity/purpose — no warm-up/execution text), exactly matching the pattern `DashboardPage.jsx`'s `TodayWorkoutCard` already uses. Completion badges, "Log this workout"/"View logged workout" CTAs, and planned-vs-actual blocks are unchanged in logic — they already operate per-row, not per-week.
- **Workout Detail**: no change — planned/actual/link/unlink logic is already fully week-agnostic (Phase 3).
- **History**: the prompt asks whether plan context should appear in workout history. Recommendation: **keep the existing "Planned: X" tag exactly as Phase 3 built it** (it already shows which scheduled workout a log fulfilled, regardless of week) — do **not** add a week number or plan-name column to History; that would add a second navigational concept to a page explicitly kept simple in Phase 3, with no clear user need identified here.
- **Create Plan**: add the duration selector recommended in §5, defaulting to 8, bounded to the existing backend-validated 4–24 range, mirroring the research form's own existing UI pattern rather than inventing a new one.
- **No new charts, no new analytics widgets** are introduced anywhere in this section, per the explicit instruction to keep the UX simple.

---

## 13. Security

Every ownership mechanism this section asks about is already implemented and already week-number-agnostic — extending materialization to more weeks changes **zero** security-relevant code path:

- **Cross-user plan access**: `GET /api/plans/{id}` and `GET /api/plans/{id}/workouts` already return a generic `404` for a non-owned plan, regardless of how many weeks it has.
- **Cross-user scheduled-workout access**: `_resolve_owned_training_plan_workout()` already joins `TrainingPlanWorkout → TrainingPlan → TrainingPlan.user_id`, unaffected by week number.
- **Archived-plan access**: unchanged (§9) — the guard checks plan status, never week.
- **Linking actual workouts to scheduled workouts**: unchanged — the same ownership chain and the same "new link into archived plan rejected, historical link preserved" rule (Phase 3) apply identically to any week's row.
- **Plan IDs / workout IDs / query parameters**: no new client input is introduced that could express an identity; a future optional `?week=N` (§11) would only ever be a non-authoritative filter on an already-scoped query.
- **Anonymous research plans**: `materialize_week_one()`'s Phase 5 successor remains gated behind `if current_user:` inside `generate_plan()` — anonymous plans continue to receive **zero** `training_plan_workouts` rows, for any week, exactly as today.

Cross-user access continues to return `404` (never `403`, never a distinguishable error) everywhere this convention is already established — nothing in this discovery proposes changing that.

---

## 14. Research Isolation

Nothing in this discovery proposes touching `app/rules/vdot.py`'s formulas, the evaluation system, or the research frontend. The one file that **is** proposed to change, `app/rules/generator.py`, is shared between the research and consumer flows — the change (looping `distribute_workouts_across_week()` over every `progression_schedule` entry to produce a `weeks` list, alongside the existing `week_1_plan` key) is **additive to the returned dictionary's shape**, not a change to any existing key's value. `week_1_plan` and `progression_schedule` remain byte-identical in content and meaning; research code (`app/routes/evaluation_routes.py`, `EvaluationStatsPage.jsx`, `PlanResultPage.jsx`, `PlanDetailPage.jsx`) reads only `week_1_plan`/`progression_schedule`/`explainability`/`paces` today and would continue to do so unmodified, simply never reading the new key.

**The multi-week materialization side effect itself is explicitly consumer-only**, gated by the exact same `if current_user:` check already guarding `archive_previous_active_plans`/`materialize_week_one` today — an anonymous research plan generation call never reaches this branch, so it never gains any new rows regardless of how many weeks the underlying rule-engine output now describes internally.

Consumer multi-week scheduling is **not** forced into the research prototype: the research UI (`CreatePlanPage.jsx`/`PlanResultPage.jsx`) never calls `GET /api/plans/{id}/workouts` at all today (it renders directly from the plan JSON it already received from `POST /api/plans/generate`) and has no reason to start.

`/research/*` routing, anonymous plan generation, evaluation submission, and evaluation statistics are all confirmed unaffected by every change proposed in this document.

---

## 15. Future AI Adaptation Boundary

Phase 5, as scoped here, does not call the LLM any differently than today (§6 — weeks 2+ are deterministic-only). The future boundary, restated precisely for when adaptive personalization is eventually considered:

```
Historical Workout Data (workout_logs, training_plan_workouts -- Phases 2/3/5, unchanged)
        ↓
Deterministic Aggregation (Phase 4's bucket_weekly_totals/generate_observations,
   and/or a future multi-week completion-rate aggregation -- still no LLM)
        ↓
   [FUTURE PHASE ONLY] Rules / Safety Context
   (the same unmodified rule engine: VDOT, 80/20, ≤10%/week, long-run cap)
        ↓
   [FUTURE PHASE ONLY] LLM Personalization -- text only, same numeric-lockdown
   constraint already enforced today by app/ai/validator.py
        ↓
   [FUTURE PHASE ONLY] Server Validation -- same pattern, extended to cover
   every week's numeric fields, not just week 1's
        ↓
   [FUTURE PHASE ONLY] User Confirmation -- shown, never silently applied
        ↓
   [FUTURE PHASE ONLY] New Plan / New Plan Version
```

**Explicit answer to the prompt's question**: if adaptive plans are ever built, they must create **a new `TrainingPlan` row** (a new plan, using the exact same `archive_previous_active_plans()` lifecycle already in place), never mutate an existing plan's `training_plan_workouts` rows in place. This preserves the same guarantee Phase 3 already established for manual regeneration — a new plan never retroactively changes what an old plan's historical links point to — and requires no new "plan version" concept, since "generate a new plan" already **is** effectively a new version under the existing archive-on-replace lifecycle (§9).

The LLM must never (restated as an absolute, unchanged since Phase 3's own design document): edit `workout_logs`/`training_plan_workouts` rows directly, alter past workout history, silently change an active plan's schedule, bypass the rule engine's numeric constraints, change `TrainingPlan.status`, or invent a training load the deterministic engine did not compute. Nothing in this discovery's Must-have or Nice-to-have scope does any of these.

---

## 16. Performance / Scalability

Row-count estimate for `training_plan_workouts`, per plan, at 7 rows/week (including rest days, exactly as today's week 1 always produces 7 rows regardless of `training_days_per_week`):

| Duration | Rows per plan |
|---|---|
| 4 weeks | 28 |
| 8 weeks (recommended default) | 56 |
| 12 weeks | 84 |
| 16 weeks | 112 |
| 24 weeks (the existing hard maximum) | 168 |

These are trivial at any realistic user count for a single-instance SQLite deployment (the existing, explicitly-accepted MVP database choice) — even a user with 20 lifetime plans at the maximum 24-week duration produces 3,360 rows in one table, well within what a single indexed query (`ix_tpw_plan_week`) resolves in microseconds. `GET /api/plans/{id}/workouts`'s response body for a full 24-week plan is at most 168 lean JSON objects — a few hundred KB uncompressed at worst, not a pagination concern.

**Recommendation: materialize every week eagerly at generation time (§6/§8), exactly as week 1 already is, with no caching, rollup, background job, or new infrastructure.** This mirrors Phase 4's own explicit "compute on read, don't prematurely optimize" philosophy, and the numbers above show there is no real workload to optimize for yet. Dashboard load performance is unaffected (it already queries at most one plan's current week, exactly as today); Plan Detail load performance for even a full 24-week plan is a single indexed query returning under 200 small rows.

---

## 17. Testing Strategy

**Backend unit tests** (extending the existing `test_plan_lifecycle.py`/`test_workout_linking.py` pattern, likely a new `test_multiweek_schedule.py`):
- Rule engine: `distribute_workouts_across_week()` called with a non-week-1 mileage value from `progression_schedule` produces the same *shape* of output (7 items, correct day placement) as week 1's own call, for several `total_weeks` values.
- Materialization: a plan generated with `plan_duration_weeks=N` produces exactly `N*7` `training_plan_workouts` rows, correct `week_number` on each, still exactly 7 unique `day_of_week` values per week.
- `scheduled_date_for(start_date, week_number, day_of_week)`: correct for week 1 (regression, byte-identical to today), week 2, and a late week, across start dates on Monday/mid-week/Sunday (extending Phase 3's existing boundary-test matrix with a week-number dimension).
- Existing week-1-only plans (simulated by not running the Phase 5 materialization change, or by asserting on an old fixture) continue to behave exactly as `test_plan_lifecycle.py` already proves.
- Archived-plan behavior (§9): a new link into an archived plan's week-6 row is rejected exactly like its week-1 row already is (extends `test_workout_linking.py`'s existing archived-plan tests with a non-week-1 case).
- Active-plan lifecycle: generating a second plan still archives exactly one previous plan regardless of how many weeks either has.

**API tests**: authentication and ownership on `GET /api/plans/{id}/workouts` re-verified with a multi-week fixture (existing tests already prove the pattern; extend with `week_number > 1` rows present); invalid `week_number`/date inputs (defensive — no client input currently expresses a week number at all, so this is mostly "confirm no such input is ever trusted," per §13); plan-duration validation already covered by existing `RunnerProfileCreate` tests, re-run with the new frontend-exposed range.

**Integration test** (the exact scenario requested): `Create Plan (duration > 1 week) → materialize full schedule → GET /plans/{id}/workouts shows all weeks → dashboard shows correct current week → log a workout linked to a week-3 scheduled workout → GET /plans/{id}/workouts shows that row as completed with planned-vs-actual → GET /dashboard/progress reflects the logged workout` — a single end-to-end test mirroring the fixture style already used in `test_workout_linking.py::test_progress_hand_computed_fixture_end_to_end`-equivalent tests.

**Regression target**: all 178 existing tests (as of `7c34963`) must remain green, unmodified. **0 regressions**, exactly as the prompt requires — nothing in this design proposes changing any existing function's signature in a way that breaks an existing caller (the one signature change, `scheduled_date_for`, gains a new required parameter, so every existing call site — `build_enriched_tpw_response`, the Phase 3 test suite's direct calls — must be updated at the same time; this is a mechanical, fully-covered-by-tests change, not a source of regression risk if done alongside the test-suite update).

---

## 18. Migration Strategy

**No schema change, therefore no migration is proposed for Phase 5.** `alembic/versions/` should remain at `0003_add_workout_logging.py` through this phase's implementation, exactly as Phases 3 and 4 also required zero migrations.

If a future decision reverses §4's conclusion and a schema change is later found necessary (none is anticipated), the same discipline already established in this project applies: rehearse on a database copy first, verify research-table row counts and content byte-for-byte before and after, apply only after explicit approval, and never fabricate historical data for existing rows (§8's core constraint).

---

## 19. Must-Have / Nice-to-Have / Out-of-Scope

**Must-have**
1. Extend `app/rules/generator.py` to produce full daily detail for every week (§6).
2. Generalize materialization (`materialize_week_one` → a full-plan materializer) and `scheduled_date_for` to accept a week number (§6/§10).
3. Remove the two `week_number == 1`/`current_week == 1` gates in `dashboard_routes.py`, using the already-correct `current_week` value instead (§11).
4. Add a duration selector to `PlanNewPage.jsx`, defaulting to 8, bounded 4–24 (§5).
5. Add week navigation to `PlanDetailConsumerPage.jsx`, reusing the already-fetched, already-multi-week-capable `GET /api/plans/{id}/workouts` response (§11/§12).
6. Derived "this plan has finished" indicator (§9), surfaced simply on Dashboard/Plan Detail.

**Nice-to-have**
- Extending the AI personalization layer (prompt/schema/validator) to produce rich per-week text for weeks 2+, instead of lean rule-based fields only.
- `?week=N` query-parameter filtering on `GET /api/plans/{id}/workouts` (not needed at current row-count scale, §16).
- An explicit standalone "archive this plan" action independent of generating a new one.
- A user-persisted default plan duration on `UserProfile` (would require one new nullable column — explicitly not proposed now, since the frontend can simply default the form field to 8 without persisting a preference).
- Week-level adherence/completion-percentage display across a full multi-week plan (extending Phase 3's week-1-only count) — **out of scope unless separately justified**, per the prompt's own explicit instruction; nothing in this discovery finds a compelling reason to add it now beyond what Phase 4's logging-consistency metric already provides.

**Out-of-scope** (restated as commitments, matching every prior phase's own discipline): autonomous adaptive training, automatic plan mutation, fitness/readiness scores, race prediction, injury prediction, overtraining diagnosis, social/leaderboard features, complex wearable integrations, payments/subscriptions, push notifications, advanced analytics beyond what Phase 4 already built.

---

## 20. Risks and Open Questions

**Risks**
- **Day-of-week placement staying fixed across all weeks (§6)** could feel repetitive to a user compared to a coach who varies the weekly structure — accepted as a reasonable MVP simplification, not a safety or correctness risk.
- **Lean (non-AI-text) rendering for weeks 2+ (§6/§12)** creates a visible quality gap between week 1's rich cards and later weeks' plain cards within the same plan — a real UX inconsistency worth the user's explicit sign-off, weighed against the alternative cost/complexity of extending the AI pipeline now.
- **`week1_detail_available`/`week1_completed_count` field names becoming semantically stale** once they mean "current week" rather than literally "week 1" (§11) — a readability/maintainability risk, not a functional one, since the values themselves remain correct.

**Open questions requiring your decision before implementation** (kept deliberately short, per the instruction to resolve what can reasonably be resolved rather than leave things open):
1. Should the Phase 4-era field names `week1_detail_available`/`week1_completed_count`/`week1_total_loggable_count` be renamed to something week-neutral (e.g. `current_week_detail_available`) as part of Phase 5, accepting a breaking response-shape rename, or kept as-is for backward compatibility despite the now-inaccurate name? Both are reasonable; this is a naming/versioning judgment call, not an architectural one.
2. Should Phase 5's Must-have include the AI-text extension for weeks 2+ (a real, separate, bounded piece of work touching `app/ai/`), or is the lean rendering explicitly acceptable for this phase, with rich text deferred? §6/§19 recommend deferring it, but this trades consumer polish for AI-pipeline risk and is worth your explicit confirmation given how central "AI-personalized" is to this product's stated value proposition.

Everything else raised by the original prompt has been resolved with an explicit decision above rather than left open.

---

## 21. Proposed Implementation Sequence

1. `app/rules/generator.py`: extend to produce a `weeks` list (or equivalent) covering every `progression_schedule` entry via `distribute_workouts_across_week()`, alongside the unchanged `week_1_plan`/`progression_schedule` keys.
2. `app/workouts/service.py`: generalize `scheduled_date_for()` to take a week number; generalize `materialize_week_one()` into a full-plan materializer; update `build_enriched_tpw_response()`'s call site accordingly (its own signature is unaffected, since it already receives a `TrainingPlanWorkout` row, not a week number).
3. `app/routes/plan_routes.py`: call the new full-plan materializer from `generate_plan()`.
4. `app/routes/dashboard_routes.py`: remove the two hardcoded week-1 gates (§11).
5. Backend tests (§17) — written alongside each step above, not after; confirm all 178 pre-existing tests still pass unmodified at every step.
6. Frontend: duration selector on `PlanNewPage.jsx`; week navigation on `PlanDetailConsumerPage.jsx`; the derived "plan finished" indicator on Dashboard/Plan Detail.
7. Manual three-viewport verification, mirroring every prior phase's own ritual.
8. Manual research-flow regression check (generate → evaluate → statistics), plus a `git diff --stat` confirmation that `app/ai/`, `app/routes/evaluation_routes.py`, and every research frontend file are untouched.

---

## 22. Acceptance Criteria

1. A newly generated plan with `plan_duration_weeks = N` produces exactly `N * 7` `training_plan_workouts` rows, with every week having exactly 7 unique `day_of_week` values.
2. `GET /api/plans/{id}/workouts` returns rows for every generated week, correctly ordered, with no week filter needed to retrieve them all.
3. `scheduled_date_for` produces byte-identical week-1 results to the pre-Phase-5 implementation, and correct results for weeks 2 through N, verified for start dates on Monday, mid-week, and Sunday.
4. The Dashboard shows the correct current week's scheduled workout (not always week 1) for a plan more than one week into its schedule.
5. A workout can be linked to a scheduled workout in any week, with ownership, archived-plan-rejection, and historical-link-preservation rules behaving identically regardless of week number (proven by extending the existing Phase 3 test fixtures to a non-week-1 case).
6. An existing (pre-Phase-5) plan with only 7 rows continues to function exactly as it does today — no error, no fabricated data for its missing weeks 2+.
7. Anonymous research plan generation produces zero `training_plan_workouts` rows, for any `plan_duration_weeks` value, exactly as today.
8. `git diff --stat` against `app/rules/vdot.py`, `app/ai/`, `app/routes/evaluation_routes.py`, and every research frontend file shows no unexpected change beyond the additive `generator.py` key described in §14.
9. All 178 pre-existing tests pass unmodified, plus every new Phase 5 test.
10. The research flow (generate → evaluate → statistics) is manually re-verified end-to-end with zero behavioral change.
11. No new database table or column exists; `alembic/versions/` is unchanged from `0003_add_workout_logging.py`.
12. The Plan Detail page's week navigation and Plan Creation's duration selector both render without horizontal overflow at 375/768/1440px.

---

## 23. Final Recommendation

Implement the **Must-have scope only** (§19): extend the deterministic rule engine to generate every week's schedule, materialize all weeks into the existing `training_plan_workouts` table with no schema change, remove the two artificial week-1 gates in the dashboard route, and add the two small, clearly-scoped frontend additions (duration selector, week navigation). This is a genuinely small, low-risk change precisely because Phases 3 and 4 already built every piece of scheduling, linking, completion, and progress logic in a week-agnostic way without realizing it would matter this soon — Phase 5's job is almost entirely to *feed* that existing machinery real data for more weeks, not to rebuild it. Defer the AI-text extension for weeks 2+ and any adherence-percentage display explicitly, pending your answer to the two open questions in §20.

---

**Design Status: DISCOVERY COMPLETE — NO CODE WRITTEN, AWAITING DIRECTION ON OPEN QUESTIONS BEFORE ANY DESIGN OR IMPLEMENTATION PROCEEDS.**

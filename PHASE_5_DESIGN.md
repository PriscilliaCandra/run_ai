# Phase 5 Design — Multi-Week Training Plans

**Date:** 2026-09-29
**Source of truth:** actual repository state at commit `7c34963`, and the findings in `PHASE_5_DISCOVERY.md`.
**Status:** DESIGN ONLY. No application code, test, migration, database, or dependency was changed to produce this document.

---

## 1. Objective (context, not a required section — orientation only)

Evolve `training_plan_workouts` from a week-1-only snapshot into the complete, normalized scheduling record for a consumer's entire multi-week plan, using the deterministic rule engine exclusively (no AI change), while leaving every existing Phase 0–4 behavior — research generation, AI personalization, ownership, linking, completion, progress — untouched in its logic, only extended in the range of weeks it now has real data to operate over.

---

## 2. Plan Duration

**Decision: Option C — a default duration with optional user selection**, not a fixed 8 weeks and not an unconstrained free-form input.

- **Range**: `4–24`, unchanged — this is already the enforced backend validation (`RunnerProfileCreate.plan_duration_weeks: int = Field(..., ge=4, le=24)`). Phase 5 does not change this range; it only finally exposes it in the consumer UI.
- **Default**: `8`, preserving the exact value every existing test fixture, manual verification session, and the current hardcoded consumer behavior already uses — changing the default would be an unjustified behavior change with no functional benefit.
- **UI control**: a `<select>` on `PlanNewPage.jsx` offering a small curated set of common values (`4, 6, 8, 12, 16, 20, 24`) rather than a free-text number input — mirroring the existing research `CreatePlanPage.jsx`'s own duration-selector pattern (already proven, already styled, no new component invented) rather than a raw numeric field that could invite off-by-one or out-of-range client mistakes. Backend validation (`ge=4, le=24`) remains the authoritative check regardless of what the dropdown offers.
- **Validation**: unchanged — `RunnerProfileCreate`'s existing `Field(..., ge=4, le=24)` already rejects anything outside range with a `422`; no new validation code is written.
- **What happens when duration changes** (in the create-plan form, before submission): nothing beyond updating the form's local state — `plan_duration_weeks` is submitted once, at generation time, exactly like every other form field already on that page (age, target race, etc.). There is no "change an existing plan's duration" feature — a plan's duration is fixed at generation time, exactly as `plan_duration_weeks` already is today for research plans.
- **How the generated schedule uses it**: unchanged — `generate_weekly_progression_summary(base_mileage, total_weeks, target_race_distance)` already accepts and correctly uses it to produce `total_weeks` entries in `progression_schedule`, including deload-every-4th-week and taper-on-the-last-1–2-weeks logic that already scales correctly for any value in the validated range.
- **How the frontend determines total weeks**: **derived, never a separate stored value** — `len(rule_based_plan.progression_schedule)`, exactly the convention `dashboard_routes.py` already uses server-side. No new field is added to carry this number redundantly.
- **Does it need to be persisted separately on `training_plans`?** **No.** Persisting it would duplicate data already fully recoverable from `rule_based_plan_json`, which is exactly the anti-pattern the discovery and this prompt both explicitly warn against. Zero new column.

---

## 3. Multi-Week Deterministic Generation

**The mechanism, precisely, extending `app/rules/generator.py`:**

```python
weeks = []
for week_info in progression_schedule:                    # existing, unchanged, already correct for any total_weeks
    week_workouts = distribute_workouts_across_week(       # existing function, called unchanged
        profile=profile,
        paces=paces,                                        # unchanged -- pace ZONES are physiological
        target_pace_str=target_pace_str,                    # constants, not weekly-varying
        weekly_mileage=week_info["target_mileage_km"],       # <- the one input that actually varies per week
    )
    weeks.append({
        "week_number": week_info["week_number"],
        "phase": week_info["phase"],
        "focus_note": week_info["focus_note"],
        "weekly_mileage_km": round(sum(w.distance_km for w in week_workouts), 1),
        "workouts": [w.model_dump() for w in week_workouts],
    })
```

Answering each of the prompt's specific points, all resolved by re-reading `distribute_workouts_across_week()`'s actual current implementation rather than assumed:

- **Input weekly mileage**: `week_info["target_mileage_km"]` — already computed correctly for every week by the existing, unmodified `generate_weekly_progression_summary()`.
- **Week number / phase**: carried straight through from the existing `progression_schedule` entries — no new computation.
- **Do deload/taper weeks change workout distribution?** **No special-casing is needed, and none is added.** `distribute_workouts_across_week()` derives the long-run distance, quality-workout distance, and easy-run distances purely as percentages of whatever `weekly_mileage` it is given (30% long run capped per race distance, 20% quality floored at 3.5 km, remainder split across easy days). A deload week's already-reduced `target_mileage_km` flows through the exact same percentage math and *automatically* produces a lighter week — the function does not need to know it is being called for a deload or taper week.
- **How pace targets are calculated**: **unchanged, and deliberately constant across every week** — `paces` (the VDOT-derived zone dictionary) and `target_pace_str` are computed once, before the per-week loop, from the runner's 5K PB and target race — these are physiological pace *zones*, not volume, and do not change week to week. Only distances change; the pace a runner should run "easy" or "interval" pace at stays the same throughout the block, exactly matching real coaching practice and exactly matching how the existing week-1-only code already treats pace as a plan-wide constant.
- **How long-run distance is calculated**: the existing formula, unchanged, re-evaluated per week: `min(weekly_mileage * 0.30, race-distance-specific cap)`, floored at 4 km.
- **How quality workouts are distributed**: the existing formula, unchanged, re-evaluated per week: `max(weekly_mileage * 0.20, 3.5)`, on the existing Tuesday/Wednesday/Thursday-preferring day logic.
- **How rest days are represented**: unchanged — any day not in the profile's active-training-day set becomes a `"Rest & Recovery"` entry with `distance_km=0.0`, for every week identically.
- **How day-of-week is assigned — the most important finding of this section**: `distribute_workouts_across_week()`'s day-selection logic (`active_days_set`, `long_run_day`, `quality_day`) is a **pure function of `profile.preferred_training_days`/`profile.training_days_per_week`/`profile.target_race_distance`** — none of which vary per week. Calling the exact same function N times with the same `profile` object and only a different `weekly_mileage` **already, automatically, with zero additional code**, produces identical day-of-week placement across every week (same long-run day every week, same quality day every week, same rest days every week). This directly satisfies the prompt's explicit requirement to not simply duplicate week 1's *content* while still keeping its *day structure* consistent — the values differ (volume scales with each week's target), the day layout does not (by design, matching real training-plan conventions per the discovery's §6 recommendation).
- **How workout purpose is generated**: unchanged — the existing static, workout-type-keyed purpose strings (e.g. "Builds capillary density, mitochondrial density, and mental stamina for race distance." for a Long Run), generated fresh on every call, for every week identically — these describe *why this type of session matters*, not a week-specific narrative, so no per-week variation is expected or introduced.

**Explicit confirmation the schedule is not a duplicate**: because `weekly_mileage` genuinely differs week to week (progressive build, periodic cutback, taper), the long-run distance, quality-workout distance, and easy-run distances all genuinely differ week to week even though the *day layout* stays constant — e.g., week 1's long run might be 6.0 km and week 6's (a build week) might be 9.5 km, both on the same day of the week. This is the correct, intended behavior, not a limitation.

---

## 4. Rule-Engine Output Shape

**Decision, resolving the prompt's explicit question about structure:**

```json
{
  "vdot": 38.4,
  "target_pace_per_km": "04:36",
  "paces": { ... unchanged ... },
  "week_1_plan": { "week_number": 1, "weekly_mileage_km": 20.0, "focus": "...", "workouts": [ ...7 items... ] },
  "progression_schedule": [ { "week_number": 1, "target_mileage_km": 20.0, "phase": "...", "focus_note": "..." }, ... ],
  "weeks": [
    { "week_number": 1, "phase": "...", "focus_note": "...", "weekly_mileage_km": 20.0, "workouts": [ ...same 7 items as week_1_plan... ] },
    { "week_number": 2, "phase": "...", "focus_note": "...", "weekly_mileage_km": 21.2, "workouts": [ ...7 items, week 2's own volume... ] },
    ...
  ],
  "explainability": { ... unchanged ... }
}
```

- **`weeks` (new key)**: added. This is the **new, uniform materialization input** — every week, including week 1, is written into `training_plan_workouts` by reading from `weeks[i]["workouts"]`, never by special-casing "week 1 comes from `week_1_plan`, the rest come from `weeks`."
- **`progression_schedule` remains completely unchanged** — same shape, same values, still the input driving `weeks`' per-week mileage, still read by `dashboard_routes.py` to derive `total_weeks`, still untouched by research code's own usage of it.
- **`week_1_plan` remains completely unchanged, for backward compatibility** — it is still read verbatim by `app/ai/prompts.py`'s `build_user_prompt()`, `app/ai/llm_service.py`'s `generate_offline_ai_plan()`, `app/ai/validator.py`'s `validate_ai_plan()`, and by frontend code that reads `plan.rule_based_plan.week_1_plan` directly (`PlanDetailConsumerPage.jsx`'s existing fallback, research's `PlanResultPage.jsx`/`PlanDetailPage.jsx`). None of these are modified.

**On "avoiding unnecessary duplication"**: `weeks[0]` and `week_1_plan` do contain the same workout values — this is a deliberate, minimal, and justified duplication, not an oversight. Both are populated from the **same single call** to `distribute_workouts_across_week()` for week 1 (the loop's first iteration produces the data placed into `weeks[0]`; `week_1_plan` is constructed from that identical result in its own pre-existing shape) — so there is no risk of the two ever drifting apart, and no second code path computing week 1 twice. The alternative — deleting `week_1_plan` and having every existing consumer read `weeks[0]` instead — would require touching `app/ai/prompts.py`, `app/ai/llm_service.py`, `app/ai/validator.py`, and multiple frontend files for a purely cosmetic consolidation, directly contradicting the instruction not to modify `app/ai/` unless absolutely required. It is not required.

**Clear source-of-truth declaration** (resolving the prompt's explicit demand for one):
- **`training_plan_workouts`** — the sole source of truth for "what is scheduled," for every week, queried by every read path (Dashboard, Plan Detail, linking, completion, progress). Unchanged role from today, now populated completely.
- **`weeks` (new JSON key)** — the sole *generation-time input* to materialization. Never queried directly by any read path; write-once, read-once (at the moment `generate_plan()` calls the materializer).
- **`week_1_plan` / `ai_plan_json`** — the generation-time record used for rich, AI-personalized *display* of week 1 only, exactly as today. Never used for scheduling decisions (ownership, linking, completion), exactly as today.
- **`progression_schedule`** — the per-week mileage/phase metadata, used to derive `total_weeks` and to drive `weeks`' generation. Unchanged role.

---

## 5. Existing AI Personalization Compatibility

**Zero changes to `app/ai/`.** Verified precisely against the actual files:

- `app/ai/prompts.py`'s `build_user_prompt()` reads only `rule_plan["week_1_plan"]` — untouched, continues to receive exactly what it receives today.
- `app/ai/llm_service.py`'s `generate_offline_ai_plan()` and the Gemini/OpenAI call paths all operate on `rule_plan["week_1_plan"]` only — untouched.
- `app/ai/validator.py`'s `validate_ai_plan()` checks the AI's output against `rule_plan["week_1_plan"]` only — untouched.
- `ai_plan_json` on `training_plans` continues to store exactly one week's rich, AI-personalized content, exactly as today. No second AI pipeline is created; no AI call is ever made for weeks 2+, ever.

**Frontend handling of the two representations, precisely** — re-confirmed against the actual current `PlanDetailConsumerPage.jsx` and `WorkoutCard.jsx`:

- **Week 1**: rendering is **completely unchanged** — `plan.ai_personalized_plan.workouts` (the rich JSON, matched by `day` string) merged with the already-fetched `scheduled` array (enriched `TrainingPlanWorkoutResponse` rows) for completion badges/CTA/planned-vs-actual, exactly as Phase 3 built it.
- **Weeks 2+**: rendered **directly from the `scheduled` array** (filtered to that `week_number`) with no JSON lookup at all — `WorkoutCard` is called with the lean object shape `{ day, workout_type, distance_km, pace_target, intensity_zone, purpose }`, **exactly the same shape `DashboardPage.jsx`'s existing `TodayWorkoutCard` already constructs and passes today**. `WorkoutCard` already conditionally renders `warmup_cooldown`/`workout_execution` only `{workout.warmup_cooldown && (...)}` — confirmed by reading the component — so passing an object without those keys already renders correctly with no component change needed at all.
- **A genuinely clean finding requiring zero new code**: `ScheduledWorkoutSummary` (the type embedded in a `WorkoutLogResponse.linked_scheduled_workout`, shown on Workout Detail's "Planned: ..." box) has **never** carried AI-rich text, even for week 1, since Phase 3 — it is built purely from `TrainingPlanWorkout` row fields (`ScheduledWorkoutSummary.from_tpw()` reads only `workout_type`/`distance_meters`/`pace_target`/`intensity_zone`/`purpose`). Workout Detail therefore requires **zero changes** for Phase 5 — it was already week-richness-agnostic (§10 below).

---

## 6. Materialization Design

**Rename**: `materialize_week_one(db, training_plan_id, rule_plan)` → `materialize_training_plan_workouts(db, training_plan_id, rule_plan)` (design only — not implemented in this document).

| Aspect | Specification |
|---|---|
| **Inputs** | `db` (the active session), `training_plan_id` (the just-flushed plan's id — unchanged, still requires `db.flush()` before this call to assign the id), `rule_plan` (the full dict, now including `weeks`) |
| **Transaction boundary** | **Unchanged from today, only extended.** Called inside `generate_plan()`'s existing single transaction, between the existing `db.flush()` and the existing `db.commit()`. Every week's rows are `db.add()`-ed into the same uncommitted transaction as the plan row itself — if anything fails before `commit()`, the whole plan and its entire schedule roll back together, exactly the same atomicity guarantee week 1 already has today, simply covering more rows. |
| **Number of rows expected** | `sum(len(week["workouts"]) for week in rule_plan["weeks"])`, always exactly `total_weeks * 7` (every week, including rest days, produces exactly 7 rows, matching today's week-1 pattern regardless of `training_days_per_week`). |
| **Week/day uniqueness** | Enforced by the existing, unmodified `UniqueConstraint("training_plan_id", "week_number", "day_of_week")` — looping `weeks[0..N-1]`, each producing its own 7 distinct `day_of_week` values, naturally satisfies this with no new logic. |
| **Rest days** | **Included as rows**, exactly as week 1 already does (`distance_meters=0`, `workout_type="Rest & Recovery"`) — not skipped. This is required, not optional: `is_rest_day()`'s completion-status derivation depends on a row existing to inspect and return `None` for. |
| **Distance conversion** | Unchanged per-row conversion: `distance_meters = round(w["distance_km"] * 1000)`, applied uniformly to every week's workouts. |
| **Pace target / intensity zone / purpose** | Copied verbatim from each week's `WorkoutItem`, exactly as today's single-week logic, extended to loop over every week. |
| **Scheduled date derivation** | **Not computed or stored during materialization at all** — unchanged from today. `training_plan_workouts` gains no new column; `scheduled_date` remains purely a read-time derivation (§7). |
| **Idempotency** | **Not idempotent, by design, unchanged from today.** `generate_plan()` is the only caller, called exactly once per plan-creation request; there is no "regenerate this plan's schedule" code path today and Phase 5 does not add one. Calling the materializer twice for the same `training_plan_id` would raise an `IntegrityError` from the existing unique constraint — it does not silently overwrite anything, satisfying the prompt's explicit requirement the hard way: by making silent overwrite structurally impossible, not merely discouraged. |

---

## 7. Scheduled Dates

**Generalized formula**, extending the existing, unmodified per-week-1 logic with exactly one new term:

```python
def scheduled_date_for(plan_start_date: date, week_number: int, day_of_week: str) -> date:
    target_idx = DAYS_OF_WEEK.index(day_of_week)
    offset = (target_idx - plan_start_date.weekday()) % 7        # unchanged formula
    week_anchor = plan_start_date + timedelta(weeks=week_number - 1)   # the one new term
    return week_anchor + timedelta(days=offset)
```

For `week_number == 1`, `timedelta(weeks=0)` is a no-op — this is **byte-identical to today's implementation** for every existing week-1 call site, including every existing Phase 3 boundary test (Monday/mid-week/Sunday start dates). Since `week_anchor` is always `plan_start_date` plus a whole number of 7-day blocks, `week_anchor.weekday() == plan_start_date.weekday()` always holds — so the `offset` calculated from `plan_start_date.weekday()` is correct for every week without needing to be recalculated relative to each week's own anchor.

Answering the prompt's specific points:
- **Week 1 starts at `start_date`**: unchanged, confirmed.
- **Monday–Sunday mapping**: the existing modulo-7 formula, unchanged, extended to any week via `week_anchor`.
- **What if `start_date` is not Monday?** Already fully handled — `start_date`'s own weekday simply determines which day of week-1's 7-day window `start_date` itself is, exactly as the existing Phase 3 tests already prove for mid-week and Sunday starts; this property is preserved unchanged for every subsequent week's anchor.
- **Is `start_date` itself a training day or just the beginning of the schedule?** Purely the anchor date — whether `start_date`'s own weekday happens to be a scheduled training day or a rest day depends entirely on the (unchanged) day-of-week assignment logic (§3); there is no special meaning attached to `start_date` beyond "day 1 of the 7-day window that is week 1."
- **How is Week 2 calculated?** `week_anchor = plan_start_date + 7 days`; every subsequent week adds another 7-day block. No new concept — a direct, minimal extension.
- **How is race day represented?** **Not as a distinct flag or field.** The plan's final week (per `generate_weekly_progression_summary`'s existing taper logic) has its long-run/quality day fall on the same day-of-week as every other week, simply at reduced taper volume — there is no "this specific day is the race" marker in the data model, and none is proposed, matching the discovery's explicit conclusion that no new field should be added without a concrete Must-have use case (none exists here).
- **Are scheduled dates persisted or derived?** **Derived only**, unchanged — no new column on `training_plan_workouts`.

No timezone complexity of any kind is introduced — every computation remains plain-`date` arithmetic on the server's local date, exactly as every prior phase.

---

## 8. Existing Plans / Backward Compatibility

**Recommended principle, adopted exactly as the prompt frames it: existing plans remain unchanged; new plans receive full multi-week materialization.** This requires no migration and no special-case code, because it is the natural, zero-effort consequence of materialization happening only inside `generate_plan()`'s own request/response cycle — nothing in Phase 5 ever revisits an already-generated plan's row.

| Existing case | Behavior after Phase 5 |
|---|---|
| A plan with only week 1 materialized | Continues to have exactly 7 rows. `GET /api/plans/{id}/workouts` returns exactly those 7 rows, ordered correctly, exactly as today. |
| Existing linked `workout_logs` | Continue to resolve through the unchanged `training_plan_workout_id` FK — the join does not care whether the plan has 7 rows or 168. |
| An active plan generated before Phase 5, now several weeks old | `current_week` may compute to a value beyond 1; the (renamed, §12) "current week detail available" flag correctly evaluates to `False` for it, because no row exists for that week — the dashboard shows the existing, already-correct "not available" messaging, exactly the honest behavior Phase 3 already built for "week 2+ of an old plan," simply still applying to old plans after Phase 5 ships. |
| An archived plan | Historical behavior (§9) is entirely unaffected by how many weeks it does or does not have materialized. |
| An anonymous research plan | Never receives materialized rows at all, for any week, both before and after Phase 5 (§10). |

**Lazy materialization was evaluated and rejected**, exactly per the discovery's own conclusion: it would reintroduce a "recompute or backfill on read" risk for a benefit that does not exist once row counts are confirmed trivial (§16) — there is no genuine reason to defer materialization to a future request when doing it once, up front, atomically with plan creation, is simpler, already-proven (week 1 already works this way), and costs nothing extra at these row counts. **No historical Week 2+ workouts are ever fabricated for a plan that predates this change** — this is not a policy applied through extra code, it is simply true because no code path ever writes to an old plan's `training_plan_workouts` rows after the fact.

---

## 9. Plan Lifecycle

**Correcting the same prompt assumption already corrected in the discovery**: there is no `draft`/`completed` status anywhere in the current codebase; only `'active'`/`'archived'` are ever written. This design does not introduce either new value.

| Lifecycle question | Design decision |
|---|---|
| Plan creation | Unchanged: sets `status='active'`, `start_date=today`, now materializes every week instead of only week 1. |
| Activation / "starting" a plan | Does not exist as a separate step, unchanged — creation *is* activation; no draft state is introduced. |
| Completing a plan — automatic or user-triggered? | **Neither, in Must-have.** No new stored status is written. A **derived** "this plan's schedule has fully elapsed" indicator (`today > start_date + total_weeks * 7 days`) is computed wherever `current_week` is already computed and surfaced as a simple, non-blocking banner (§11) — consistent with the project's established "prefer derived over stored state" principle (Phase 3). |
| Can an active plan be replaced? | Yes, unchanged — generating a new plan archives the previous active one via the existing, unmodified `archive_previous_active_plans()`. |
| Future scheduled workouts of an archived plan | Remain fully visible historically — `training_plan_workouts` rows are never deleted or hidden on archive, unchanged. |
| Do actual logs remain linked forever? | Yes, unless the *log itself* is soft-deleted (Phase 2's `deleted_at`) — plan archival never touches `workout_logs` at all, unchanged. |
| Creating a second plan / old-plan history | Unchanged — the previous plan (and all its weeks' rows) simply becomes `status='archived'`, fully intact and queryable via `GET /api/plans/mine` and `GET /api/plans/{id}/workouts`. |

**Phase 3 rule preserved exactly, re-verified against Phase 5's own changes**: a **new** link into an archived plan's schedule is rejected (`_reject_if_archived`, which checks `TrainingPlan.status`, never `TrainingPlanWorkout.week_number`) regardless of which week the target row belongs to; an **existing historical** link made while the plan was active remains fully readable regardless of week, since nothing about materializing more weeks changes how `_get_owned_workout_or_404`/`build_enriched_tpw_response` resolve an existing link. No automatic archival, completion, or reactivation behavior is introduced anywhere in this design.

---

## 10. Week Navigation and Frontend UX

### Plan Detail

**Structure**: a horizontally-scrollable row of week-number tab buttons ("Week 1 | Week 2 | ... | Week N") directly above the existing workout-card grid, reusing the same visual language already established by `Badge`/`Button` components — no new UI library, no charting.

**Why tabs, not a dropdown or accordion**: for the recommended default (8 weeks) and the full supported range (4–24), a horizontal tab row scales acceptably — it stays a single, obviously-scannable row at desktop widths and becomes a natural horizontally-scrollable strip at 375px (the same overflow-scroll pattern already implicitly available via Tailwind's `overflow-x-auto`, no new interaction pattern to learn). A dropdown would hide the "how many weeks total" context a user likely wants at a glance; an accordion (all weeks stacked, individually expandable) risks exactly the "one giant page" problem the prompt explicitly warns against once a plan reaches 16–24 weeks.

**Only the selected week's 7 day-cards are rendered in the DOM at any time** — never all `N * 7` at once, directly satisfying "avoid rendering every workout from every week in one giant page."

**Which week opens by default**: the **current week**, computed client-side, not always week 1. This requires the plan-detail page to know the plan's `start_date` and `total_weeks`, which it does not receive today (`PlanGenerationResponse` has no `start_date` field). **Design decision: add `start_date: Optional[date] = None` to `PlanGenerationResponse`**, following the **exact precedent already established in Phase 3** for adding `status` to the same response (an additive, optional field, `None` for every anonymous research plan, backward-compatible with every existing consumer). The frontend then computes `current_week = clamp(floor((today - start_date) / 7) + 1, 1, total_weeks)` — the **identical formula** `dashboard_routes.py` already uses server-side — to pre-select the right tab on load. For a finished plan (past its last week), this naturally clamps to the last week, matching the existing dashboard clamping behavior. This avoids inventing any new endpoint (§13) and reuses an already-proven additive-field pattern rather than a new architectural mechanism.

**Per-day-card behavior is completely unchanged regardless of which week is selected** — completion badge, "Log this workout"/"View logged workout" CTA, planned-vs-actual block, and the archived-plan CTA-suppression rule (Phase 3) all already operate per-row, with no assumption about week number anywhere in their existing implementation.

**Responsive behavior**: the week-tab row uses the same `overflow-x-auto`/`flex` pattern this codebase already relies on (e.g. `WeeklyDistanceBars`'s flex-based bars); verified conceptually to work at 375/768/1440px without a new breakpoint-specific layout, and to be confirmed the same way every prior phase confirmed it — measured `scrollWidth <= innerWidth`, not eyeballed, once implemented.

### Dashboard

**No structural change.** The existing "Week X of Y" badge (`Badge variant="indigo" icon={Calendar}>Week {current_week} of {total_weeks}`) already displays plan duration and current week correctly — it was never actually broken, only fed data that happened to only exist for week 1. Once the two gates in §12 are removed, "Today's Workout," "Up next," and the (renamed) current-week completion count all correctly reflect whichever week the user is actually in, with **zero frontend code change to `DashboardPage.jsx`'s Training Plan card** beyond the field-rename follow-through (§12). The existing Progress section (Phase 4) is entirely unaffected — it operates purely on `workout_logs`, with no dependency on plan week structure at all.

### Workout Detail

**No change of any kind** — confirmed in §5, `ScheduledWorkoutSummary` was already lean/week-richness-agnostic since Phase 3.

### History

**No change** — the existing "Planned: X" tag (Phase 3) already works identically regardless of which week the linked scheduled workout belongs to; no week or plan-name column is added, consistent with the discovery's recommendation to keep History simple.

---

## 11. Completion Semantics

Preserved exactly, restated to confirm they apply correctly across every week without modification:

- **`completed`** = a non-deleted `workout_logs` row links to the scheduled row — unchanged; `build_enriched_tpw_response()`'s query already has no week-number filter of its own.
- **`scheduled`** = `scheduled_date >= today` and no linked log — unchanged; `scheduled_date` is now correctly computed for any week via §7's generalized formula.
- **`missed`** (surfaced to the user as "Not logged," never "Missed" — Phase 3's own established wording) = `scheduled_date < today` and no linked log — unchanged.
- **Rest days** = `completion_status: null` for every week, unchanged — `is_rest_day()` only inspects `workout_type`, never week number.

**No adherence score, compliance score, or streak score is introduced.** The only aggregate figure that exists is the (renamed, §12) current-week completed/total-loggable count, which is a plain count exactly as Phase 3 already built it — extending its scope from "always week 1" to "whichever week is actually current" is not a new metric, it is the same metric finally seeing the week it was always supposed to describe.

---

## 12. Dashboard Current-Week Logic

**Decision: remove the week-1 gate, replace it with a real current-week schedule lookup, and rename the response fields.** All three of the prompt's options are addressed, not left as alternatives:

1. **Remove the gate**: the `week1_detail_available = (current_week == 1)` line and the `TrainingPlanWorkout.week_number == 1` filter in `dashboard_routes.py` are both replaced — the query becomes `TrainingPlanWorkout.week_number == current_week` (the already-correctly-computed, already-clamped value), and the availability flag becomes "does at least one row exist for `current_week`" (which, after Phase 5 ships, is true for every week 1..total_weeks of a newly-generated plan, and correctly false only for an *old*, pre-Phase-5 plan whose current week is beyond its materialized week 1 — §8).
2. **Rename the fields**: `week1_detail_available` → `current_week_detail_available`, `week1_completed_count` → `current_week_completed_count`, `week1_total_loggable_count` → `current_week_total_loggable_count`.

**Why rename rather than keep the old names** (the prompt requires an explicit decision, not a punt): these fields are consumed **only** by this project's own frontend (`DashboardPage.jsx`) — there is no external API consumer to break. The files that read and write these field names (`dashboard_routes.py`, `workouts/schemas.py`'s `ActivePlanSummary`, `DashboardPage.jsx`) are already being modified by this exact phase for the gate removal itself, so the marginal cost of also renaming is a handful of mechanical find-and-replace edits in files already open for editing — not a separate migration or a breaking change for any real consumer. Leaving a field named `week1_completed_count` that, after this phase, actually reports whichever week the user is currently in would be a permanent, compounding readability trap for anyone reading this code later (including a future AI-assisted session), which this project's own established documentation discipline argues strongly against accumulating. This is a deliberate, justified decision, not an oversight either way.

---

## 13. API Design

**No new endpoint is created.** Every capability the prompt asks to evaluate is already satisfied by an existing endpoint, enriched additively:

| Capability | How it's satisfied |
|---|---|
| Retrieving all plan weeks | `GET /api/plans/{id}/workouts` — already returns every row for the plan with no week filter (confirmed in discovery, unchanged by this design). |
| Retrieving a selected week efficiently | The existing composite index `ix_tpw_plan_week (training_plan_id, week_number)` already makes any future `?week=N` filter (Nice-to-have, §19 — not built in Must-have) trivially efficient; for Must-have, the frontend filters the already-fetched full-plan array client-side (§10), which is cheap at the row counts established in §16. |
| Retrieving current week | Already served by `GET /api/dashboard/summary`'s existing `current_week`/`total_weeks` fields (unchanged); Plan Detail computes it independently client-side using the new `start_date` field (§10) via the identical formula, needing no new endpoint. |
| Dashboard current workout | Already served by `GET /api/dashboard/summary`'s `today_scheduled_workout`, once the §12 gate is removed. |

**The two additive response-field changes proposed by this design, both following the exact precedent already set by Phase 3's `status` addition to `PlanGenerationResponse`:**

| Endpoint | Field added | Type | Purpose |
|---|---|---|---|
| `POST /api/plans/generate`, `GET /api/plans/{id}` | `start_date` | `Optional[date] = None` | Lets the frontend compute "current week" client-side for Plan Detail's default tab (§10); `None` for every anonymous research plan, unchanged behavior for every existing consumer of this response that doesn't read the new field. |
| `GET /api/dashboard/summary` | *(rename only, §12 — no new field, existing fields renamed)* | — | — |

No request body of any existing or proposed endpoint changes shape. `plan_duration_weeks` is **already** an existing, validated field on `RunnerProfileCreate` — the consumer frontend simply starts sending a value other than the hardcoded `8` (§2).

---

## 14. Security

Every ownership mechanism this section asks about is unchanged by this design, because none of it was ever week-number-dependent to begin with (re-confirmed, not merely re-asserted, by reading each function again during this design pass):

- **Plans**: `GET /api/plans/{id}` / `GET /api/plans/{id}/workouts` already return a generic `404` for a non-owned plan — unaffected by how many weeks it has.
- **Training plan workouts**: `_resolve_owned_training_plan_workout()`'s join (`TrainingPlanWorkout → TrainingPlan → TrainingPlan.user_id`) is week-number-agnostic — unchanged.
- **Actual workout links**: the new-link-into-archived-plan rejection and historical-link preservation (Phase 3) both key off `TrainingPlan.status`, never `TrainingPlanWorkout.week_number` — unchanged, re-confirmed in §9.
- **Week query parameters**: none exist in Must-have (§13); if the Nice-to-have `?week=N` filter is ever added, it would only ever narrow an already-ownership-scoped query, never widen or bypass it, exactly like every other query parameter in this codebase (e.g. `weeks` on the Phase 4 progress endpoint).
- **Current-week queries**: computed server-side from `current_user.id`'s own active plan — no client input determines *whose* current week is returned, only the client's own session identity does.
- **Anonymous research plans**: continue to receive zero `training_plan_workouts` rows for any week (§8, §15) — the ownership boundary between research and consumer data is completely unaffected by this design.

Cross-user access continues to return `404` (never `403`, never a distinguishable error) everywhere this convention already applies — nothing here changes that.

---

## 15. Research Isolation

**The `if current_user:` gate already guarding `archive_previous_active_plans()`/`materialize_week_one()`'s successor inside `generate_plan()` is the entire mechanism preserving this separation — it is not technically difficult, and no workaround or special-casing is needed.** An anonymous request (`current_user is None`) never reaches the materialization call at all, regardless of how many weeks the underlying `rule_plan["weeks"]` list now describes.

The one shared file this design touches, `app/rules/generator.py`, gains only the new `weeks` key (§4) — every existing key (`week_1_plan`, `progression_schedule`, `explainability`, `paces`, `vdot`, `target_pace_per_km`) is returned with **identical** values to today, since they are all still computed by the exact same unmodified code paths. Research code (`app/routes/evaluation_routes.py`, `EvaluationStatsPage.jsx`, `PlanResultPage.jsx`, `PlanDetailPage.jsx`, `CreatePlanPage.jsx`) reads only the pre-existing keys and never reads `weeks` — it does not need to change, and does not change, because there is nothing new for it to accidentally pick up.

Explicitly confirmed unaffected: `/research/*` routing, anonymous plan generation semantics, evaluation submission, evaluation statistics, and all research terminology. `git diff --stat` against `app/rules/vdot.py`, `app/ai/`, `app/routes/evaluation_routes.py`, and every research frontend file must show zero change at implementation time, exactly as every prior phase has verified.

---

## 16. Performance

Row-count table, matching the prompt's own examples against this design's actual output (always 7 rows/week including rest days, regardless of `training_days_per_week`):

| Plan | Rows created |
|---|---|
| 4 weeks | 28 |
| 8 weeks (default) | 56 |
| 12 weeks | 84 |
| 16 weeks | 112 |
| 24 weeks (max) | 168 |

(The prompt's own illustrative "8 weeks × 5 runs = ~40 rows" undercounts because it excludes rest-day rows — this design's actual materialization always produces 7 rows/week, matching the existing week-1 behavior exactly, not 5.)

**Existing indexes are already sufficient**: `ix_tpw_plan_week (training_plan_id, week_number)` covers every query pattern this design introduces (full-plan fetch, a future `?week=N` filter, the dashboard's `week_number == current_week` lookup) without any new index. At the maximum 24-week/168-row plan, `GET /api/plans/{id}/workouts`'s response body is at most ~168 small JSON objects — comfortably under any pagination threshold, so **no pagination is introduced**, matching the instruction not to add it without justification. **No caching, background worker, or rollup is introduced** — materializing everything eagerly at generation time (§6) is cheap enough at these volumes that there is nothing to optimize.

---

## 17. Testing Design

**Rule engine** (extending `test_rule_engine.py`'s existing pattern, or a focused new test module):
- A plan generated with `plan_duration_weeks=N` produces a `weeks` list of exactly `N` entries.
- Each week's `weekly_mileage_km` matches its corresponding `progression_schedule` entry's `target_mileage_km` (proving each week genuinely uses its own target, not a duplicate of week 1).
- A deload week (every 4th week, per existing logic) produces a visibly lower long-run/quality/easy distance than the week before it.
- The final (taper) week produces the expected reduced volume.
- Day-of-week placement (long-run day, quality day, rest days) is **identical** across every week of the same generated plan (proving §3's "day layout constant, volume varies" property directly).
- Boundary durations: `4` and `24` weeks both succeed and produce plausible progressions; `3` and `25` are rejected by the existing Pydantic validation (regression of an already-existing check, not new logic).

**Materialization** (extending `test_plan_lifecycle.py`):
- A plan with `plan_duration_weeks=N` produces exactly `N * 7` `training_plan_workouts` rows.
- Every row has the correct `week_number` (1..N, each appearing exactly 7 times).
- `scheduled_date_for` (generalized, §7) produces correct, non-overlapping date ranges for every week, re-verified for start dates on Monday, mid-week, and Sunday (extending Phase 3's existing boundary-test matrix with a week-number dimension).
- No rest-day row is ever missing (every week still has exactly 7 rows including its rest days).
- The existing unique constraint prevents duplicate `(plan, week, day)` rows — attempting to materialize the same plan twice raises, proving non-idempotency is enforced structurally (§6).

**Existing plans** (regression-focused):
- A plan generated *before* this change (simulated via a fixture that only materializes week 1) continues to be fully readable, linkable, and correctly reports "current week detail not available" once its `current_week` exceeds 1 — extending, not replacing, `test_plan_lifecycle.py`'s existing assertions.
- Historical links on an archived plan remain readable for a non-week-1 row, extending `test_workout_linking.py`'s existing archived-plan fixtures.
- No fabricated data appears for any week beyond what a given plan actually materialized.

**API**:
- `GET /api/dashboard/summary` correctly resolves `today_scheduled_workout`/the renamed current-week fields for a plan currently in week 3 of 8 (a genuinely new scenario Phase 3/4 never had real data to test).
- `GET /api/plans/{id}/workouts` returns rows spanning multiple weeks, correctly ordered.
- Ownership/cross-user `404` re-verified with a multi-week fixture present (extends existing tests, doesn't replace them).
- Invalid `plan_duration_weeks` (outside 4–24) continues to be rejected — regression of existing validation.

**Integration test** (the exact scenario the prompt requests): `Create Plan (duration=8) → materialize full 56-row schedule → GET /plans/{id}/workouts shows all 8 weeks → GET /dashboard/summary shows week 1's today's workout → advance the fixture's simulated "today" into week 3 → GET /dashboard/summary now shows week 3's today's workout → log a workout linked to a week-3 scheduled row → that row shows completed with planned-vs-actual → GET /dashboard/progress reflects the logged workout` — one end-to-end fixture, mirroring the style already used by the Phase 3/4 fixture tests.

**Frontend** (manual, three-viewport, matching the established ritual): week-tab navigation at 375/768/1440px with no horizontal overflow; week 1 renders rich AI-text cards; week 2+ renders lean cards with no visual error from missing `warmup_cooldown`/`workout_execution`; the current week auto-selects on Plan Detail load; a completed workout and a not-logged workout both display correctly in a non-week-1 tab; an archived plan's historical week 6 link still displays correctly with the CTA suppressed for any of its uncompleted rows (Phase 3 behavior, re-verified in a multi-week context).

**Regression target: all 178 existing tests (as of `7c34963`) remain green, unmodified. 0 regressions.** The one function signature that gains a required parameter (`scheduled_date_for`) has every existing call site updated in the same change — a mechanical, fully-test-covered update, not a source of regression risk if done together.

---

## 18. Migration Strategy

**Zero schema migration.** `alembic/versions/` remains at `0003_add_workout_logging.py` through this design — no new table, no new column beyond the two purely additive Pydantic response fields (`start_date` on `PlanGenerationResponse`, which is a response-shape change, not a database schema change) and the two renamed (not newly added) response field names (§12), neither of which touches `alembic` at all.

If a future design ever genuinely requires a schema change (none is found here), the same discipline already established across every prior phase applies: rehearse on a database copy first, verify research-table row counts and content byte-for-byte before and after, apply only after explicit approval, never fabricate historical data for existing rows.

---

## 19. Scope

**Must-have**
1. `app/rules/generator.py`: produce the `weeks` list for every plan (§3/§4).
2. `app/workouts/service.py`: generalize `scheduled_date_for()` (week-number parameter, §7); rename and extend the materializer to cover every week (§6).
3. `app/routes/plan_routes.py`: call the generalized materializer; add `start_date` to `PlanGenerationResponse` (§13).
4. `app/routes/dashboard_routes.py`: remove the week-1 gate, query the actual current week, rename the three response fields (§12).
5. `PlanNewPage.jsx`: add the duration selector (§2).
6. `PlanDetailConsumerPage.jsx`: add week-tab navigation, current-week auto-select, lean rendering for weeks 2+ (§10).
7. `DashboardPage.jsx`: mechanical field-name follow-through for the §12 rename — no structural change.
8. The derived "plan finished" indicator (§9), surfaced on Dashboard and/or Plan Detail.

**Nice-to-have**
- `?week=N` query-parameter filtering on `GET /api/plans/{id}/workouts` (not needed at current row-count scale, §16).
- Extending AI personalization to weeks 2+ (explicitly excluded from this phase by direct instruction, §5).
- An explicit standalone "archive this plan" action independent of generating a new one.
- A persisted user-preferred default duration (would need one new nullable `UserProfile` column — not proposed now).

**Out-of-scope** (restated as firm commitments, matching every prior phase): autonomous AI adaptation, automatic plan mutation, AI-generated rich prose for every week, fitness/readiness scores, race prediction, injury prediction, overtraining diagnosis, wearable integrations, social/leaderboard features, payments/subscriptions, push notifications, advanced analytics beyond what Phase 4 already built.

---

## 20. Risks and Open Questions

Resolving each of the prompt's nine explicit points, none left open:

1. **`week1_detail_available` naming** — **Resolved**: renamed to `current_week_detail_available` (§12).
2. **`week1_completed_count` naming** — **Resolved**: renamed to `current_week_completed_count` (§12), with `week1_total_loggable_count` → `current_week_total_loggable_count` alongside it.
3. **Week 1 AI-rich vs. Week 2+ lean rendering** — **Resolved by direct instruction**: confirmed, weeks 2+ are lean, no AI prose is generated for them (§5).
4. **Plan duration UX** — **Resolved**: Option C, default 8, curated dropdown over the validated 4–24 range (§2).
5. **Old plan compatibility** — **Resolved**: unchanged behavior, no migration, no lazy materialization, no fabrication (§8).
6. **Rule-engine schedule consistency** — **Resolved**: `distribute_workouts_across_week()` reused unmodified per week; day-of-week placement is provably identical across weeks because it does not depend on `weekly_mileage` (§3).
7. **Plan JSON duplication** — **Resolved**: `week_1_plan` and `weeks[0]` deliberately share values (generated from one call), justified as the minimum duplication needed to avoid touching `app/ai/` (§4).
8. **Source-of-truth boundaries** — **Resolved**: `training_plan_workouts` for scheduling, `weeks` for materialization input, `week_1_plan`/`ai_plan_json` for generation-time rich display, `progression_schedule` for per-week mileage/phase metadata (§4).
9. **Hidden assumptions discovered while designing** — two favorable ones, both verified by re-reading the actual code, neither a problem: (a) `distribute_workouts_across_week()`'s day-selection logic already does not depend on `weekly_mileage`, making multi-week generation far simpler than a naive re-implementation would require; (b) `ScheduledWorkoutSummary` was already fully lean since Phase 3, meaning Workout Detail needs zero changes for this phase.

**No open question remains that requires your decision before implementation can begin.**

**Residual risks** (not decisions, just named for transparency):
- The visible quality gap between week 1's rich cards and weeks 2+'s lean cards within the same plan is an accepted, explicit product tradeoff per direct instruction, not an oversight — worth being aware it will be visible to real users.
- Renaming the three dashboard response fields (§12), while low-risk given the single-consumer situation, still requires the implementation step to update every call site in the same change to avoid a transient inconsistency — flagged here as an implementation-sequencing note, not an open design question.

---

## 21. Proposed Implementation Sequence

1. **Design approval** (this document) — gate: explicit sign-off before any code is written.
2. **Rule engine multi-week generation** (`app/rules/generator.py`) + its own unit tests (§17) — gate: new `weeks` key verified correct in isolation, `week_1_plan`/`progression_schedule` verified byte-identical to pre-change output for the same input profile.
3. **Backend materialization** (`app/workouts/service.py`'s generalized `scheduled_date_for`/materializer) + tests — gate: a generated plan produces the exact expected row count and week/day/date correctness before touching any route.
4. **API/dashboard changes** (`plan_routes.py`, `dashboard_routes.py`) + tests — gate: full existing suite (178 tests) still green, plus new tests for a multi-week dashboard scenario.
5. **Frontend multi-week UX** (`PlanNewPage.jsx` duration selector, `PlanDetailConsumerPage.jsx` week navigation, `DashboardPage.jsx` field-rename follow-through) — gate: manual verification at 375/768/1440px, no console errors, no overflow.
6. **Compatibility verification** — gate: a pre-existing (simulated old-shape) plan fixture still behaves correctly; archived-plan historical links across a non-week-1 row still resolve correctly.
7. **Full test suite** — gate: 0 regressions against the 178-test baseline, all new Phase 5 tests passing.
8. **Browser verification** — gate: the full manual checklist from §17's frontend section, plus a live two-account security spot-check mirroring every prior phase's own practice.
9. **Final read-only audit** — gate: scope/security/statistics/API/frontend/research-isolation/design-consistency review, mirroring the audit format already used for Phases 2–4, before any commit.
10. **Commit** — only after the audit's verdict is `READY TO COMMIT`.
11. **Push** — normal push only, to `origin/master`, only after commit.

---

## 22. Acceptance Criteria

1. A new consumer plan with `plan_duration_weeks = N` creates exactly `N * 7` `training_plan_workouts` rows, spanning `week_number` 1 through N.
2. Each week's materialized distances genuinely differ according to that week's own `progression_schedule` mileage target (not a duplicate of week 1's values, except where week 1 itself is being compared to itself).
3. Week 1 continues to render with full AI-personalized content, byte-identical to pre-Phase-5 behavior for the same input profile.
4. Weeks 2+ render correctly using only deterministic rule-based fields, with no error or missing-data artifact from the absence of AI text.
5. `scheduled_date_for` produces correct, verified dates for every week, for plans starting on Monday, mid-week, and Sunday.
6. The Dashboard shows the correct actual current week's data (not always week 1) once a plan is more than one week old.
7. Planned-vs-actual linking, completion derivation, and archived-plan-link rejection/preservation all continue to work correctly for a non-week-1 scheduled workout.
8. An existing (pre-Phase-5-shaped) plan with only 7 rows continues to function with no error and no fabricated data for its un-materialized weeks.
9. Anonymous research plan generation produces zero `training_plan_workouts` rows, for any duration, unchanged.
10. `git diff --stat` against `app/rules/vdot.py`, `app/ai/`, `app/routes/evaluation_routes.py`, and every research frontend file shows no change beyond the additive `weeks` key in `generator.py`'s return value.
11. No new database table or column exists; `alembic/versions/` is unchanged from `0003_add_workout_logging.py`.
12. All 178 pre-existing tests pass unmodified, plus every new Phase 5 test.
13. The research flow (generate → evaluate → statistics) is manually re-verified end-to-end with zero behavioral change.
14. Plan Detail's week navigation and Plan Creation's duration selector both render without horizontal overflow at 375/768/1440px.
15. No new console error appears anywhere in the multi-week flow.
16. No code path allows a workout log, its edit, or its deletion to automatically modify any `training_plans`/`training_plan_workouts` row — confirmed by code review, not only by the absence of a failing test.

---

## 23. Final Recommendation

**No schema changes are needed.** Full multi-week materialization into the existing `training_plan_workouts` table — extended from covering only week 1 to covering every week of the plan — is the recommended mechanism, keeping that table as the single normalized consumer-scheduling source of truth exactly as it already is today, with no second competing source introduced. AI personalization remains scoped to week 1 only, with zero changes to `app/ai/`; weeks 2+ use plain deterministic rule-based fields, rendered through the exact lean-`WorkoutCard` pattern the Dashboard already proved works. Plan duration becomes user-selectable (default 8, range 4–24, already backend-validated) via a small frontend addition, with `total_weeks` always derived from the plan JSON, never separately persisted. Old plans are left entirely alone — no migration, no backfill, no fabricated history — because materialization only ever happens once, at generation time, for a plan that does not yet exist at the moment this change ships. Research plan generation is untouched, protected by the same `if current_user:` gate already in place today. The first implementation step should be the rule-engine extension (§21, step 2) in isolation, verified against its own unit tests before any route, materializer, or frontend code is touched — because everything else in this design depends on that single, deterministic, already-de-risked change actually producing correct per-week data.

---

**Design Status: DESIGN COMPLETE — WAITING FOR IMPLEMENTATION APPROVAL**

# Phase 3 Technical Design — Plan ↔ Actual Workout Integration

**Date:** 2026-09-29
**Status:** DESIGN ONLY. No application code, database, migration, or dependency was changed to produce this document. See the "Implementation Readiness" section and the final safety verification at the end.

---

## 1. Executive Summary

Phase 2 built two things side by side without connecting them: `training_plan_workouts` (what's scheduled) and `workout_logs` (what actually happened), joined by a nullable `workout_logs.training_plan_workout_id` column that Phase 2 deliberately defined but never used. Phase 3's job is to **close that loop** — let a user say "this is the run I did for today's scheduled session" and see a simple planned-vs-actual comparison — without touching the schema, without fabricating any data the rule engine doesn't actually produce, and without ever letting a logged workout automatically rewrite a training plan.

**The most important finding of this design:** Phase 3 needs **zero schema changes**. The ownership-safe linking mechanism (`_resolve_owned_training_plan_workout()` in `workout_routes.py`) was already built and tested in Phase 2 — it is simply unused by any frontend UI today. Phase 3 is therefore primarily an **API response-shape enrichment + frontend feature** built entirely on existing tables, plus one new *derived* (never stored) completion-state concept.

Completion state, planned-vs-actual deltas, and a week-1 adherence percentage are all computed **on read**, from data that already exists — no new mutable column is introduced anywhere. This follows the brief's own instruction to prefer derived state over redundant stored state, and it means editing or deleting a logged workout automatically and correctly un-completes/re-completes its scheduled slot with no extra bookkeeping.

Phase 3 explicitly does **not** extend the rule engine to produce weeks 2+, and explicitly does **not** let any workout log, RPE, or adherence number automatically change a training plan. Both are called out as separate, larger decisions for a future phase, consistent with Section 3's framing of Phase 3 as "not yet about automatically changing training plans."

---

## 2. Current Phase 2 Architecture Findings

Read directly from the current codebase (not from memory of the design docs, per instruction) on 2026-09-29:

- **`backend/app/models.py`**: `TrainingPlanWorkout` (scheduled, read-only, week-1-only, 7 rows per consumer plan including rest days at `distance_meters=0`) and `WorkoutLog` (actual, soft-deletable, `training_plan_workout_id` nullable FK) exist exactly as documented in `PHASE_2_DESIGN.md`/`PHASE_2_REPORT.md`. `TrainingPlan.status` is a free-text `VARCHAR(20)` but in practice only ever set to `'active'` or `'archived'` by the current code (`app/routes/plan_routes.py`, `app/workouts/service.py`) — no `'draft'` or `'completed'` value is ever written today, despite being mentioned as *possible* values in the Phase 2 design doc's comment.
- **`backend/app/routes/workout_routes.py`**: `_resolve_owned_training_plan_workout()` **already performs the exact ownership JOIN Phase 3's brief asks for** (`workout_log → training_plan_workout → training_plan → training_plan.user_id == current_user.id`), already wired into both `POST /api/workouts` and `PATCH /api/workouts/{id}` (only when `training_plan_workout_id` is present in the payload), already returns a generic `400 Invalid training_plan_workout_id.` for both "doesn't exist" and "belongs to someone else," and is **already covered by three passing tests** in `test_workouts.py` (`test_cannot_link_workout_to_another_users_training_plan_workout`, `test_can_link_workout_to_own_training_plan_workout`, `test_nonexistent_training_plan_workout_id_is_rejected`). **This is the single biggest finding of this design phase: the hard security work for linking is done and tested; nothing in Section 6/18 below requires new backend validation logic, only reuse of what exists.**
- **`backend/app/workouts/schemas.py`**: `WorkoutLogCreate`/`WorkoutLogUpdate` already accept `training_plan_workout_id: Optional[str] = None`. `WorkoutLogResponse.from_model()` currently returns the raw `training_plan_workout_id` string but **no enriched schedule detail** (no day/type/planned-distance) — a frontend showing "Planned: Easy Run 5km" next to a logged workout would need a second fetch today, or (as Section 13 proposes) a small additive enrichment.
- **`frontend/src/components/WorkoutForm.jsx`**: has **no field at all** for `training_plan_workout_id` — a user cannot link a workout to a scheduled session anywhere in the current UI, confirmed by reading the full component. This is the concrete gap Phase 3 closes on the frontend.
- **`frontend/src/pages/DashboardPage.jsx`**: renders `today_scheduled_workout` via the existing `WorkoutCard` component with no completion indicator and no "log this" shortcut — logging today's run and logging any other run use the identical generic `/workouts/new` link.
- **`frontend/src/pages/PlanDetailConsumerPage.jsx`**: renders the 7 week-1 `WorkoutCard`s with no completion state and no link back to any actual workout.
- **`frontend/src/pages/HistoryPage.jsx`** / **`WorkoutDetailPage.jsx`**: show only the actual-workout fields; nothing indicates whether a history row is linked to a plan.
- **`backend/app/rules/generator.py`**: confirmed again, read in full — `week_1_plan.workouts` is the only fully-detailed output; `progression_schedule` (weeks 1..N) is `[{week_number, target_mileage_km, phase, focus_note}]`, a single number per week, **no day-by-day breakdown**. This is unchanged since Phase 2 and remains the hard constraint on Section 5's "weeks beyond week 1" question.
- **`backend/app/routes/dashboard_routes.py`**: `_period_totals()` (volume-weighted pace, calendar week/month, no timezone) and the week-1-only `today_scheduled_workout` resolution are both confirmed unchanged and are reused, not replaced, by this design.
- **`backend/app/routes/plan_routes.py`**: `GET /api/plans/{plan_id}/workouts` (ownership pattern identical to `GET /api/plans/{plan_id}`) and `GET /api/plans/mine` both already exist and are reused as-is (Section 13).
- **Test baseline confirmed by re-running the suite during this design task**: `122 passed, 0 failed` (see Section 18 for the exact command/output). This is the regression baseline Phase 3 implementation must not break.

---

## 3. Phase 3 Objective

Connect the plan to what actually happened, without ever letting a single workout silently rewrite a plan:

```
Training Plan
  ↓
Scheduled Workout (training_plan_workouts, week 1 only)
  ↓
Today's Planned Workout (dashboard)
  ↓
User Runs
  ↓
User Logs Actual Workout (workout_logs), optionally linking it
  ↓
Actual Workout linked to Scheduled Workout (workout_logs.training_plan_workout_id)
  ↓
Planned vs Actual comparison (descriptive, computed on read)
  ↓
Descriptive adherence/progress context (week-1 completion count, purely informational)
  ↓
[Future phase only] This context may inform the next plan regeneration —
never an automatic mutation of the current plan.
```

Everything left of the last arrow is Phase 3. The last line is explicitly **not** Phase 3 (Section 20).

---

## 4. User Journey

1. User opens the Dashboard. If they have an active plan in week 1, they see today's scheduled workout with a clear state: **Not logged yet** or **Completed** (Section 8).
2. If not logged yet, a **"Log this workout"** button pre-fills the workout form with today's date, the scheduled `workout_type`/distance as a starting point, and silently carries the scheduled workout's ID.
3. User adjusts the actual numbers to what they really did (or logs something completely different — the app never blocks this) and submits.
4. The workout is saved as an ordinary `workout_log`, now carrying `training_plan_workout_id`. The scheduled workout's derived status flips to **Completed** on the next read — no separate "mark complete" action exists.
5. On Plan Detail, that day's card now shows the planned figures next to the actual figures logged against it (Section 7).
6. On History, that workout's row shows a small "Planned: Easy Run" tag, distinguishing it from a standalone log.
7. If the user edits the actual workout (e.g., corrects the distance) or unlinks it, the comparison updates on the next read. If they delete it (soft delete), the scheduled workout reverts to **Not logged yet** or **Missed**, again with zero extra bookkeeping.
8. Past week 1, there is no scheduled workout to link to — the user logs standalone workouts exactly as they do today, with no regression in that experience.

---

## 5. Data Model Analysis

### 5.A How a scheduled workout is represented (existing, unchanged)

`training_plan_workouts` — one row per calendar day of week 1 of a consumer plan (7 rows always, including rest days), each carrying `week_number` (always `1` today), `day_of_week` (a weekday *name*, not a date), `workout_type`, `distance_meters`, `pace_target`, `intensity_zone`, `purpose`. It is a read-only, immutable snapshot taken once at plan-generation time.

**A concrete gap this design closes:** `day_of_week` is a name, not a date, so nothing today can answer "what calendar date was Tuesday's scheduled workout?" without also knowing the plan's `start_date`. Phase 3 needs this to determine whether a given scheduled day is in the past (candidate for "missed"), today, or upcoming. The existing dashboard code already implicitly does this matching (`today_name = today.strftime("%A")`, matched only when `current_week == 1`), but doesn't generalize it to every day of the week. **Design decision:** introduce one small, pure, stateless helper function (no schema change):

```python
def scheduled_date(plan_start_date: date, day_of_week: str) -> date:
    """The one calendar date within [plan_start_date, plan_start_date+6] whose
    weekday name matches day_of_week. Every weekday name appears exactly once
    in any 7 consecutive calendar days, so this is always well-defined for a
    week-1 row."""
    target_idx = DAYS_OF_WEEK.index(day_of_week)  # Monday=0..Sunday=6
    offset = (target_idx - plan_start_date.weekday()) % 7
    return plan_start_date + timedelta(days=offset)
```
This is pure computation over already-stored data (`training_plans.start_date`, `training_plan_workouts.day_of_week`) — no new column, no migration.

### 5.B How a workout log is linked to a scheduled workout (existing, unchanged)

`workout_logs.training_plan_workout_id` — nullable FK, already present, already validated server-side (Section 2). Phase 3 adds **no new column** here. Multiple `workout_logs` rows *may* reference the same `training_plan_workout_id` (no uniqueness constraint exists today) — this is intentional and is exactly what makes Section 9's duplicate-handling simple (see below).

### 5.C How weeks beyond week 1 are handled

**Unchanged from Phase 2: there is nothing to link to.** No `training_plan_workouts` rows exist for week 2+ because the rule engine (`app/rules/generator.py`) does not produce day-by-day detail for them — confirmed again by reading `generate_rule_based_plan()` in full during this design task. A user in week 2+ simply logs a standalone workout (`training_plan_workout_id = null`), identical to today's behavior. Nothing in Phase 3 degrades or changes this.

### 5.D Should Phase 3 materialize additional weeks?

**No — continue supporting week 1 only, and explicitly park multi-week materialization as a separate dependency, not part of this design.** Reasoning:
- Materializing real per-day workouts for weeks 2+ requires the rule engine to *generate* that detail first (it currently only computes a single `target_mileage_km` per week). That is a nontrivial rules-engine extension (deciding day placement, quality/long-run/easy distribution, progression-aware pacing for every week, not just week 1) — a meaningfully sized, separate piece of work with its own design questions (e.g., does week 2's long-run day move if the user's preferred days change mid-plan?).
- Fabricating placeholder scheduled workouts for weeks 2+ from just the summary mileage number would violate the brief's explicit instruction ("Do NOT fabricate workouts for weeks that the generator does not actually provide") and would silently misrepresent what the AI/rule engine actually decided.
- Phase 3's plan↔actual linking feature is fully valuable and testable using week 1 alone — every new user's first week is exactly when the loop matters most for onboarding retention.

**Recommendation, requiring approval:** extending the generator to multi-week daily detail is a good candidate for a **dedicated future design document** (tentatively "Phase 3.5" or an early Phase 4 item), explicitly scoped as a rule-engine change, not bundled here.

---

## 6. Workout ↔ Scheduled Workout Relationship (Linking)

### 6.1 Ownership chain (already enforced, reused as-is)

```
workout_log.training_plan_workout_id
        ↓
training_plan_workout.training_plan_id
        ↓
training_plan.user_id == current_user.id   ← the only trusted authority
```

This exact chain is already implemented in `_resolve_owned_training_plan_workout()` (`backend/app/routes/workout_routes.py:23`) and called from both create and update. Phase 3 introduces no new write path that bypasses it — any new endpoint or enrichment that resolves a `training_plan_workout_id` reuses this same function or an equivalent read-only ownership filter.

### 6.2 Create behavior

Unchanged: `POST /api/workouts` already accepts `training_plan_workout_id` and validates ownership before insert. **Phase 3 frontend change:** the "Log this workout" CTA (Section 10) pre-fills this field from a query parameter or router state, but the field is still validated server-side exactly the same way regardless of what the client sends — the CTA is a UX convenience, not a trust boundary.

### 6.3 Edit behavior

Unchanged: `PATCH /api/workouts/{id}` already re-validates `training_plan_workout_id` via the same helper whenever the field is present in the payload (`if "training_plan_workout_id" in updates:`). **Phase 3 frontend change:** `WorkoutDetailPage`'s edit mode gains a way to change or clear this link (Section 11/13).

### 6.4 Unlink behavior

**Supported today with zero backend change**, confirmed by reading the code: sending `PATCH /api/workouts/{id}` with `"training_plan_workout_id": null` is picked up by `payload.model_dump(exclude_unset=True)` (the key is present because it was explicitly sent, even though its value is `null`), routed through `_resolve_owned_training_plan_workout(db, None, current_user)` which returns `None` immediately for a `None` ID, and then `setattr(workout, "training_plan_workout_id", None)`. **Phase 3 only needs a frontend "Unlink" action that sends this payload** — no backend work.

### 6.5 Deletion behavior

Unchanged: `DELETE /api/workouts/{id}` soft-deletes the `workout_log` (`deleted_at = now()`). Because completion state is **derived** by querying non-deleted logs (Section 8), deleting a linked log automatically makes its scheduled workout revert to its prior derived state on the very next read — no cleanup code needed, no dangling "completed" flag left behind. This is the concrete payoff of choosing derived over stored state.

### 6.6 Cross-user attack cases and expected HTTP behavior

See Section 18 (Security Model) for the full attack-case table — restated briefly here since it's the crux of this section: submitting another user's `training_plan_workout_id` on create or update returns `400 Invalid training_plan_workout_id.`; the workout is never created/updated with that link, and no distinction is made in the error between "doesn't exist" and "belongs to someone else."

### 6.7 Behavior when the referenced scheduled workout belongs to an archived plan

**Design decision: linking to a scheduled workout on an archived (not deleted) plan is allowed.** `training_plan_workouts` rows are never deleted when a plan is archived (`archive_previous_active_plans()` only ever updates `TrainingPlan.status`, never touches `TrainingPlanWorkout` rows or cascades a delete). An archived plan's schedule is historical record, not gone — a user should still be able to look back at "what I was supposed to do in my previous plan" and see what they actually logged against it. The ownership check (`TrainingPlan.user_id == current_user.id`) does not filter on `status` at all today, and this design does not add such a filter. **This needs explicit sign-off** since it's a considered choice, not an oversight (see Section 21 open questions if you'd prefer archived-plan links to be blocked instead).

---

## 7. Planned vs Actual Model

Purely descriptive, computed on read, never stored:

| Planned (from `training_plan_workouts`) | Actual (from linked `workout_logs`) |
|---|---|
| `workout_type` (e.g. "Interval Training") | `workout_type` (e.g. `INTERVAL`) — shown via the existing `workoutTypeLabel()` mapping for a cleaner side-by-side, but never validated/enforced to match |
| `distance_km` (derived from `distance_meters`) | `distance_km` |
| `pace_target` (a string, sometimes a range e.g. "05:50 - 06:27 /km") | `pace_display` (a single computed value, e.g. "05:35 /km") |
| `intensity_zone` | *(no actual equivalent — descriptive only, shown for context)* |
| `purpose` | *(no actual equivalent — shown for context)* |
| *(no planned equivalent)* | `duration_seconds`, `rpe`, `avg_heart_rate`, `cadence_spm`, `elevation_gain_m`, `notes` |

**Display, not computation, does the comparing** — e.g. "Planned: 5.0 km · Actual: 5.2 km" side by side. The only numeric delta computed is a simple difference/percentage for distance (`actual_km - planned_km`, and `actual_km / planned_km * 100` rounded), explicitly labeled "vs planned distance" — never a score, grade, or letter rating.

**Explicitly not built:** no "AI score," no "fitness score," no "you trained 87% correctly," no predicted race outcome, no medical-certainty language anywhere in this comparison. A completed-but-shorter-than-planned run is shown as exactly that — "Actual 3.1 km vs planned 5.0 km" — and nothing else is inferred from it.

**If a single number is wanted for "how much of the plan happened," it is the week-1 completion count/percentage defined precisely in Section 8.4 below — always labeled as a count of logged-vs-scheduled sessions, explicitly not a measure of fitness or training quality**, per the brief's explicit requirement to define exactly how any percentage is calculated.

---

## 8. Completion-State Model

### 8.1 Decision: derived, not stored

No new column is added to `training_plan_workouts` or anywhere else. Status is computed at read time from data that already exists: `training_plan.start_date` + `training_plan_workout.day_of_week` (→ `scheduled_date`, Section 5.A) and the presence/absence of a non-deleted `workout_log` with matching `training_plan_workout_id`.

### 8.2 States

Three states, not four — **no `partially_completed`** (see 8.3 for why):

| State | Condition |
|---|---|
| **Completed** | At least one non-deleted `workout_log` exists with `training_plan_workout_id == this row's id` |
| **Missed** | `scheduled_date < today` AND no such log exists |
| **Scheduled** | `scheduled_date >= today` AND no such log exists |

**Rest days are excluded from this model entirely.** A `training_plan_workout` whose `workout_type` contains "Rest" (matching the existing frontend convention already used in `WorkoutCard.jsx`'s `isRest` check) never shows Completed/Missed/Scheduled and never gets a "Log this workout" CTA — there is nothing to log against a rest day, and treating it as "missed" would be actively wrong.

### 8.3 Why no `partially_completed`

Introducing a partial state requires an arbitrary threshold ("what % of planned distance counts as partial vs. complete?") with no physiologically or product-meaningful default. The planned-vs-actual comparison (Section 7) already surfaces a shortfall descriptively and honestly ("Actual 3.1 km vs planned 5.0 km") without forcing a binary or ternary judgment call onto it. **Completed simply means "at least one log exists for this slot"** — the comparison view is where the user (or a future coach feature) judges quality, not a stored/derived status enum. This is the simplest model that is still correct, per the brief's explicit preference.

### 8.4 Source of truth, who changes it, derivation

- **Source of truth:** the existence and `deleted_at` state of `workout_logs` rows, plus `scheduled_date` arithmetic (Section 5.A) — nothing else.
- **Who changes it:** nobody directly. It is never set by any endpoint; it falls out of ordinary create/edit/delete of a workout log.
- **Editing a linked actual workout:** does not change the derived state (still Completed) unless the edit *removes* the link (Section 6.4), which reverts it to Missed/Scheduled per 8.2.
- **Deleting a linked actual workout:** reverts the derived state immediately on the next read (Section 6.5) — no cleanup needed.
- **Duplicate logs:** do not create any special state — "Completed" is a boolean fact (≥1 log exists), not a count; Section 9 covers duplicates in full.

### 8.5 Week-1 completion count (the one aggregate number proposed)

`completed_count / total_loggable_count` where `total_loggable_count` = the number of week-1 `training_plan_workouts` rows **excluding rest days** (typically 4–6 of the 7 rows, depending on `training_days_per_week`). Labeled explicitly wherever shown: **"3 of 5 planned runs logged this week"** — a plain count, never phrased as a percentage of "correctness," "adherence quality," or "fitness." This is optional polish for Plan Detail (Section 12), not a blocking requirement, and requires no schema change since it's computed from the same query used to render the 7 workout cards.

---

## 9. Duplicate / Multiple Workout Handling

Deliberately kept minimal — the existing schema already accommodates every case below with **no change**:

1. **Same run logged twice accidentally.** Both rows exist as ordinary `workout_logs`. If the user linked both to the same scheduled workout, the derived state is still just "Completed" (a boolean, Section 8.4) — no double-counting bug possible. The user deletes the duplicate via the existing soft-delete UI; nothing special is needed because nothing special was introduced.
2. **Two runs in one day (e.g., AM/PM double).** Both are ordinary, independent `workout_logs` with the same `workout_date`. At most one *should* sensibly link to that day's single scheduled workout (Section 9 doesn't force this), but nothing prevents linking both if the user wants to — same reasoning as case 1.
3. **Standalone workout, no plan link.** Already fully supported (`training_plan_workout_id = null`); this is in fact the majority case outside week 1 and remains completely unaffected by Phase 3.
4. **Actual workout differs significantly from the planned one** (e.g., planned Long Run 10km, actual is a 3km recovery jog because of a tweaked ankle). Linking is still allowed — Phase 3 does not validate or block a "mismatched" link. The planned-vs-actual view (Section 7) shows the honest gap; forcing type/distance agreement before allowing a link would be paternalistic and would actively discourage honest logging.
5. **User edits a linked workout.** Ordinary `PATCH`; the link is untouched unless the edit payload explicitly changes/clears `training_plan_workout_id` (Section 6.3/6.4).
6. **User deletes a linked workout.** Ordinary soft delete (Section 6.5); derived state reverts automatically.
7. **Multiple scheduled workouts on one day** (a future possibility the brief asks to consider). **Not possible today** — `UNIQUE(training_plan_id, week_number, day_of_week)` on `training_plan_workouts` guarantees exactly one row per calendar day of week 1. If a future phase wants AM/PM double-session scheduled plans, that unique constraint would need to be relaxed (e.g., add a `slot` column) — **explicitly out of scope here**, flagged only so it isn't forgotten if ever requested.

**Recommendation: no deduplication logic, no "are you sure this is a duplicate?" warning, no uniqueness constraint added.** Simpler is correct here — the user is trusted to manage their own logged data (as they already are for standalone workouts today), and every case above degrades gracefully to existing, already-tested behavior.

---

## 10. Dashboard Changes

Extends `DashboardPage.jsx` and `GET /api/dashboard/summary`'s `active_plan.today_scheduled_workout` — same endpoint, enriched response (Section 13), not a new one.

### 10.1 Additions

- **Completion badge** on today's scheduled workout card: "Not logged yet" (neutral/amber) or "Completed" (green), using the derived state from Section 8, computed server-side and included in the response (never computed client-side from raw dates, to keep "today" server-authoritative and consistent with the rest of the app's no-timezone-drift design).
- **"Log this workout" button** directly on the card when not yet completed, navigating to `/workouts/new?scheduled=<training_plan_workout_id>`; `WorkoutForm` reads this query param once on mount to pre-fill `workout_type`/`distance_km` as starting suggestions and to carry the ID through to submit (Section 13.3).
- **"View logged workout" link** on the card when already completed, linking to the (first, if duplicates exist) linked workout's detail page.
- **Upcoming scheduled workout** (optional, low-cost addition): if today is not the last day of week 1, show the next non-rest scheduled day's type/distance as a small preview line — purely descriptive, reusing data already fetched for `today_scheduled_workout`'s sibling rows via the same `training_plan_id` query, no new endpoint.

### 10.2 Explicitly excluded

Same non-goals as Phase 2 (Section 22 restates the full list): no fitness score, no streaks/gamification, no push notifications, no auto-plan-adjustment triggered from this screen.

### 10.3 Behavior matrix (all 7 states from the brief, mapped to what already exists + what's new)

| State | Dashboard shows |
|---|---|
| **A. No active plan** | Unchanged from Phase 2: empty-state "Create a Training Plan" card. |
| **B. Active plan, no scheduled workout for today** (today falls outside the 7-day window, or today is genuinely unscheduled — not expected given 7 rows always cover 7 days, but defensively handled) | Unchanged: "No scheduled workout for today." text, already implemented. |
| **C. Scheduled workout not completed** | **New:** "Not logged yet" badge + "Log this workout" CTA (10.1). |
| **D. Scheduled workout completed** | **New:** "Completed" badge + link to the logged workout. |
| **E. Week 1 available** | Full card as above. |
| **F. Week 2+ (no detailed schedule)** | Unchanged: the existing amber "Detailed daily workouts are currently only available for week 1" notice — Phase 3 adds no fabricated data here. |
| **G. Workout history exists, no active plan** | Unchanged: "This Week"/"Recent Activity" populate normally; plan card shows its own empty state independently — these two sections were already decoupled in Phase 2. |

Today's scheduled workout being a **rest day** is a related, distinct case not in the brief's list but present in real data: the card renders as it does today ("Rest Day" via the existing `WorkoutCard` `isRest` branch), with **no** completion badge and **no** "Log this workout" CTA (Section 8.2).

---

## 11. History Changes

Extends `HistoryPage.jsx` and `WorkoutLogResponse` (additive field, Section 13.1) — informational only, exactly as instructed ("do not turn History into an analytics dashboard yet"):

- Each history row that has `training_plan_workout_id` set gains a small secondary line: **"Planned: Easy Run — 5.0 km"** (reusing `workoutTypeLabel()`/the plan's own `workout_type` string), directly under the existing "Actual: 5.2 km @ 5:35/km" line (which is what the row already shows today).
- A standalone workout (no link) shows nothing extra — zero visual change from today's row for the common case, so History doesn't get visually noisier for the majority of entries outside week 1.
- No new filter is added for "planned vs standalone" in this phase — out of scope per "do not turn History into an analytics dashboard yet"; a future phase could add a filter if this proves useful, but it's not needed for the core loop to work.
- `WorkoutDetailPage.jsx` gains the same "Planned: ..." line plus an **Unlink** action (only shown when a link exists) and — while creating/editing via `WorkoutForm` — the ability to pick/change which scheduled workout it's linked to, scoped to only that user's own current (not necessarily active-only, per 6.7) plans' week-1 rows.

---

## 12. Plan Detail Changes

Extends `PlanDetailConsumerPage.jsx` and `GET /api/plans/{plan_id}/workouts` (enriched response, Section 13.2):

- Each of the 7 week-1 `WorkoutCard`s gains the same completion badge as the dashboard (Completed / Not logged yet / — for rest days).
- A completed card gets a compact planned-vs-actual block appended (Section 7's table, rendered inline) and a link to the actual workout's detail page. If more than one log is linked (Section 9, case 1/2), all are listed rather than picking one arbitrarily.
- The existing "Full multi-week daily schedules are coming in a future update" disclaimer (already present in `PlanDetailConsumerPage.jsx`) is kept verbatim — Section 5.D's decision means this remains accurate and does not need new wording.
- **Optional:** the week-1 completion count from Section 8.5 ("3 of 5 planned runs logged this week") shown once near the top of the Week 1 Schedule section, clearly labeled as a count, not a score.

---

## 13. API Changes

**Design principle applied throughout, per the brief's explicit instruction: reuse existing endpoints via additive response-shape enrichment; add no redundant new endpoint.** Every field added below is optional/nullable in the response schema, so existing frontend code that doesn't yet read the new fields keeps working unmodified — this is a backward-compatible enrichment, not a breaking change.

### 13.1 `WorkoutLogResponse` (used by `GET/POST/PATCH /api/workouts*` and the dashboard's `recent_activities`)

**Add one field:**
```
linked_scheduled_workout: Optional[TrainingPlanWorkoutResponse] = None
```
Populated by an additional (optional) join in `from_model()` when the workout has a `training_plan_workout_id` — implemented as a small variant, e.g. `WorkoutLogResponse.from_model(wl, tpw=None)`, where callers that already have the joined row (list/detail endpoints, which can eager-load it) pass it through; callers that don't care (e.g., a hypothetical future bulk export) simply omit it and get `null`. No new endpoint.

### 13.2 `TrainingPlanWorkoutResponse` (used by `GET /api/plans/{plan_id}/workouts` and the dashboard's `today_scheduled_workout`)

**Add two fields:**
```
scheduled_date: date                                   # from Section 5.A's helper
completion_status: Optional[Literal["completed","missed","scheduled"]]  # None for rest days
linked_workout_logs: List[WorkoutLogResponse] = []      # empty list, never null, for a clean frontend .map()
```
Computed server-side in the same handler that already builds these responses (`get_plan_workouts` in `plan_routes.py`, and the dashboard's `today_scheduled_workout` construction in `dashboard_routes.py`) — both already have `current_user`/`training_plan` in scope, so no new dependency or query pattern is introduced, only additional `SELECT`s scoped by the same ownership filters already in place.

### 13.3 No new endpoints required for linking or unlinking

`POST /api/workouts` and `PATCH /api/workouts/{id}` already accept `training_plan_workout_id` (Section 6). The frontend's "Log this workout" CTA (Section 10.1) is purely a **client-side pre-fill via a query parameter** (`/workouts/new?scheduled=<id>`) read by `LogWorkoutPage`/`WorkoutForm` — it calls the existing `createWorkout()` API function with the ID already in the payload, exactly like any other field. No `POST /api/workouts/{id}/link` or `/unlink` endpoint is proposed; that would duplicate what `PATCH` already does (explicitly avoided per the brief's "do not create redundant APIs").

### 13.4 Full endpoint table (only endpoints that change; everything else in Phase 2's table is untouched)

| Method | Path | Auth | Change |
|---|---|---|---|
| `GET` | `/api/plans/{plan_id}/workouts` | optional* (unchanged) | Response gains `scheduled_date`, `completion_status`, `linked_workout_logs` per row |
| `GET` | `/api/dashboard/summary` | required (unchanged) | `active_plan.today_scheduled_workout` gains the same three fields; optionally an `upcoming_scheduled_workout` sibling field (Section 10.1) |
| `GET` | `/api/workouts` | required (unchanged) | Each item gains `linked_scheduled_workout` |
| `GET` | `/api/workouts/{id}` | required (unchanged) | Gains `linked_scheduled_workout` |
| `POST` | `/api/workouts` | required (unchanged) | No request-shape change; `training_plan_workout_id` already accepted |
| `PATCH` | `/api/workouts/{id}` | required (unchanged) | No request-shape change; already supports set/clear of `training_plan_workout_id` |

*`GET /api/plans/{plan_id}/workouts` keeps its existing dual-mode auth (open for anonymous research plans, ownership-checked for consumer plans) — unchanged from Phase 2.

### 13.5 Validation / error cases (all pre-existing, restated for completeness)

- `training_plan_workout_id` referring to a nonexistent row → `400 Invalid training_plan_workout_id.`
- `training_plan_workout_id` referring to another user's plan → identical `400 Invalid training_plan_workout_id.` (no distinguishing signal)
- `training_plan_workout_id` referring to a row on the caller's own **archived** plan → **allowed** (Section 6.7)
- Workout not found / not owned (`GET/PATCH/DELETE /api/workouts/{id}`) → unchanged generic `404`

---

## 14. Security Model

Phase 3 introduces no new authentication or session mechanism. It reuses Phase 1/2's cookie session, CSRF Origin-check, and rate limiting exactly as-is — no endpoint proposed above is exempt from any of them.

### 14.1 Attack-case table (as requested by the brief), with actual current behavior verified by reading the code

| # | Attack | Expected/actual HTTP behavior |
|---|---|---|
| 1 | User A submits User B's `training_plan_workout_id` on `POST /api/workouts` | `400 Invalid training_plan_workout_id.` — verified by existing test `test_cannot_link_workout_to_another_users_training_plan_workout` |
| 2 | User A submits User B's `training_plan_id` (e.g., trying to address `GET /api/plans/{id}/workouts` with someone else's plan ID) | `404 Training plan not found` — same generic-404 ownership pattern as `GET /api/plans/{id}`, already covered by `test_plan_lifecycle.py`'s ownership tests |
| 3 | User A edits a linked workout belonging to User B (i.e., tries `PATCH /api/workouts/{B's workout id}`) | `404 Workout not found.` — `_get_owned_workout_or_404()` filters by `user_id == current_user.id` before any field is touched; verified by `test_user_a_workout_not_readable_updatable_or_deletable_by_user_b` |
| 4 | User A accesses a scheduled workout belonging to User B (via `GET /api/plans/{B's plan id}/workouts`) | `404 Training plan not found` — same as case 2 |
| 5 | A workout log references a scheduled workout that has since been deleted | **Currently unreachable**: nothing in the codebase ever deletes a `training_plan_workout` row (no `DELETE` endpoint exists, no cascade from plan archival). If this ever becomes possible (a future phase), the FK has no `ON DELETE` behavior defined today, so this must be revisited before such a delete path is added — flagged here so it isn't forgotten, not because it's reachable now |
| 6 | An archived plan is manipulated through an old URL (e.g., an old bookmark to `/plans/{archived-plan-id}`) | **Allowed, by design** — an archived plan is still the user's own data and remains fully viewable/linkable (Section 6.7); "manipulated" in the sense of being *edited* doesn't apply, since `training_plan_workouts` has no edit endpoint at all (Phase 2's design: read-only/derived, never a new authoring surface) |

### 14.2 What Phase 3 preserves unchanged (confirmed by reading the relevant modules, not assumed)

- Server-derived user identity only (`get_current_user`/`get_optional_current_user` in `app/auth/dependencies.py`) — no new dependency, no new way to resolve "current user."
- No client-supplied `user_id` anywhere — none of the enriched response shapes in Section 13 add any writable `user_id`-shaped field.
- The existing CSRF Origin-check middleware (`app/core/csrf.py`) applies automatically to any new mutating request the same way it does today — nothing in this design adds a new mutating endpoint that would need separate coverage (Section 13.3).
- The existing `RATE_LIMIT_WORKOUT_WRITE` limiter already covers `POST`/`PATCH`/`DELETE /api/workouts*` — no new write endpoint is proposed that would need a new limit.
- Soft-delete semantics (`deleted_at IS NULL` filtering) are extended, not altered — the new "linked workout logs" joins in Section 13.1/13.2 must filter `deleted_at IS NULL` exactly like every existing query does, so a soft-deleted log never counts toward completion or appears in a "linked logs" list. **This is a concrete implementation requirement to carry into Phase 3, called out explicitly so it isn't missed.**

---

## 15. Research Isolation

No research-facing file was modified to produce this design, and none is touched by any proposal in it:

- `app/rules/`, `app/ai/`, `app/routes/evaluation_routes.py`, `app/schemas.py`'s `RunnerProfileCreate`/`WorkoutItem`, and every `/research/*` frontend page are **read-only references** in this document (Sections 2 and 5.D), never modified.
- `plan_evaluations` gains **no** `user_id` column, now or ever proposed — untouched.
- `runner_profiles`/`plan_evaluations` remain unlinked to `users`; nothing in Sections 6–13 introduces any join or query that crosses from the consumer (`users` → `training_plans.user_id IS NOT NULL` → `training_plan_workouts`/`workout_logs`) branch into the anonymous research branch (`runner_profiles` → `training_plans.user_id IS NULL` → `plan_evaluations`).
- Every new query proposed (Section 13) is scoped through `training_plans.user_id == current_user.id`, which by construction can never match an anonymous research plan (`user_id IS NULL`) — the same structural guarantee Phase 1/2 already rely on.
- Research evaluation scoring, statistics aggregation (`GET /api/evaluations/stats`), and the Likert instrument are not referenced by any Phase 3 proposal.

**Verification performed for this design task:** re-read `app/rules/generator.py` and `app/models.py` in full; confirmed via `git diff` (Section "Final Safety Verification" below) that no file was modified.

---

## 16. Plan Lifecycle / Versioning Implications

**Recommendation: the current Phase 2 architecture (single active plan + archived history, never deleted) is sufficient. No versioning, snapshotting, or immutability mechanism needs to be added for Phase 3.**

Reasoning:
- `training_plan_workouts` rows are never deleted when a plan is archived (`archive_previous_active_plans()` only flips `status`) — an archived plan's week-1 schedule remains permanently queryable and linkable (Section 6.7).
- `workout_logs.training_plan_workout_id` has no expiry or invalidation tied to plan status — a link made while a plan was active continues to resolve correctly forever, even after the plan is archived, because nothing ever deletes the row it points to.
- Regenerating a new plan (Phase 2's existing "only one active plan" rule) creates an entirely new `TrainingPlan` row with its own new `training_plan_workouts` — it never mutates or overwrites the previous plan's rows, so historical planned-vs-actual comparisons for the old plan remain perfectly intact after a new plan is generated.
- A plan is never edited in place after generation (Phase 2 made `training_plan_workouts` read-only precisely to avoid this ambiguity) — so there is no "which version of the plan does this old link refer to?" question to begin with; there is exactly one, permanent, immutable version per `TrainingPlan` row.

**If explicit plan versioning is ever wanted** (e.g., "show me exactly what my plan said before I regenerated it" as a first-class timeline feature, rather than just "it's in the archived list"), that is additive on top of what exists today (the archived rows already serve as an implicit version history) and is not a Phase 3 requirement.

---

## 17. Migration Plan

**None. No schema change is proposed anywhere in this design.** Every capability described above (scheduled-date computation, completion-state derivation, planned-vs-actual comparison, linking/unlinking) is achieved by:
1. Reusing existing columns (`training_plans.start_date`, `training_plan_workouts.*`, `workout_logs.training_plan_workout_id`) exactly as they exist today.
2. Adding computed (non-persisted) fields to API response schemas (Pydantic models only — no `ALTER TABLE`).
3. Adding frontend UI to surface and act on data that already flows through the existing API contracts.

Since no migration is proposed, none of the following apply and are stated here only to explicitly close out the brief's checklist: no DB backup is needed for this design phase (none was taken or needed — no write was made to any database, confirmed in the Final Safety Verification section); no rollback strategy is needed; research row counts were not re-verified because no migration ran. **If, during actual implementation, any of the "open questions" in Section 21 resolve to a decision that does require a schema change (e.g., relaxing the one-scheduled-workout-per-day uniqueness constraint per Section 9, case 7), that would need its own follow-up design note and the full backup → copy → migrate → verify → apply procedure used in Phases 1 and 2 — not assumed here.**

---

## 18. Test Plan

**Baseline reconfirmed for this design task** (read-only — no code was changed to run this):
```
$ cd backend && python -m pytest -q
122 passed, 18 warnings in ~33s
```
This is the exact number that must still pass, unmodified, after Phase 3 implementation.

### 18.1 Backend — new/extended tests

Likely extends `test_workouts.py`, `test_plan_lifecycle.py`, `test_dashboard.py` rather than only adding new files, since the three existing files already own the relevant fixtures:

- **Linking (mostly already covered — verify still green, add only what's new):**
  - Link workout to own scheduled workout → `201`/`200`, response includes `linked_scheduled_workout` *(new field, new assertion)*
  - Reject cross-user scheduled workout ID *(already exists — regression only)*
  - Unlink via `PATCH {"training_plan_workout_id": null}` → subsequent `GET` shows no link *(new)*
  - Edit a linked workout's other fields (distance/date) without touching the link → link persists *(new)*
  - Delete a linked workout (soft delete) → scheduled workout's derived `completion_status` reverts on next `GET /api/plans/{id}/workouts` *(new)*
  - Link to a scheduled workout on the caller's own **archived** plan → allowed *(new, proves Section 6.7)*
  - Link to a scheduled workout on a **different active** plan than the currently-active one (i.e., an older, now-archived plan's week 1) still resolves ownership correctly *(new)*
- **Planned vs actual / completion state:**
  - A day with no linked log → `completion_status: "scheduled"` if in the future, `"missed"` if in the past *(new, needs a fixture that manipulates `start_date` the same way `test_dashboard.py`'s week-1-limitation test already does)*
  - A day with ≥1 linked non-deleted log → `"completed"` *(new)*
  - A rest day → `completion_status: null`, no CTA-relevant field misleadingly populated *(new)*
  - Two logs linked to the same scheduled workout → still `"completed"`, both appear in `linked_workout_logs` *(new, proves Section 9 case 1/2 don't break anything)*
- **Duplicate/standalone handling:**
  - Standalone workout (no link) → `linked_scheduled_workout: null`, unaffected by any Phase 3 change *(regression)*
  - Workout logged with a different `workout_type`/distance than the linked scheduled workout → still allowed, no validation error *(new, proves Section 9 case 4)*
- **Missing schedule / week-1 limitation:**
  - `GET /api/dashboard/summary` for a plan in week 2+ → `today_scheduled_workout: null`, `week1_detail_available: false`, no fabricated data *(regression of existing Phase 2 test, re-verify still passes with the enriched schema)*
- **Dashboard/history/plan-detail integration:** covered as response-shape assertions on the existing dashboard/plan-workouts endpoints (no new endpoint to test separately, per Section 13).

### 18.2 Security (mandatory two-user tests for every ownership-sensitive operation, per the brief)

- User A cannot link a workout to User B's scheduled workout *(already exists, re-verify)*
- User A cannot read User B's plan's scheduled workouts via `GET /api/plans/{B's id}/workouts` *(already exists, re-verify)*
- User A cannot see User B's linked workout logs leak into User A's `GET /api/plans/{own id}/workouts` response *(new — specifically tests that the new `linked_workout_logs` join is scoped correctly and can't cross users even indirectly)*

### 18.3 Regression

- All 122 existing tests must continue passing unmodified.
- The research flow (`generate → evaluate → statistics`) must be manually re-verified end-to-end after implementation, exactly as done for Phase 1 and Phase 2 (Section 15's isolation claims are necessary but a live re-check is still required before calling Phase 3 done, per the established project pattern).

### 18.4 Frontend / manual verification (once implemented)

Same three-viewport (375/768/1440px) pass already used in Phase 2, specifically exercising: dashboard completion badge + "Log this workout" CTA (both not-yet-logged and completed states), Plan Detail's per-card planned-vs-actual block, History's "Planned: ..." tag, and the unlink action — plus a manual two-account cross-user check in the live browser (mirroring Phase 1/2's practice) attempting to submit one account's `training_plan_workout_id` while authenticated as the other account via direct API call (not just through the UI, which wouldn't expose the other user's ID anyway) to confirm the `400` in a real running instance, not just in pytest.

---

## 19. UX Considerations

Consumer-facing language only — no academic/internal terminology leaks into any of the screens below (the research UI's own vocabulary, e.g. "physiological engine values," stays confined to `/research/*` exactly as today):

| Concept | Consumer-facing label |
|---|---|
| `training_plan_workout` | "Planned workout" / "Scheduled workout" |
| `workout_log` | "Actual workout" / just "Workout" in most contexts (History already just says "Workout") |
| Completion state = completed | "Completed" |
| Completion state = missed | "Not logged" (deliberately **not** "Missed" or "Failed" in the UI — avoids guilt-tripping language for something that may have been an intentional rest, injury, or schedule change; "missed" is used only as the internal/API-level state name) |
| Completion state = scheduled | "Not logged yet" |
| The linking action | "Log this workout" (create, pre-filled) / "Link to today's plan" (if linking an already-created standalone log after the fact — optional secondary flow) |
| The unlink action | "Unlink from plan" |
| Week-1 completion count | "3 of 5 planned runs logged this week" (never "adherence score" or "%") |

Terms explicitly **not** shown on any consumer screen touched by this design: VDOT engine, physiological engine values, LLM validation pipeline, traceability matrix — all remain research-only vocabulary.

---

## 20. Future Adaptive-Training Boundary

Phase 3 as designed here produces exactly the kind of read-only context a future phase could use, and this design goes no further than that:

- Completion history (Section 8), planned-vs-actual distance/pace deltas (Section 7), and RPE (already collected, unused for this purpose until now) are all **available** after Phase 3, purely as descriptive data sitting in `workout_logs`/derived queries.
- **Nothing in this design computes, stores, or surfaces an aggregate "recent workload" or "readiness" metric.** That is explicitly future-phase work, not prepared for here beyond the raw data already existing.
- If a future phase builds adaptive personalization, it must flow through the same pipeline the product audit and Phase 2 design already mandated:

```
Deterministic adherence/context calculation (reading workout_logs + training_plan_workouts)
        ↓
   Read-only context (never a write to training_plans)
        ↓
   Rules / Safety Constraints (same ≤8-10%/week, 80/20, long-run-cap engine)
        ↓
        LLM Personalization (text only, same as today)
        ↓
    Validation (same numeric/structural re-check as today)
        ↓
  User confirmation (shown, never silently applied)
        ↓
    New plan / new version
```

- **A single workout must never automatically change a training plan.** Nothing in Phase 3 wires any workout-log event to plan mutation — `POST`/`PATCH /api/workouts` never touches `training_plans` in any way, confirmed by this design proposing no such code path anywhere in Section 13.

This entire section is explicitly **out of scope for Phase 3 implementation** — it exists only to confirm the data Phase 3 produces is future-compatible with, not a commitment to build, adaptive training.

---

## 21. Known Limitations

- **Week-1-only linking** — by design (Section 5.D), not a bug; a real limitation for a user in week 2+ of an 8-week plan, who gets no plan-linking feature for 7 of their 8 weeks. This is the single biggest limitation of shipping Phase 3 without also extending the rule engine, and is worth the user's explicit awareness when approving this design.
- **No validation that a linked actual workout "matches" its scheduled workout** (Section 9, case 4) — a deliberate permissiveness, but means the completion state can be trivially "gamed" by linking an unrelated tiny workout just to flip a badge to green. Accepted as a reasonable tradeoff for an honest, non-punitive product (Section 19's "Not logged" language reasoning) rather than building type/distance-matching heuristics.
- **`scheduled_date` computation (Section 5.A) is a derived approximation**, not a stored date — if `training_plans.start_date` is ever null for a legacy row (shouldn't happen for any plan created after Phase 2, but theoretically possible if a row predates the migration and was never backfilled), the derivation cannot run and the plan must fall back to "no schedule linking available for this plan," identical to today's `week1_detail_available: false` fallback path.
- **Two runs same day, one scheduled workout**: nothing determines *which* run "counts" if a user links only one of two same-day workouts — this is left entirely to the user's own choice, with no system opinion, consistent with Section 9's "trust the user" philosophy.
- **The archived-plan-linking decision (Section 6.7)** is a genuine judgment call needing your explicit approval, not a neutral default — see Section 21's open-questions-requiring-approval note below (this section intentionally overlaps with the next one where a limitation and an open decision are the same thing).
- **No account for a plan that has fully elapsed** (today is more than 7 days past `start_date` and `total_weeks == 1`, an edge case for a 1-week plan) — behavior is identical to any week-2+ scenario (`week1_detail_available: false`), which is arguably correct but was not separately designed for; flagged for awareness.

---

## 22. Acceptance Criteria

Concrete and testable — Phase 3 is considered done when all of the following hold:

1. A user can link a newly created or existing workout log to one of their own week-1 scheduled workouts, and the link persists and is returned in both `GET /api/workouts/{id}` and `GET /api/plans/{plan_id}/workouts`.
2. **User B cannot link, read, or have a workout of theirs falsely appear as linked to any of User A's scheduled workouts** — proven by automated two-user tests (Section 18.2), mirroring the mandatory Phase 1/2 IDOR pattern.
3. A scheduled workout's `completion_status` correctly reflects `"completed"`/`"missed"`/`"scheduled"` purely from the presence/absence and timing of linked non-deleted logs — proven by fixture-based tests that manipulate `start_date` the same way `test_dashboard.py` already does for its week-1-limitation test.
4. Deleting (soft) a linked workout reverts its scheduled workout's derived completion state on the very next read, with no manual cleanup step.
5. Unlinking a workout (`PATCH` with `training_plan_workout_id: null`) succeeds and is reflected immediately in both endpoints from criterion 1.
6. Rest days never show a completion badge or "Log this workout" CTA anywhere in the UI.
7. The Dashboard, Plan Detail, and History pages render the new information correctly in all documented states (Section 10.3's 7-state matrix; Section 11/12's integration points) with no error thrown in any combination.
8. No new endpoint accepts a client-supplied `user_id`, `owner_id`, or equivalent field.
9. **No schema migration was run** — the real database's table structure is unchanged from Phase 2's `alembic upgrade head` state.
10. All 122 pre-existing tests continue to pass unmodified, plus all new Phase 3 tests pass.
11. The research flow (`/research/*`) is manually re-verified end-to-end (generate → evaluate → stats) and shows zero behavioral change from before Phase 3.
12. The Dashboard, Plan Detail, and History pages are usable without horizontal overflow at 375px, 768px, and 1440px viewport widths.
13. Nowhere in the implementation does logging, editing, or deleting a `workout_log` write to, or trigger a write to, `training_plans` or `training_plan_workouts` — verified by code review, not just by the absence of a failing test.

---

## 23. Explicitly Out-of-Scope Items

Restating the brief's list precisely, confirmed nothing in this design touches any of them:

Garmin, Strava, Apple Health, Google Fit, GPS tracking, live running tracking, social feed, followers, challenges, leaderboards, payments, subscriptions, push notifications, AI coach chat, autonomous adaptive training, automatic plan mutation, advanced analytics, race prediction, fitness score, medical recommendations, PostgreSQL migration, Redis, microservices, Kubernetes.

Additionally, specific to this design: multi-week schedule materialization (Section 5.D — flagged as a separate future design), workout-type vocabulary normalization between the rule engine and `workout_logs` (still deferred from Phase 2, not required for Phase 3's purely-descriptive comparison), any plan-versioning mechanism beyond what already exists (Section 16), and any change to `training_plan_workouts`'s uniqueness constraint (Section 9, case 7).

---

## 24. Recommended Implementation Order (for Phase 3, once approved)

1. Backend: `scheduled_date()` helper + completion-state derivation function (pure functions, unit-testable in isolation before touching any route).
2. Backend: enrich `TrainingPlanWorkoutResponse` (Section 13.2) and wire it into `GET /api/plans/{plan_id}/workouts`.
3. Backend: enrich `WorkoutLogResponse` (Section 13.1) and wire it into `GET /api/workouts`, `GET /api/workouts/{id}`, and the dashboard's `recent_activities`.
4. Backend: extend `GET /api/dashboard/summary`'s `today_scheduled_workout` construction with the same enrichment (reusing the same helper functions from step 1, not duplicating logic).
5. Backend tests (Section 18) — written alongside each piece above, not after, per the established project pattern.
6. Frontend: `WorkoutForm.jsx` gains the (hidden, pre-filled) link field + an explicit "linked to: ..." indicator and unlink control when editing.
7. Frontend: `LogWorkoutPage.jsx` reads the `?scheduled=` query param.
8. Frontend: `DashboardPage.jsx` — completion badge + CTA (Section 10).
9. Frontend: `PlanDetailConsumerPage.jsx` — completion badges + planned-vs-actual blocks (Section 12).
10. Frontend: `HistoryPage.jsx` / `WorkoutDetailPage.jsx` — "Planned: ..." tag (Section 11).
11. Manual cross-viewport + two-account verification (Section 18.4) before calling Phase 3 done.
12. Research regression re-check (generate → evaluate → stats), exactly as performed for Phase 1 and Phase 2.

---

## Implementation Readiness

- **Can Phase 3 be implemented without schema changes? Yes.** Every mechanism proposed reuses existing columns exactly as they were designed in Phase 2 (`training_plans.start_date`, `training_plan_workouts.*`, `workout_logs.training_plan_workout_id`). No `ALTER TABLE`, no new table, no new index or constraint is proposed anywhere in this document.
- **Is the existing Phase 2 architecture sufficient? Yes**, with one caveat already flagged twice (Sections 5.D and 21): it is sufficient for exactly what it was built for — week 1. A genuinely complete "plan ↔ actual" loop across an entire multi-week plan requires the separate rule-engine extension discussed in Section 5.D, which this design does not include and recommends scoping separately.
- **Decisions that must be approved before implementation begins:**
  1. **Section 6.7** — allow linking to scheduled workouts on the user's own *archived* plans, not just the active one. (Recommendation: yes, as designed.)
  2. **Section 8.3** — no `partially_completed` state; completion is a boolean "at least one log exists." (Recommendation: yes, as designed.)
  3. **Section 9** — no deduplication logic or uniqueness constraint on multiple logs linking to the same scheduled workout. (Recommendation: yes, as designed.)
  4. **Section 10.1** — whether the optional "upcoming scheduled workout" dashboard addition is worth including in this phase, or should be deferred as a pure nice-to-have. (Recommendation: include it — it's a zero-schema, low-cost addition reusing data already fetched.)
  5. **Section 5.D** — explicit confirmation that multi-week schedule materialization is *not* part of this phase and will be scoped as its own future design document rather than silently expected to "just happen" inside Phase 3 implementation.
  6. **Section 8.5** — whether the week-1 completion count ("3 of 5 planned runs logged") is included in this phase's Plan Detail page, or deferred as pure polish.
- **Risks that remain, even after approval:**
  - The permissiveness in Section 9/21 (no match validation between planned and actual) could, in principle, be used to make the completion badge misleading (link a 1km jog to a 15km long-run slot). This is an accepted product tradeoff, not an oversight, but worth naming as a risk rather than silently accepting it.
  - The week-1-only ceiling (Section 21) may produce a confusing product experience for users deep into a longer plan, who get no plan-linking feature at all past week 1 — this risk is inherent to deferring the rule-engine extension and should be weighed against implementing Phase 3 now vs. bundling it with that larger engine change later.
  - Nothing about this design has been executed against real data yet (no code was written) — the derivation logic in Section 5.A/8 should be unit-tested thoroughly against real edge cases (e.g., a plan whose `start_date` falls on a Sunday, so `day_of_week="Monday"` maps to a date *after* several other days in the same week) before being trusted in the dashboard.

---

## Final Safety Verification

Performed immediately before finishing this document:

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
?? PHASE_2_REPORT.md
?? PHASE_3_DESIGN.md
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

$ git diff --stat -- backend/ frontend/
 backend/.env.example                           |  1 +
 backend/app/config.py                          |  3 +
 backend/app/main.py                            |  4 +-
 backend/app/models.py                          | 91 +++++++++++++++++++++-
 backend/app/routes/plan_routes.py              | 85 +++++++++++++++++++++-
 backend/tests/factories.py                     | 12 ++++
 frontend/src/App.jsx                           | 73 +++++----------------
 frontend/src/api.js                            | 44 +++++++++++
 frontend/src/layouts/ConsumerLayout.jsx        | 47 ++++++++-----
 frontend/src/pages/PhaseTwoPlaceholderPage.jsx | 23 -------
 10 files changed, 284 insertions(+), 99 deletions(-)

This diff-stat is byte-for-byte identical to the one recorded in PHASE_2_REPORT.md's
Section 14 (from the still-uncommitted Phase 2 implementation) -- proving zero new
lines changed in any backend or frontend file during this Phase 3 design task. The
only new filesystem entries are this document and the already-existing PHASE_2_REPORT.md.

$ git log --oneline
6777472 Add Phase 2 technical design document
717faca Document Phase 1 authentication architecture and final report
8ffb72c Phase 1: multi-user authentication, authorization, and security foundation
732f4b3 Initial commit: baseline research prototype before Phase 1
```

- **No application code was changed.** Every backend/frontend file referenced above (Section 2) was only *read* (via the `Read`/`Grep` tools), never edited, during this design task.
- **No database was changed.** No write, migration, or schema-altering command was executed; the only database interaction during this task was the earlier, already-completed Phase 2 verification query, not repeated here.
- **No migration was executed.** No `alembic` command was run during this task.
- **No dependency was installed.** No `pip install`/`npm install` command was run during this task.
- **Only one pytest run was performed** (`python -m pytest -q`, Section 18), purely to re-confirm the current 122-test baseline — a read-only verification, not a code change.

No unexpected modification occurred. **STOP — awaiting your review and approval before any Phase 3 implementation begins.**

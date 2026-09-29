# Product Readiness Audit — Running Training Platform

**Date:** 2026-09-29
**Scope:** Full audit of the existing S2 research prototype against the goal of evolving it into a public-facing AI running training product. This is an **audit and roadmap only** — no implementation was performed. Every recommendation below is a proposal awaiting approval.

**Method:** Full source review of `backend/` and `frontend/`, live test runs of the pytest suite, and hands-on browser testing of every page at mobile (375–390px), tablet (768px), and desktop (1024–1440px) viewports, including the full Create → Result → Evaluate → Stats flow.

---

## 1. Audit of the Existing Application

### 1.A Visual / UI

| Dimension | Assessment |
|---|---|
| Professional appearance | Good. Consistent Tailwind slate/indigo palette, shared `Button`/`Badge`/`StatusMessage` primitives now exist ([frontend/src/components/ui](frontend/src/components/ui)). |
| Consistency | Good post-polish. Cards, shadows, radii, and spacing follow one system. |
| Typography | Mostly consistent; several `text-[10px]`/`text-[11px]` labels (badges, hints) are borderline small for a consumer audience that includes older/casual users — fine for a research tool, worth revisiting for consumer. |
| Spacing / Colors / Hierarchy | Consistent, primary actions clearly styled. |
| Mobile / Tablet / Desktop UX | Verified overflow-free at 375, 390, 768, 1024, 1280, 1440px. Mobile nav (hamburger drawer) works correctly. |
| Accessibility | **Partial.** `aria-label`/`aria-pressed`/focus-visible rings exist on some components (Evaluation Likert buttons, mobile nav toggle), but there has been no systematic pass: no contrast audit, no screen-reader pass, no heading-hierarchy audit, no keyboard-only navigation test of `<select>`/range inputs. |
| Empty / Loading / Error states | Empty and loading states are good (dedicated components). **Error states have one real gap:** [frontend/src/pages/CreatePlanPage.jsx](frontend/src/pages/CreatePlanPage.jsx) and [frontend/src/api.js](frontend/src/api.js) surface a **raw FastAPI 422 validation payload** (a stringified JSON array of Pydantic error objects) directly in the UI when validation fails server-side. This is a genuine "research prototype" smell — a consumer must never see `[{"type":"string_pattern_mismatch",...}]`. |

### 1.B Product UX

Evaluated by actually generating a plan, viewing it as both Rule-Based and AI-Personalized, running the evaluation flow, and checking the stats page — end to end, on a phone-sized viewport.

- **Onboarding / first-time experience:** None exists. There is no signup, no "what is this app" moment beyond a homepage that opens with a "BINUS University • S2 IT Research Prototype" badge and an "S2 PROTOTYPE" tag in the header. A general user lands directly in academic framing.
- **Navigation:** Now mobile-safe (fixed this session), but the entire app is a single-page React state machine with **no routing** (no react-router, no URLs per page). Refreshing the browser loses the current plan; a plan cannot be bookmarked, shared, or resumed after closing the tab, since it exists only in React state, not persisted per identity. This is a structural gap for any product with return visits.
- **Create Plan flow:** Genuinely good — clear grouped form, live pace preview, sensible defaults. This is a strong foundation to keep.
- **Understanding AI plans:** The explainability matrix is a real differentiator (most consumer running apps don't explain their AI), but the copy is academic ("Traceability Matrix", "physiological engine values", "VDOT Interpretation"). Good bones, needs a copy pass for a general audience.
- **Workout detail:** `WorkoutCard` is already consumer-presentable.
- **Evaluation flow:** 100% research-only. A 1–5 Likert questionnaire "for the S2 thesis paper" and an explicit Rule-Based-vs-AI comparison toggle are not things a general running app user should ever be asked to do by default.
- **Progress / history:** **Does not exist.** No workout logging, no calendar, no completed-vs-planned view. This is the single largest gap relative to the stated product vision.
- **User profile:** Does not exist as a persistent, identity-linked concept. "Profile" today is a one-time form submitted anonymously per plan generation — nothing survives between visits because there is no login.
- **Retention:** Currently zero. Every visit starts from zero because nothing is tied to a returning identity.

**Verdict:** The current app is a well-crafted **stateless, single-session research demo**. It is not close to a retainable consumer product structurally (no accounts, no history, no persistence tied to identity, no routing) — but the parts that exist (rule engine, AI validation, explainability, form UX) are a genuinely solid foundation to build on, not a throwaway.

---

## 2. Product Positioning

1. **Best-fit target user:** A self-coached recreational-to-intermediate runner training toward a specific race (5K/10K/Half) who wants structured, explainable guidance without hiring a human coach — a "data-curious, self-directed runner," not a competitive elite (too basic) and not a complete non-goal-oriented beginner (the flow requires a PB and a target time).
2. **Core value proposition:** *"A training plan you can actually trust, because you can see exactly why it's built that way"* — physiologically-grounded rules plus AI personalization that is never allowed to override the physiology, as opposed to either a black-box AI plan or a generic static PDF plan.
3. **What brings users back:** Only logging + seeing progress + a plan that adapts to what they actually did would create a return habit. **Nothing today does this** — this is the product's central missing piece.
4. **Too research-oriented today:** the Likert evaluation flow, "S2 Prototype"/BINUS branding, the forced Rule-Based-vs-AI comparison UI, the Evaluation Stats page, academic terminology throughout.
5. **Needed before public launch (must-have):** accounts + ownership, at minimum manual workout logging + history, a dashboard, hiding research-only flows from the default consumer path, rate limiting on plan generation (cost control), and the security/backup/deployment basics in the checklist (Section 16).
6. **Should be deferred:** GPS/live tracking, Garmin/Strava/Apple Health/Google Fit integrations, social features (followers, feed, leaderboards, challenges), payments/subscriptions, multi-language.

---

## 3. Authentication & User Accounts — Proposed Architecture (not implemented)

**Password storage:** bcrypt or argon2 hash (via `passlib`) — never reversible encryption, never plaintext.

**Session strategy — recommendation: server-side opaque session token in an httpOnly, Secure, SameSite=Lax cookie**, backed by a `sessions` table, rather than hand-rolled JWT. Reasoning: this is a single FastAPI instance at MVP scale; a DB-backed session can be instantly revoked on logout/password-change (JWT access tokens generally can't be revoked before expiry without an extra denylist — which is the same complexity as just using a session table). Revisit JWT only if/when the API needs to be stateless across multiple independently-scaled instances.

**Password reset:** opaque random token, **stored hashed**, short expiry (~30 min), single-use, emailed as a link. Requires an email-sending provider (e.g. Resend/SES/SendGrid) — a new external dependency to select in Phase 1, not before.

**Logout:** must invalidate the server-side session record, not just clear the client cookie.

**New tables (additive):**
- `users` (id, email UNIQUE, password_hash, display_name, is_active, email_verified_at NULL, created_at, updated_at)
- `sessions` (id, user_id FK, token_hash, expires_at, created_at, revoked_at NULL, user_agent/ip optional)
- `password_reset_tokens` (id, user_id FK, token_hash, expires_at, used_at NULL)

**Ownership enforcement:** every user-owned resource query filtered by `WHERE user_id = current_user.id` via a reusable FastAPI dependency (`get_current_user`). The client must never be able to supply `user_id` in a request body — it always comes from the authenticated session.

**Critical design decision to preserve research integrity:** keep the existing anonymous research schema (`runner_profiles`, `training_plans`, `plan_evaluations`) **as-is and unlinked to `users`**. A logged-in consumer user is a new, separate identity concept. If a logged-in user chooses to participate in the thesis research, that should be an **explicit, separate opt-in** that creates an anonymous research record — not an automatic link from `user_id` to research data. This is what Section 17 expands on.

---

## 4. Security Audit

No destructive testing was performed — this is a static/behavioral review of the current code.

| Area | Finding | Severity |
|---|---|---|
| Ownership / IDOR | `GET /api/plans/{plan_id}` has **no ownership check today** — anyone who has or guesses a plan's UUID can view it. Currently low-impact (no PII in plan data), but becomes **CRITICAL** the moment any personal data attaches. Must be fixed in the same phase accounts are introduced — every existing resource route needs an ownership check added, not bolted on later. | **HIGH (today) → CRITICAL if accounts ship without this fix** |
| Rate limiting / cost abuse | **None exists anywhere.** `/api/plans/generate` calls a billed LLM API with zero throttling. Any public deployment with a real API key attached is exposed to cost-abuse and basic DoS today, before any accounts even exist. | **HIGH** |
| CORS | Currently hardcoded to `http://localhost:5173` / `http://127.0.0.1:5173` ([backend/app/main.py](backend/app/main.py)) — correct for dev, but must become environment-driven for the real production domain before deploy, or it will either break or get "temporarily" reopened to `*` under deploy pressure. | MEDIUM (dev-safe, deploy-blocking if forgotten) |
| Prompt injection (numeric surface) | `injury_limitations` and other free-text profile fields are interpolated into the LLM prompt unsanitized. **Well-mitigated already**: [backend/app/ai/validator.py](backend/app/ai/validator.py) independently re-checks every numeric/structural field (distance, pace, workout count, weekly mileage, rest days) against the deterministic rule-based baseline and falls back to the offline synthesizer on any mismatch — a real defense-in-depth already in place. | LOW (numeric surface) |
| Prompt injection (textual surface) | The *textual* AI fields (`coach_overview`, `warmup_cooldown`, `workout_execution`, `personalized_insights`, `ai_personalization_summary`) are **not** content-validated. A crafted injury/preference string could coax the LLM into producing off-topic, unsafe-sounding, or instruction-injected text that is shown verbatim. | MEDIUM |
| CSRF | Not currently relevant (no cookies/sessions exist). **Becomes a requirement** the moment cookie-based sessions ship (Section 3) — SameSite=Lax/Strict plus a token check on state-changing requests. | N/A today → MEDIUM once auth ships |
| Mass assignment | Not currently exploitable — Pydantic schemas are explicit allow-lists. Must remain disciplined once `user_id`/ownership fields are added (never accept `user_id` from a client body). | LOW (must stay disciplined) |
| SQL injection | Not applicable — 100% SQLAlchemy ORM, no raw SQL anywhere in the codebase. | LOW/None |
| XSS | Not applicable today — React escapes all rendered text by default; no `dangerouslySetInnerHTML` anywhere in the codebase. Re-check if markdown/rich-text rendering of AI or user content is ever added. | LOW |
| API key / secret exposure | Correct architecture: Gemini/OpenAI keys are read server-side only via `app/config.py`, never sent to the frontend; the frontend only calls same-origin `/api/*`. | LOW |
| Version control hygiene | **The project is not a git repository at all**, and there is **no root `.gitignore`**. This means there is currently zero risk of a historical leak, but also zero protection queued up for the first commit. Before this project is ever pushed to a remote (GitHub etc.), a `.gitignore` covering `.env`, `*.db`, `__pycache__`, `node_modules`, and `dist` must be created **before** the first `git add`, or the very first commit could capture `running_research.db` (accumulated data) or a future real `.env`. | MEDIUM (trivial to fix, easy to forget, high blast radius if missed) |
| Error information leakage | No explicit `debug=False`/production error-handler configuration observed for FastAPI/uvicorn. Needs an explicit check before deploy. | MEDIUM |

---

## 5. Privacy & Personal Data

**Currently stored (research path, unchanged, anonymous by design):** age, gender, experience level, 5K/10K PB, target race/time, weekly mileage, training days, an optional free-text injury/limitation note, generated plan JSON, Likert scores, optional free-text comments. No email, no name, no account — this anonymity is a deliberate, already-documented research design choice (see [README.md § 7](README.md)) and should not be disturbed.

**New categories once consumer accounts exist:**

| Category | Classification | Notes |
|---|---|---|
| Email, password hash, display name | **Required** | Needed for login/reset. Display name can be a pseudonym — don't require a real legal name. |
| Runner profile (age, experience, PBs, target race, mileage, days) | **Required** | Already collected today; needed to generate any plan. |
| Injury / limitation notes | **Optional**, health-adjacent | Should be clearly marked optional with an explanation of why it's asked. |
| Workout logs (distance, duration, computed pace, RPE, notes) | **Optional to fill in detail, but core to the tracking feature** | This is the whole point of the tracking feature — but individual fields (HR, cadence, elevation) stay optional per the user's own request. |
| Heart rate, cadence, elevation | **Optional** | As specified — never required. |
| Precise GPS routes | **Should NOT be stored** at this stage | Out of scope per Section 10 ("Later"); don't collect data you have no current feature for. |
| Payment info | **Not applicable** | No payment feature exists or is planned in this roadmap. |

**Privacy architecture recommendations:**
- Keep research data and consumer-account data **architecturally separate** (no `user_id` on `plan_evaluations`/research tables). Linking a logged-in identity into the research dataset requires a **separate, explicit, opt-in consent flow** — never an automatic join.
- Practice data minimization: don't add fields "in case they're useful later."
- Support account deletion with cascading (or scheduled) deletion of the user's own profile/plans/workout logs — never delete the separate, anonymous research records.

**Compliance note (not legal advice):** If this project ever references Indonesia's UU PDP or GDPR, that reference is an **architectural design consideration only** — e.g., data minimization, purpose limitation, deletion capability — and is **not a substitute for actual legal review**. Before storing real user PII in production, get an actual privacy/legal consultation; nothing in this document should be read as a compliance claim.

---

## 6. Running Activity Tracking — Design Audit

Proposed minimal `workout_logs` shape (fields exactly as requested, nothing extra):

```
workout_logs
  id, user_id (FK)
  date
  distance_km
  duration_seconds
  avg_heart_rate      (nullable)
  max_heart_rate      (nullable)
  cadence_spm         (nullable)
  elevation_gain_m    (nullable)
  workout_type
  rpe                 (nullable)
  notes               (nullable)
  training_plan_workout_id (nullable FK — Phase 3, links a log to a scheduled workout)
  created_at, updated_at, deleted_at (soft delete)
```

**Pace is never entered by the user** — `avg_pace_sec_per_km = duration_seconds / distance_km`, computed server-side (and mirrored client-side for a live preview, reusing the exact UX pattern already built for target-pace preview in [CreatePlanPage.jsx](frontend/src/pages/CreatePlanPage.jsx)). It is not necessary to persist the computed pace as its own column at this scale — deriving it on read avoids drift; revisit only if a query pattern later needs to filter/sort by pace at a scale where computing it per-row becomes a real cost.

---

## 7. Training History — Concept

A date-grouped list (reusing the existing `Badge`/card visual language from `WorkoutCard`): date, workout-type badge, distance, duration, pace, RPE per row, expandable to a detail view. Actions: view, edit, delete (soft delete, with confirmation). Filters: date range, workout type. Paginate — never load the full history at once. Every list/detail/edit/delete query is scoped to `WHERE user_id = current_user.id` server-side, re-checked on every mutating request regardless of what the client claims.

---

## 8. Dashboard — Concept (not implemented)

Data actually needed, nothing invented:
- Display name (from `users`)
- This week's aggregate: total distance, run count, computed from `workout_logs` for the current week — no fabricated "training load" metric without a defined formula
- Today's scheduled workout: requires the active plan to know "today" relative to a real start date — **today's plans don't store a start date** (only `created_at` and a duration-in-weeks), so a "week 4 of 8, here's today's workout" view cannot be built reliably yet. This is a concrete, small gap to close in Phase 3.
- Quick "Log Workout" call to action
- Recent activities (last 3–5 logs)
- Plan progress bar (needs the start-date fix above)

---

## 9. Training Plan ↔ Activity Integration

```
Training Plan → Today's Scheduled Workout → User Runs → Log Actual Workout
→ Compare Planned vs Actual → Training History → Future Personalization
```

**Gap found:** the current rule engine ([backend/app/rules/generator.py](backend/app/rules/generator.py)) only produces a fully detailed **Week 1** schedule; weeks 2+ are summarized as a single target-mileage number per week (`progression_schedule`), not day-by-day workouts. A "Today's Workout" dashboard needs every week's workouts, not just week 1 — this requires extending the generator (Phase 3), and is a meaningful but contained engine change, not a rewrite.

**Planned-vs-actual:** a `workout_log` optionally references a `training_plan_workout_id`; the UI shows simple, descriptive deltas (planned vs actual distance/pace) — purely informational.

**Future personalization — explicit safety rule:** adherence %, recent RPE, and recent pace trend should be computed **deterministically** (same style as the existing rule engine) and fed as *additional read-only context* into the same Rules → LLM → Validation pipeline for the **next plan regeneration** — never as an automatic, silent mutation triggered by a single workout. A single missed run or one RPE-9 session must never itself cause the AI to rewrite the plan. Any plan adjustment must (a) pass through the same deterministic safety bounds already governing weekly progression, and (b) be shown to the user for confirmation before taking effect.

---

## 10. Feature Scope vs. Garmin/Strava

| Tier | Features | Why |
|---|---|---|
| **Must Have** | Account, profile, training plan, manual workout logging, history, dashboard, basic stats | This is the entire core product loop (plan → follow → log → see progress). Nothing else matters if this loop doesn't work. |
| **Should Have** | Progress charts, personal records, weekly/monthly mileage, planned-vs-actual, RPE tracking | Meaningfully increases perceived value and retention at **low-to-medium** implementation cost — mostly aggregation queries and simple charts over data the Must-Have tier already collects. No new external integrations required. |
| **Later** | Garmin/Strava/Apple Health/Google Fit sync, GPS/live tracking, social feed/followers/challenges/leaderboards | Technical reason: each external sync is its own OAuth + webhook/polling integration with a rate-limited third party; live GPS tracking fundamentally needs a mobile app with background location, which a web app can't do well. Product reason: none of this is required to validate the core "trustworthy AI plan + logging" value proposition, and social features add moderation/privacy complexity disproportionate to an early-stage product. |

---

## 11. Proposed Production Data Model

```
users                     -- auth identity only
user_profiles             -- runner-specific data (1:1 with users)
training_plans            -- extends current TrainingPlan; gains user_id
training_plan_workouts    -- NEW, normalized per-workout rows (Phase 3)
workout_logs              -- NEW, user-owned activity records
evaluations               -- UNCHANGED, stays anonymous/research-only
user_preferences          -- units, notification opt-in, etc.
sessions                  -- auth session tokens
password_reset_tokens     -- auth reset tokens
```

Deliberately **not** proposing a separate `workout_metrics` table — per the instruction not to add tables just to look "enterprise," simple metrics (HR, cadence, elevation) fold directly into `workout_logs` unless a real query pattern later demands otherwise.

- **Keys/indexes:** every FK indexed; `users.email` unique; composite index on `workout_logs(user_id, date)` for history queries; index on `training_plans(user_id, created_at)`.
- **Ownership:** every user-facing table above (except `evaluations`) carries a `user_id` FK and is queried through the same ownership-check pattern.
- **Soft delete:** `deleted_at` nullable timestamp on `training_plans` and `workout_logs` so user-initiated deletes are recoverable for a grace period; hard-delete on a schedule or on explicit account deletion.
- **Cascade:** deleting a `user` cascades (or soft-deletes) their `user_profiles`/`training_plans`/`workout_logs`/`preferences`. It must **never** cascade into `evaluations`, which has no link to `users` by design.

**Migration strategy:** every Phase 1 change is **additive** — new tables (`users`, `sessions`, `password_reset_tokens`) plus a **nullable** `user_id` column added to existing tables, so existing anonymous research rows remain valid and untouched. Recommend adopting **Alembic** starting Phase 1 instead of continuing to rely on `Base.metadata.create_all` (which can create tables but can't alter existing ones) — this becomes a hard requirement the moment the schema needs to evolve rather than just be created fresh. **No destructive migration is proposed or should be run** against the current database.

---

## 12. Proposed API Structure (not implemented)

| Group | Endpoint (indicative) | Auth | Ownership check |
|---|---|---|---|
| Auth | `POST /auth/register`, `/login`, `/logout`, `/forgot-password`, `/reset-password` | Public (register/login/forgot), session-required (logout) | N/A |
| Profile | `GET/PATCH /users/me` | Required | Implicit (always "me") |
| Plans | `POST /plans`, `GET /plans` (mine), `GET/DELETE /plans/{id}` | Required | **Every plan route gains an ownership check** (today's biggest concrete gap) |
| Workouts | `POST/GET /workouts`, `GET/PATCH/DELETE /workouts/{id}` | Required | Ownership check on every op |
| Dashboard | `GET /dashboard/summary` | Required | Implicit (current user's own aggregates) |
| Evaluations | `POST /evaluations`, `GET /evaluations/stats` | Unchanged (research flow decision to be made explicitly in Phase 1: stays anonymous-capable, or gains an optional link for consenting logged-in participants) | N/A (research design) |

Full request/response schemas are implementation detail for the relevant phase, not this audit.

---

## 13. AI Architecture — Extension, Not Replacement

Current, and to be preserved exactly:

```
Runner Profile → Rule-Based Baseline → LLM Personalization → Validation → AI-Personalized Plan
```

Proposed extension for adaptive personalization:

```
Runner Profile + (adherence %, recent RPE avg, recent pace trend — computed deterministically)
        ↓
   Rule Engine (same safety bounds: ≤8-10%/week, 80/20, long-run cap)
        ↓
        LLM (personalizes text; still cannot set numbers)
        ↓
    Validator (same numeric/structural checks as today)
        ↓
     Safe, Updated Plan (shown to user for confirmation, never silently applied)
```

The LLM remains a **personalization layer**, never the source of physiological truth — this principle is already correctly implemented today and must not be weakened as adaptive features are added.

---

## 14. Cost & Abuse Prevention

- **Today:** zero rate limiting exists anywhere. `/api/plans/generate` calls a billed LLM with no throttle — this is already a real cost/DoS exposure the moment a real API key is attached to any publicly reachable instance, independent of whether accounts exist yet.
- **Recommend:** per-user (once authenticated) and per-IP (for any public/anonymous surface) rate limits on plan generation before any public, key-enabled deployment.
- **Existing strength to keep:** the deterministic offline fallback ([generate_offline_ai_plan](backend/app/ai/llm_service.py)) already guarantees the app keeps working even under total LLM outage or quota exhaustion — this is a genuinely good cost-control lever already built. Consider deliberately using it as a **free/anonymous tier** (deterministic-only) while reserving real LLM calls for authenticated or paid usage later — an option to design, not a decision to make now.
- **Caching:** low priority at MVP scale, but a short-TTL cache keyed on a normalized-profile hash would blunt accidental duplicate submissions.

---

## 15. Scalability

**MVP (recommended, do not over-build):**
- SQLite is **fine** for MVP — current write volume is low, and it's already proven working with zero ops overhead.
- Single FastAPI (uvicorn/gunicorn) container + a statically built React app behind one reverse proxy (nginx or a platform's built-in one) — no Kubernetes, no microservices.
- No background job queue needed yet; FastAPI's built-in `BackgroundTasks` covers something like "send a password reset email" without new infrastructure.
- Logging: current `logging`-module warnings are fine for MVP; before public launch, route logs to a persistent destination and keep enforcing "never log secrets or raw user PII" (already the discipline applied to the LLM fallback logging this session).
- Monitoring: the existing `/api/health` endpoint plus basic uptime checks and the LLM provider's own cost dashboard are sufficient at MVP scale.

**Future Scale (trigger-based, not scheduled):**
- Move to PostgreSQL when concurrent writes become meaningful (dozens of simultaneously-active writing users), or when horizontal scaling of the API becomes necessary.
- Add a real task queue (e.g., Celery/RQ + Redis) only once background work exists that truly can't wait on a request/response cycle.
- Add a dedicated error-tracking/observability service (e.g., Sentry-style) once there are real users whose failures you can't just reproduce locally.

---

## 16. Production Readiness Checklist

| Item | Current Status | Risk | Recommendation | Priority |
|---|---|---|---|---|
| UX | PARTIAL | MEDIUM | Build the core consumer loop (logging/history/dashboard) | P1 |
| Accessibility | PARTIAL | LOW–MEDIUM | Dedicated contrast/screen-reader/keyboard-nav pass | P2 |
| Authentication | NOT READY | CRITICAL | Implement per Section 3 | P0 |
| Authorization | NOT READY | CRITICAL | Ownership checks on every resource route, same phase as auth | P0 |
| Security | PARTIAL | HIGH | Rate limiting, CSRF (once cookies exist), `.gitignore` before first commit | P0/P1 |
| Privacy | PARTIAL | MEDIUM | Draft a privacy policy + explicit consent flow before storing real PII | P1 |
| Database | PARTIAL | MEDIUM | Additive user/ownership tables + adopt Alembic | P1 |
| API | PARTIAL | MEDIUM | Auth middleware, ownership filters, pagination on list endpoints | P1 |
| AI | PARTIAL (strong foundation) | MEDIUM | Extend textual-output validation; extend engine to multi-week workouts | P1/P2 |
| Performance | READY for MVP scale | LOW | Monitor as usage grows | P3 |
| Error handling | PARTIAL | LOW–MEDIUM | Stop surfacing raw 422 payloads to end users | P2 |
| Logging | PARTIAL | LOW | Persistent log destination, keep the "no secrets/PII" discipline | P2/P3 |
| Monitoring | NOT READY | MEDIUM | Wire up uptime + basic error tracking before public launch | P1 |
| Backup | NOT READY | HIGH (once real user data exists) | Automated DB backup/export process | P1 |
| Deployment | NOT READY | HIGH | Dockerfile/deploy config/CI, explicit production CORS + debug=False | P1 |
| Cost control | NOT READY | HIGH | Rate limiting before any public deployment with a real LLM key | P0/P1 |

---

## 17. Research Compatibility — Explicit Separation

**Research-only (must remain, must not require a consumer login):**
Rule-Based Baseline generation, AI-Personalized generation, the Rule-Based-vs-AI comparison toggle on Plan Result, the Evaluation Likert flow, the Evaluation Stats page, the anonymous `plan_evaluations` design, and the underlying `validate_ai_plan` / rule-engine logic they depend on.

**Dual-purpose (keep, but adapt tone per context):** the explainability matrix is genuinely valuable for both the thesis *and* consumer trust — recommend keeping the mechanism, but writing lighter, non-academic copy when shown in a consumer context.

**Consumer-only (new, additive):** accounts, dashboard, workout logging/history, progress analytics, a persistent user profile tied to identity, settings/preferences.

**Recommendation:** gate or route-segment the research flow (e.g., reachable via a distinct path or an explicit "Research Participation" opt-in) so general users never default into the Likert survey, while research participants — registered or not — can still reach it. **Do not remove or weaken** the rule engine, validator, or evaluation statistics to make room for consumer features; build the consumer product around them.

---

## 18. Recommended Development Roadmap

Complexity is qualitative (Low/Medium/High) only — no time estimates, per your instruction.

### Phase 0 — Current State
Existing research prototype: rule-based engine, LLM personalization + validation, anonymous evaluation system, polished but account-less UI.

### Phase 1 — Authentication + User Ownership
- **Objective:** introduce accounts without disturbing research anonymity.
- **Features:** register/login/logout/password reset, a consumer user profile (separate from the anonymous research runner-profile), ownership checks retrofitted onto every existing plan endpoint.
- **Files/modules affected:** new `app/auth/` (models, routes, hashing/session utils), `app/models.py`, `app/database.py` (Alembic setup), `app/main.py` (auth router + dependency); frontend gains a router library, auth context, login/register pages.
- **Database changes:** new `users`, `sessions`, `password_reset_tokens`; additive nullable `user_id` on `training_plans`.
- **API changes:** new `/auth/*`; `/plans/*` gain an auth dependency + ownership filter.
- **Security considerations:** password hashing, session invalidation on logout, rate-limited login attempts, the IDOR fix on plan retrieval (Section 4).
- **Complexity:** Medium–High (foundational; touches most of the backend).

### Phase 2 — Dashboard + Workout Logging + History
- **Objective:** deliver the core "record your running" loop.
- **Features:** Log Workout form (computed pace), History list with filters/edit/delete, a basic Dashboard (this week's totals, recent activities).
- **Files/modules:** new `app/routes/workout_routes.py`, `WorkoutLog` model; frontend Dashboard/LogWorkout/History pages + routing.
- **Database changes:** new `workout_logs` (user-owned, soft-delete).
- **API changes:** new `/workouts` CRUD.
- **Security considerations:** ownership checks on every CRUD operation, reusing the Phase 1 pattern.
- **Complexity:** Medium.

### Phase 3 — Training Plan ↔ Actual Workout Integration
- **Objective:** connect the plan to what actually happened.
- **Features:** extend the rule engine to generate full multi-week workouts (not just week 1), "Today's Workout" on the dashboard (requires a stored plan start date), logging against a scheduled workout, planned-vs-actual comparison.
- **Files/modules:** `app/rules/generator.py` extended, new `training_plan_workouts` table, dashboard wiring on the frontend.
- **Database changes:** new `training_plan_workouts`; `workout_logs` gains an optional FK to it; `training_plans` gains a `start_date`.
- **API changes:** `/plans/{id}/workouts`.
- **Security considerations:** same ownership pattern; care not to disturb the existing JSON-based plan storage that research evaluations depend on.
- **Complexity:** High (the biggest data-model shift in the roadmap).

### Phase 4 — Progress Analytics
- **Objective:** weekly/monthly mileage, personal records, adherence %, RPE trend.
- **Features:** aggregation endpoints, chart UI (a charting library becomes a new frontend dependency).
- **Files/modules:** new consumer-facing `/stats` endpoints (kept distinct from the research `/evaluations/stats`), new chart components.
- **Database changes:** primarily read/aggregation; consider a cached weekly-summary table only if performance later demands it.
- **Security considerations:** standard ownership scoping.
- **Complexity:** Medium.

### Phase 5 — Security Hardening + Production Readiness
- **Objective:** close every P0/P1 item in Section 16 before any public launch.
- **Features:** rate limiting, CSRF protection (now that cookies exist), automated backups, monitoring/error tracking, a deployment pipeline (Docker/CI), Alembic migrations finalized, a privacy policy + consent flow, an accessibility pass.
- **Complexity:** Medium–High (broad, not deep).

### Phase 6 — External Integrations
- **Objective:** Garmin/Strava/Apple Health/Google Fit import, exploratory GPS tracking.
- **Complexity:** High (each integration is effectively its own project).

---

## Summary of the Most Important Findings

1. **The AI/rule-engine architecture is a genuine strength — preserve it exactly.** Deterministic physiological constraints, LLM personalization, and independent output validation are already correctly separated.
2. **The single biggest product gap is the complete absence of accounts, history, and a dashboard** — without these, there is no retention mechanism at all.
3. **The single biggest current security gap is missing ownership checks** (`GET /api/plans/{id}` today trusts the UUID alone) and **the complete absence of rate limiting** on a route that calls a billed LLM API.
4. **The project has no version control yet** — a `.gitignore` must exist before the first commit, or a first push risks leaking the accumulated research database.
5. **Research integrity is fully preservable** — every consumer feature proposed above is additive and separable from the existing anonymous research schema and evaluation flow; nothing in this roadmap requires removing or weakening them.

---

**No implementation has been performed.** This document is the deliverable for the audit stage. Awaiting your review and approval before starting Phase 1.

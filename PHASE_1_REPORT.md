# Phase 1 Final Report — Authentication, Authorization & Security Foundation

**Date:** 2026-09-29
**Scope:** Transform the stateless S2 research prototype into a multi-user application foundation (accounts, sessions, ownership, rate limiting, CSRF, friendly errors, routing) **without changing any research logic**. Phase 2+ (dashboard, workout logging, analytics) was explicitly not implemented, per instruction.

---

## 1. Files Changed

### Modified
- `backend/.env.example` — documented every new env var (no secrets)
- `backend/app/config.py` — environment, session, email, and rate-limit settings
- `backend/app/main.py` — rate limiter, CSRF middleware, exception handlers, CORS from env, new routers mounted
- `backend/app/models.py` — added `User`, `UserProfile`, `Session`, `PasswordResetToken`; added nullable `TrainingPlan.user_id`
- `backend/app/routes/plan_routes.py` — ownership enforcement + rate limiting on plan generation/retrieval/listing
- `backend/requirements.txt` — added `alembic`, `argon2-cffi`, `slowapi`, `email-validator`
- `backend/tests/conftest.py` — rate-limiter test isolation, CSRF-safe default test client
- `backend/tests/factories.py` — auth test helpers
- `frontend/package.json` / `package-lock.json` — added `react-router-dom`
- `frontend/src/App.jsx` — rewritten as the top-level router (was the whole research app; the research app moved to `ResearchApp.jsx`)
- `frontend/src/api.js` — `credentials: 'include'` everywhere, new auth/profile API functions, cleaner error extraction
- `frontend/src/main.jsx` — wrapped in `BrowserRouter`
- `README.md` — new Section 8 (Authentication Architecture & Security), migration step added to Quick Start, schema section updated

### New
**Backend:**
- `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`
- `backend/alembic/versions/0001_baseline_research_schema.py`
- `backend/alembic/versions/0002_add_auth_and_ownership.py`
- `backend/app/auth/__init__.py`, `security.py`, `schemas.py`, `dependencies.py`, `email_service.py`, `routes.py`
- `backend/app/core/__init__.py`, `rate_limit.py`, `csrf.py`, `errors.py`
- `backend/app/routes/profile_routes.py`
- `backend/tests/test_auth.py`, `test_authorization.py`, `test_password_reset.py`, `test_rate_limiting.py`, `test_csrf.py`, `test_profile.py`

**Frontend:**
- `frontend/src/ResearchApp.jsx` (the original, unmodified research app, now mounted at `/research/*`)
- `frontend/src/context/AuthContext.jsx`
- `frontend/src/components/ProtectedRoute.jsx`
- `frontend/src/layouts/ConsumerLayout.jsx`
- `frontend/src/pages/LandingPage.jsx`, `ProfilePage.jsx`, `PhaseTwoPlaceholderPage.jsx`
- `frontend/src/pages/auth/LoginPage.jsx`, `RegisterPage.jsx`, `ForgotPasswordPage.jsx`, `ResetPasswordPage.jsx`

**Repository-level (Section 0/1):**
- `.gitignore` (new, root)
- `PRODUCT_READINESS_AUDIT.md`, `PHASE_1_REPORT.md` (this file)
- Git repository initialized (`git init`), two commits made (baseline, then Phase 1)

**Not touched:** `app/rules/generator.py`, `app/rules/vdot.py`, `app/ai/*`, `app/routes/evaluation_routes.py`, `app/schemas.py` (RunnerProfileCreate etc.), and every existing frontend research page's internals (`HomePage.jsx`, `CreatePlanPage.jsx`, `PlanResultPage.jsx`, `PlanDetailPage.jsx`, `EvaluationPage.jsx`, `EvaluationStatsPage.jsx`, `WorkoutCard.jsx`, `DisclaimerBanner.jsx`, all `components/ui/*`).

---

## 2. Database Changes

**Backup taken first:** `backend/running_research.db.PRE_PHASE1_BACKUP_20260929_084808` (full copy of the live database before any migration work, git-ignored, kept on disk).

**Migration path:** the migration was rehearsed on a throwaway copy of the real database first, verified row-for-row, and only then applied to the real `running_research.db`.

| Step | Action | Effect on existing data |
|---|---|---|
| `alembic stamp 0001_baseline` | Bookkeeping only — records revision `0001` as already applied | **Zero.** No DDL executed. |
| `alembic upgrade head` (→ `0002_add_auth`) | Creates `users`, `user_profiles`, `sessions`, `password_reset_tokens`; adds nullable `training_plans.user_id` | **Zero rows changed.** New column defaults to `NULL` on every existing row. |

**Verified before and after, on the real database:**
- `runner_profiles`: 9 rows (unchanged)
- `training_plans`: 9 rows (unchanged), all with `user_id = NULL` (correctly anonymous)
- `plan_evaluations`: 9 rows (unchanged)

No row in any research table was read, rewritten, or deleted. No `downgrade`/destructive migration was run against the real database at any point.

---

## 3. Authentication

| Flow | Endpoint | Behavior |
|---|---|---|
| Register | `POST /api/auth/register` | Email normalized + unique, Argon2-hashed password, display name (pseudonym-safe). Auto-logs in (sets session cookie). |
| Login | `POST /api/auth/login` | Same generic `"Invalid email or password."` for both "unknown email" and "wrong password" — never reveals which. |
| Logout | `POST /api/auth/logout` | Revokes the session **server-side** (`revoked_at`), then clears the cookie. |
| Session | httpOnly, `SameSite=Lax` cookie holding a random opaque token; only its SHA-256 hash is stored, in `sessions` (`expires_at`, `revoked_at`). |
| Get current user | `GET /api/auth/me` | 401 if no valid session — the frontend `AuthContext` treats this as "logged out," not an error. |
| Forgot password | `POST /api/auth/forgot-password` | Always the same generic response, regardless of whether the email exists. Reset link is logged server-side (dev mode) — no real email provider is wired up, and the token is never included in any API response. |
| Reset password | `POST /api/auth/reset-password` | Single-use (`used_at`), expires (default 30 min), revokes every existing session for that user on success. |

Full architectural rationale is in `README.md` Section 8 and `PRODUCT_READINESS_AUDIT.md` Section 3.

---

## 4. Authorization

Ownership is derived **exclusively** from the authenticated session (`get_current_user` / `get_optional_current_user` in `app/auth/dependencies.py`) — never from anything the client sends.

| Endpoint | Ownership enforcement |
|---|---|
| `POST /api/plans/generate` | `user_id` set from session if authenticated, else `NULL` (anonymous/research, unchanged) |
| `GET /api/plans/{id}` | Anonymous plan (`user_id IS NULL`): open to anyone, unchanged. Owned plan: only the owning user gets it; anyone else (including another logged-in user) gets the **same generic 404** a nonexistent ID would return |
| `GET /api/plans` (recent list) | Now excludes owned plans entirely — only ever lists anonymous research plans |
| `GET/PATCH /api/users/me/profile` | Always the session's own profile; a client-supplied `user_id` is ignored everywhere (verified by `test_client_supplied_user_id_is_ignored_on_profile_update`) |

Every existing resource endpoint was audited, not only the primary `GET`, per instruction.

---

## 5. Security

| Area | Implementation |
|---|---|
| Password hashing | Argon2 (`argon2-cffi`), verified via `test_password_is_never_stored_in_plaintext` |
| Cookie config | `HttpOnly; SameSite=Lax; Path=/; Max-Age=604800` confirmed via live `curl` (see below); `Secure` flag controlled by `SESSION_COOKIE_SECURE` (false in dev, must be true in production) |
| CSRF | SameSite=Lax + Origin-check middleware on cookie-bearing mutating requests (`app/core/csrf.py`), documented in README §8.5 with an explicit "not claimed fully secure in isolation" qualification |
| Rate limiting | `slowapi`, env-configurable (`RATE_LIMIT_LOGIN=5/minute`, `RATE_LIMIT_REGISTER=10/hour`, `RATE_LIMIT_PASSWORD_RESET=3/hour`, `RATE_LIMIT_PLAN_GENERATION=20/hour` defaults), per-user when authenticated else per-IP, clean 429 body with no internal details |
| CORS | `ALLOWED_ORIGINS` env var (still defaults to the two local dev origins), `allow_credentials=True` required for the session cookie |
| Secret handling | LLM keys remain server-side only; `.env` git-ignored; `.env.example` has variable names only |
| Error leakage | Global handlers (`app/core/errors.py`) convert raw 422 validation payloads and any unhandled exception into friendly messages; full details logged server-side only |

**Live cookie verification:**
```
set-cookie: session_token=***; HttpOnly; Max-Age=604800; Path=/; SameSite=lax
```

---

## 6. Tests

```
pytest: 79 passed, 0 failed
```
(43 pre-existing research tests + 36 new Phase 1 tests, run 3 times consecutively for determinism — identical result every time.)

New test files and what they cover:
- `test_auth.py` — registration (valid, duplicate email, invalid email, weak password, missing fields), login (valid, wrong password, unknown email — same generic error), logout (session revoked server-side, subsequent request rejected), session lifecycle (expired rejected, revoked rejected), password never stored in plaintext
- `test_authorization.py` — **the mandatory two-user cross-access test** (`test_user_a_plan_is_not_readable_by_user_b`: User B gets 404 on User A's plan, on GET, and it never appears in User B's list), anonymous-plan-stays-open regression test, ownership attaches correctly for authenticated generation and stays NULL for anonymous, client-supplied `user_id` is ignored
- `test_password_reset.py` — token never exposed in API response, same generic response for known/unknown email, raw token never persisted (only its hash), single-use enforcement, expiry enforcement
- `test_rate_limiting.py` — threshold enforced → 429, response body doesn't leak internals, limits sourced from configuration
- `test_csrf.py` — mutating request without Origin rejected, wrong Origin rejected, correct Origin allowed, GET requests never blocked
- `test_profile.py` — requires auth, defaults to empty, partial PATCH only touches sent fields, invalid pace format rejected, registration schema has no unnecessary PII fields

**Manual browser verification** (real running app, two real test accounts, not production credentials):
1. Registered `phase1-e2e-test@example.com` via the actual UI → redirected to `/dashboard`, session cookie set.
2. Saved a profile field (age) → persisted (confirmed via a direct API read after re-login).
3. Logged out via the UI → confirmed redirected to `/login` and that `/dashboard` immediately redirects to `/login` when re-visited unauthenticated.
4. Logged back in via the UI → correctly landed back on `/dashboard`, profile data intact.
5. Confirmed `/research` still works **with zero login**: generated a full anonymous plan through the real UI exactly as before; verified in the database that the new plan has `user_id = NULL`.
6. **Two-account IDOR check against the live server:** registered User A, generated an owned plan (200 on own read), logged out, registered User B, attempted to read User A's plan as User B → **404**, generic message, not distinguishable from a nonexistent plan.

---

## 7. Research Integrity — Explicit Confirmation

**No research logic was changed.** Specifically, none of the following were modified in this phase:
- VDOT calculations (`app/rules/vdot.py`)
- Training pace calculations, the 80/20 design constraint, or progression constraints (`app/rules/generator.py`)
- AI validation (`app/ai/validator.py`) or the deterministic offline fallback (`app/ai/llm_service.py`)
- The anonymous research evaluation system, its 4 dimensions, or the 1–5 Likert scale (`app/routes/evaluation_routes.py`, `app/schemas.py`)
- "Rule-Based Baseline" / "AI-Personalized Plan" terminology anywhere in the UI

The only change touching a research-adjacent table was the **additive, nullable** `user_id` column on `training_plans` and the two ownership-scoped queries in `plan_routes.py` — both verified to leave every existing and newly-generated anonymous plan's behavior identical to before.

---

## 8. Git Safety

```
$ git log --oneline
8ffb72c Phase 1: multi-user authentication, authorization, and security foundation
732f4b3 Initial commit: baseline research prototype before Phase 1

$ git status
On branch master
nothing to commit, working tree clean
```

- `.gitignore` created at the repo root, covering `.env`/`.env.*` (with `!.env.example` explicitly un-ignored), `*.db`/`*.sqlite*`, `__pycache__/`, `node_modules/`, `dist/`, and the timestamped DB backup files.
- Confirmed via `git ls-files`: **no** `.env` file, **no** `.db` file, **no** `node_modules`/`__pycache__` path is tracked.
- Confirmed via `git add -A -n` (dry run) before every commit: no secret, database, or build-artifact path would ever be staged.
- `.env.example` is tracked and contains variable names only — no real API keys or secrets.

---

## 9. Remaining Limitations (Honest Assessment)

- **Rate limiting is in-memory, single-process.** Fine for MVP; must move to a shared store (e.g. Redis) before running multiple API instances behind a load balancer.
- **No real email provider is integrated.** Password reset links are logged server-side in development, not emailed. This must be wired up (`app/auth/email_service.py`, provider TBD) before password reset is usable by real users.
- **CSRF protection is Origin-check + SameSite, not a cryptographic double-submit token.** Documented as an appropriate, not absolute, defense for this architecture in README §8.5.
- **No account email verification flow yet** — `email_verified_at` exists on the `users` table but nothing sets it. Low risk at this stage (no email-dependent features exist yet) but should be addressed before relying on email for anything sensitive.
- **No CI pipeline, Dockerfile, or production deployment config** — this phase is local-development-ready only, matching the original audit's Phase 5 ("Security Hardening + Production Readiness") scope, not this phase's.
- **The `/dashboard`, `/plans`, `/plans/new`, `/plans/:id` routes are intentionally placeholder pages** — routing/auth foundation only, as instructed; no workout logging, history, or analytics exist yet.
- **A handful of test/manual accounts now exist in the real `running_research.db`'s new `users` table** (from the manual browser verification in Section 6) — harmless test data, not real users, but worth knowing about if you inspect the database directly.
- The `sessions` table has no scheduled cleanup of expired rows yet — harmless at this scale, but worth adding a periodic cleanup before the table grows large in production.

---

**Phase 1 is complete. Awaiting review and approval before Phase 2.**

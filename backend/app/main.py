from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.database import engine, Base
from app.routes import plan_routes, evaluation_routes, profile_routes
from app.auth import routes as auth_routes
from app.core.rate_limit import limiter
from app.core.csrf import CSRFOriginCheckMiddleware
from app.core.errors import register_exception_handlers

# Initialize SQLite database tables (auth tables + research tables).
# The real running_research.db is migrated via Alembic (see backend/alembic/);
# this create_all() call is a no-op for tables that already exist and only
# matters for a brand-new database (e.g. the isolated test DB in
# tests/conftest.py, which intentionally bypasses Alembic for speed).
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Academic Research Prototype for BINUS University S2 Thesis: 'Design and Evaluation of an AI-Based Personalized Running Training Recommendation System' -- now growing a multi-user consumer foundation alongside the unchanged research flow.",
    version="1.1.0"
)

# Rate limiting (see app/core/rate_limit.py) -- limits on login/register/
# password-reset/plan-generation are applied at the route level.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Friendly, non-leaking error responses (see app/core/errors.py).
register_exception_handlers(app)

# CORS: origins are environment-driven (ALLOWED_ORIGINS), never "*" --
# see .env.example. allow_credentials=True is required for the session cookie.
_allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CSRF defense-in-depth for the cookie-based session (see app/core/csrf.py
# and README.md's "Authentication & CSRF Strategy" section).
app.add_middleware(CSRFOriginCheckMiddleware)

app.include_router(auth_routes.router, prefix="/api")
app.include_router(profile_routes.router, prefix="/api")
app.include_router(plan_routes.router, prefix="/api")
app.include_router(evaluation_routes.router, prefix="/api")

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "prototype": settings.PROJECT_NAME,
        "academic_affiliation": "BINUS University - S2 Information Technology",
        "safety_disclaimer": "This system provides running recommendations solely for academic research and educational purposes. It does not constitute medical advice."
    }

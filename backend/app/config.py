import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")

class Settings(BaseModel):
    PROJECT_NAME: str = "AI Running Training Recommendation System (Academic Prototype)"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./running_research.db")

    # 'development' or 'production'. Controls cookie Secure flag and other
    # environment-sensitive behavior. Never defaults to production implicitly.
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Comma-separated list of allowed CORS/frontend origins.
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

    # LLM Settings
    # Supports 'gemini', 'openai', or 'auto' (checks available keys)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # --- Authentication / session settings ---
    SESSION_COOKIE_NAME: str = os.getenv("SESSION_COOKIE_NAME", "session_token")
    SESSION_TTL_HOURS: int = int(os.getenv("SESSION_TTL_HOURS", "168"))  # 7 days
    # Only send the cookie over HTTPS when true. Must be true in production;
    # defaults to false so local http development keeps working.
    SESSION_COOKIE_SECURE: bool = _get_bool("SESSION_COOKIE_SECURE", default=False)
    PASSWORD_RESET_TOKEN_TTL_MINUTES: int = int(os.getenv("PASSWORD_RESET_TOKEN_TTL_MINUTES", "30"))

    # --- Email (password reset) ---
    # No real email provider is wired up yet. When EMAIL_PROVIDER is empty,
    # the email service logs the reset link server-side instead of sending
    # a real email (see app/auth/email_service.py) -- it never pretends to
    # have delivered anything.
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "")
    EMAIL_API_KEY: str = os.getenv("EMAIL_API_KEY", "")
    EMAIL_FROM_ADDRESS: str = os.getenv("EMAIL_FROM_ADDRESS", "no-reply@example.com")
    FRONTEND_BASE_URL: str = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")

    # --- Rate limiting (see app/core/rate_limit.py) ---
    # slowapi/limits string format, e.g. "5/minute", "10/hour".
    RATE_LIMIT_LOGIN: str = os.getenv("RATE_LIMIT_LOGIN", "5/minute")
    RATE_LIMIT_REGISTER: str = os.getenv("RATE_LIMIT_REGISTER", "10/hour")
    RATE_LIMIT_PASSWORD_RESET: str = os.getenv("RATE_LIMIT_PASSWORD_RESET", "3/hour")
    RATE_LIMIT_PLAN_GENERATION: str = os.getenv("RATE_LIMIT_PLAN_GENERATION", "20/hour")

settings = Settings()

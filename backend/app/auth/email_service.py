"""
Email-sending abstraction for password reset links.

No third-party email provider is integrated in Phase 1 -- per the Phase 1
instructions, we do not add an external email service without a documented
reason, and we never pretend delivery works when it doesn't. When
settings.EMAIL_PROVIDER is unset (the default), send_password_reset_email()
logs the reset link server-side instead of emailing it, clearly labeled as
a development-mode fallback. It never raises, and the caller must never
include the raw reset link/token in an HTTP response.

To wire up a real provider later (e.g. Resend, SendGrid, SES): implement
the "real provider" branch below using settings.EMAIL_PROVIDER /
EMAIL_API_KEY / EMAIL_FROM_ADDRESS (already defined in app/config.py and
documented in .env.example), without changing this function's signature.
"""
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    if settings.EMAIL_PROVIDER:
        # No provider is implemented yet even if one is configured -- fail
        # loudly in logs rather than silently pretending to send.
        logger.warning(
            "EMAIL_PROVIDER=%s is configured but no email integration is implemented yet. "
            "Falling back to logging the reset link instead of sending real email.",
            settings.EMAIL_PROVIDER,
        )

    logger.info(
        "[DEV MODE - no email provider configured] Password reset requested for %s. "
        "Reset link (would normally be emailed, never logged in production): %s",
        to_email,
        reset_link,
    )

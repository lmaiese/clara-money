import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


async def send_reset_email(to_email: str, reset_link: str) -> None:
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set — skipping password reset email")
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": "Clara <noreply@claramoney.it>",
                    "to": [to_email],
                    "subject": "Reimposta la tua password — Clara",
                    "html": (
                        f"<p>Hai richiesto il reset della password.</p>"
                        f"<p><a href='{reset_link}'>Clicca qui per reimpostare</a> (link valido 1 ora).</p>"
                        f"<p>Se non hai richiesto il reset, ignora questa email.</p>"
                    ),
                },
            )
    except Exception:
        logger.exception("Failed to send reset email to %s", to_email)

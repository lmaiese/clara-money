import asyncio
import html
import json
import logging
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
from anthropic import Anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Profile, Scenario, User
from app.scenarios.math import compute_scenarios
from app.scenarios.service import _build_fallback, _build_prompt, _fmt_eur

logger = logging.getLogger(__name__)

MONTHS = {
    1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile",
    5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto",
    9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre",
}


def _delta_str(delta: dict | None, key: str) -> str:
    """Restituisce HTML colorato '+€X.XXX vs mese scorso' o stringa vuota."""
    if delta is None:
        return ""
    val = delta[key]
    sign = "+" if val >= 0 else "-"
    color = "#16a34a" if val >= 0 else "#dc2626"
    return f' <span style="color:{color}">({sign}€{_fmt_eur(abs(val))} vs mese scorso)</span>'


async def send_digest_email(
    to_email: str,
    profile: SimpleNamespace,
    math_data: dict,
    delta: dict | None,
    narratives: dict,
) -> None:
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set — skipping digest email for %s", to_email)
        return

    now = datetime.now(timezone.utc)
    subject = f"Il tuo aggiornamento mensile Clara — {MONTHS[now.month]} {now.year}"

    html_content = f"""<p>Ciao {html.escape(to_email)},</p>
<p>Il tuo piano finanziario aggiornato per <strong>{profile.horizon_years} anni</strong>.</p>
<table cellpadding="8">
  <tr>
    <td><strong>Scenario Sicuro</strong></td>
    <td>€{_fmt_eur(math_data["sicuro"][-1])}{_delta_str(delta, "sicuro")}</td>
  </tr>
  <tr>
    <td><strong>Scenario Bilanciato</strong></td>
    <td>€{_fmt_eur(math_data["bilanciato"][-1])}{_delta_str(delta, "bilanciato")}</td>
  </tr>
  <tr>
    <td><strong>Scenario Crescita</strong></td>
    <td>€{_fmt_eur(math_data["crescita"][-1])}{_delta_str(delta, "crescita")}</td>
  </tr>
</table>
<p>{narratives["intro"]}</p>
<p><strong>Sicuro:</strong> {narratives["sicuro"]}</p>
<p><strong>Bilanciato:</strong> {narratives["bilanciato"]}</p>
<p><strong>Crescita:</strong> {narratives["crescita"]}</p>
<hr>
<p style="font-size:12px;color:#6b7280">Clara · Problemi? Scrivi a
<a href="mailto:support@claramoney.it">support@claramoney.it</a></p>"""

    async with httpx.AsyncClient(timeout=10.0) as http:
        response = await http.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": "Clara <noreply@claramoney.it>",
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            },
        )
        response.raise_for_status()


async def run_monthly_digest(db: Session) -> dict:
    sent = skipped = errors = 0
    now = datetime.now(timezone.utc)

    users = db.execute(
        select(User).join(Profile)
    ).scalars().all()

    logger.info("Digest job started: %d Pro users found", len(users))

    # Fix 5: Anthropic client creato una volta sola fuori dal loop
    ai = Anthropic(api_key=settings.anthropic_api_key, max_retries=1) if settings.anthropic_api_key else None

    # Fix 3: range datetime UTC esplicito per dedup timezone-safe
    if now.month == 12:
        month_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        month_end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    for user in users:
        email = user.email
        user_id = user.id
        profile = db.get(Profile, user_id)

        try:
            # 1. Solo utenti pro con profilo completo
            if user.plan != "pro" or not profile or profile.onboarding_step < 5 or not profile.horizon_years:
                logger.info("Skipping user %s: incomplete profile", user_id)
                skipped += 1
                continue

            # 2. Dedup: skip se già inviato questo mese (timezone-safe)
            existing = db.execute(
                select(Scenario.id)
                .where(Scenario.user_id == user_id)
                .where(Scenario.generated_at >= month_start)
                .where(Scenario.generated_at < month_end)
                .limit(1)
            ).first()
            if existing:
                logger.info("Skipping user %s: already sent this month", user_id)
                skipped += 1
                continue

            # 3. Ultimo scenario per calcolare delta
            prev_scenario = db.execute(
                select(Scenario)
                .where(Scenario.user_id == user_id)
                .order_by(Scenario.generated_at.desc())
                .limit(1)
            ).scalar_one_or_none()

            # 4. Ricalcola scenari
            capital = float(profile.liquid_savings or 0)
            monthly_pmt = max(
                0.0,
                float((profile.monthly_income or 0) - (profile.monthly_expenses or 0)),
            )
            math_data = compute_scenarios(capital, monthly_pmt, profile.horizon_years)

            # 5. Delta (None se primo scenario) — schema-safe
            delta = None
            if prev_scenario and prev_scenario.math_data:
                try:
                    prev = prev_scenario.math_data
                    delta = {k: math_data[k][-1] - prev[k][-1] for k in ["sicuro", "bilanciato", "crescita"]}
                except (KeyError, IndexError, TypeError):
                    logger.warning("Could not compute delta for user %s: legacy math_data schema", user_id)

            # 6. Narrativa Claude (timeout 30s) o fallback template
            profile_ns = SimpleNamespace(
                age=profile.age,
                monthly_income=profile.monthly_income,
                monthly_expenses=profile.monthly_expenses,
                liquid_savings=profile.liquid_savings,
                existing_investments=profile.existing_investments,
                goal=profile.goal,
                horizon_years=profile.horizon_years,
            )
            narratives = None
            if ai is not None:
                try:
                    response = await asyncio.to_thread(
                        ai.messages.create,
                        model=settings.claude_model,
                        max_tokens=1024,
                        timeout=30,
                        messages=[{"role": "user", "content": _build_prompt(profile_ns, math_data)}],
                    )
                    parsed = json.loads(response.content[0].text)
                    if {"intro", "sicuro", "bilanciato", "crescita"}.issubset(parsed.keys()):
                        narratives = parsed
                except Exception:
                    logger.exception("Claude failed for user %s, using fallback", user_id)
            if narratives is None:
                narratives = _build_fallback(profile_ns, math_data)

            # 7. Prepara nuovo Scenario (non ancora committato)
            profile_snapshot = {
                "age": profile.age,
                "monthly_income": profile.monthly_income,
                "monthly_expenses": profile.monthly_expenses,
                "liquid_savings": profile.liquid_savings,
                "existing_investments": profile.existing_investments,
                "goal": profile.goal,
                "horizon_years": profile.horizon_years,
            }
            scenario = Scenario(
                user_id=user_id,
                profile_snapshot=profile_snapshot,
                math_data=math_data,
                narratives=narratives,
                narrative_ready=True,
            )
            db.add(scenario)

            # 8. Email PRIMA del commit — se fallisce, exception → per-user except → db.rollback()
            await send_digest_email(email, profile_ns, math_data, delta, narratives)

            # 9. Commit SOLO se email ha avuto successo
            db.commit()
            logger.info("Digest sent to user %s (delta=%s)", user_id, delta is not None)
            sent += 1

        except Exception:
            logger.exception("Digest failed for user %s", user_id)
            db.rollback()
            errors += 1

    logger.info("Digest job completed: sent=%d skipped=%d errors=%d", sent, skipped, errors)
    return {"sent": sent, "skipped": skipped, "errors": errors}

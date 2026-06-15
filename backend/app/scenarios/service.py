import json
from types import SimpleNamespace
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Profile, Scenario
from app.scenarios.math import MathData, compute_scenarios


NARRATIVE_FALLBACK = {
    "intro": "Ecco cosa potrebbero fare i tuoi risparmi in {anni} anni.",
    "sicuro": (
        "Con un approccio prudente (3.5% annuo), potresti arrivare a circa €{valore}. "
        "Strumenti tipici: conti deposito, BTP. Rischio: basso."
    ),
    "bilanciato": (
        "Un portafoglio bilanciato (5% annuo) potrebbe portarti a circa €{valore}. "
        "Strumenti tipici: ETF obbligazionari misti. Rischio: medio."
    ),
    "crescita": (
        "Lo scenario più ambizioso (7% annuo) punta a circa €{valore} in {anni} anni. "
        "Strumenti tipici: ETF azionario globale diversificato. Rischio: alto."
    ),
}


def _fmt_eur(value: float) -> str:
    return f"{int(value):,}".replace(",", ".")


def _build_fallback(profile: SimpleNamespace, math_data: MathData) -> dict:
    return {
        "intro": NARRATIVE_FALLBACK["intro"].format(anni=profile.horizon_years),
        "sicuro": NARRATIVE_FALLBACK["sicuro"].format(valore=_fmt_eur(math_data["sicuro"][-1])),
        "bilanciato": NARRATIVE_FALLBACK["bilanciato"].format(valore=_fmt_eur(math_data["bilanciato"][-1])),
        "crescita": NARRATIVE_FALLBACK["crescita"].format(
            valore=_fmt_eur(math_data["crescita"][-1]), anni=profile.horizon_years
        ),
    }


def _build_prompt(profile: SimpleNamespace, math_data: MathData) -> str:
    investments_note = (
        f"Nota: l'utente ha già {profile.existing_investments}€ investiti — citalo come contesto."
        if (profile.existing_investments or 0) > 0
        else ""
    )
    return f"""Sei Clara, consulente finanziaria italiana semplice e diretta.
L'utente ha {profile.age} anni, reddito netto {profile.monthly_income}€/mese,
spese {profile.monthly_expenses}€/mese, risparmi liquidi {profile.liquid_savings}€,
obiettivo: {profile.goal}, orizzonte: {profile.horizon_years} anni.
{investments_note}

Hai calcolato 3 scenari. Per ognuno scrivi 2-3 frasi in italiano semplice:
cosa significa il valore finale, che categoria di strumento si usa, rischio in una parola.
Scenario Sicuro: valore finale €{int(math_data['sicuro'][-1])}.
Scenario Bilanciato: valore finale €{int(math_data['bilanciato'][-1])}.
Scenario Crescita: valore finale €{int(math_data['crescita'][-1])}.
Non nominare prodotti specifici. Solo categorie.

Rispondi SOLO con JSON valido senza markdown:
{{"intro":"...","sicuro":"...","bilanciato":"...","crescita":"..."}}"""


def _run_narrative_generation(scenario_id: str, profile_data: dict, math_data: MathData) -> None:
    """Background task: chiama Claude, usa fallback template se fallisce."""
    db: Session = SessionLocal()
    try:
        scenario = db.get(Scenario, scenario_id)
        if scenario is None:
            return

        profile = SimpleNamespace(**profile_data)
        narratives = None

        if settings.anthropic_api_key:
            try:
                from anthropic import Anthropic
                client = Anthropic(api_key=settings.anthropic_api_key)
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": _build_prompt(profile, math_data)}],
                )
                parsed = json.loads(response.content[0].text)
                _REQUIRED = {"intro", "sicuro", "bilanciato", "crescita"}
                if _REQUIRED.issubset(parsed.keys()):
                    narratives = parsed
            except Exception:
                pass

        if narratives is None:
            narratives = _build_fallback(profile, math_data)

        scenario.narratives = narratives
        scenario.narrative_ready = True
        db.commit()
    finally:
        db.close()


def generate_scenarios(db: Session, user, background_tasks: BackgroundTasks) -> tuple[Scenario, MathData]:
    profile = db.get(Profile, user.id)
    if profile is None or profile.onboarding_step < 5:
        raise HTTPException(status_code=400, detail="Profile not complete")

    capital = float(profile.liquid_savings or 0)
    monthly_pmt = max(0.0, float((profile.monthly_income or 0) - (profile.monthly_expenses or 0)))
    math_data = compute_scenarios(capital, monthly_pmt, profile.horizon_years)

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
        user_id=user.id,
        profile_snapshot=profile_snapshot,
        math_data=math_data,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)

    background_tasks.add_task(_run_narrative_generation, str(scenario.id), profile_snapshot, math_data)
    return scenario, math_data


def get_latest_scenario(db: Session, user) -> Scenario | None:
    stmt = (
        select(Scenario)
        .where(Scenario.user_id == user.id)
        .order_by(Scenario.generated_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()

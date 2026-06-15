from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.scenarios.service import generate_scenarios, get_latest_scenario
from app.schemas import ScenarioResponse

router = APIRouter()


@router.post("/generate", response_model=ScenarioResponse)
def generate(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scenario, math_data = generate_scenarios(db, current_user, background_tasks)
    return ScenarioResponse(
        scenario_id=scenario.id,
        math_data=math_data,
        narratives=scenario.narratives,
        narrative_ready=scenario.narrative_ready,
        generated_at=scenario.generated_at,
    )


@router.get("/me", response_model=ScenarioResponse | None)
def get_my_scenario(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scenario = get_latest_scenario(db, current_user)
    if scenario is None:
        return None
    return ScenarioResponse(
        scenario_id=scenario.id,
        math_data=scenario.math_data,
        narratives=scenario.narratives,
        narrative_ready=scenario.narrative_ready,
        generated_at=scenario.generated_at,
    )

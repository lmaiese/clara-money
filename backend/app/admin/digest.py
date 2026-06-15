from sqlalchemy.orm import Session


async def send_digest_email(to_email, profile, math_data, delta, narratives) -> None:
    pass


async def run_monthly_digest(db: Session) -> dict:
    return {"sent": 0, "skipped": 0, "errors": 0}

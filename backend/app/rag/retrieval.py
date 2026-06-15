from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings

RETRIEVAL_QUERIES: dict[str, str] = {
    "sicuro":     "conti deposito BTP obbligazioni garantite normativa italiana rendimento",
    "bilanciato": "ETF obbligazionario misto MiFID II consulenza finanziaria rischio moderato",
    "crescita":   "ETF azionario globale CONSOB rischio mercato orizzonte lungo termine",
}

MAX_DISTANCE = 0.35


def _embed_query(query: str) -> list[float]:
    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(model="text-embedding-3-small", input=[query])
    return response.data[0].embedding


def _cosine_search(db: Session, embedding: list[float]) -> list[tuple]:
    from app.models import Document
    rows = db.execute(
        select(
            Document,
            Document.embedding.cosine_distance(embedding).label("distance"),
        )
        .order_by(Document.embedding.cosine_distance(embedding))
        .limit(2)
    ).all()
    return [(row.Document, row.distance) for row in rows]


def retrieve_context(db: Session, scenario_type: str) -> list:
    embedding = _embed_query(RETRIEVAL_QUERIES[scenario_type])
    rows = _cosine_search(db, embedding)
    return [doc for doc, dist in rows if dist <= MAX_DISTANCE]


def retrieve_all_contexts(db: Session) -> dict[str, list]:
    result: dict[str, list] = {}
    for scenario_type in RETRIEVAL_QUERIES:
        try:
            docs = retrieve_context(db, scenario_type)
            if docs:
                result[scenario_type] = docs
        except Exception:
            pass
    return result

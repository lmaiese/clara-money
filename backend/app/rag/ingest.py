from pathlib import Path
from sqlalchemy.orm import Session
from app.config import settings

SOURCE_MAP: dict[str, str] = {
    "bdi": "BdI",
    "ae": "AE",
    "consob": "CONSOB",
}


def extract_text(pdf_path: Path) -> str:
    import pymupdf4llm
    return pymupdf4llm.to_markdown(str(pdf_path), header=False, footer=False)


def chunk_text(text: str) -> list[str]:
    from langchain_text_splitters import MarkdownTextSplitter
    splitter = MarkdownTextSplitter(chunk_size=400, chunk_overlap=50)
    return splitter.split_text(text)


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(model="text-embedding-3-small", input=chunks)
    return [item.embedding for item in response.data]


def ingest_folder(db: Session, folder: Path) -> int:
    from app.models import Document

    count = 0
    for pdf_path in sorted(folder.rglob("*.pdf")):
        source_key = pdf_path.parent.name.lower()
        source = SOURCE_MAP.get(source_key, source_key.upper())
        stem = pdf_path.stem

        text = extract_text(pdf_path)
        chunks = chunk_text(text)
        if not chunks:
            continue

        embeddings = embed_chunks(chunks)
        total = len(chunks)

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            title = f"{stem} [{i + 1}/{total}]"
            existing = db.query(Document).filter_by(title=title, content=chunk).first()
            if existing:
                continue
            doc = Document(title=title, source=source, content=chunk, embedding=embedding)
            db.add(doc)
            count += 1

        db.flush()

    return count

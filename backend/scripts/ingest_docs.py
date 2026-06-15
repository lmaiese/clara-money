#!/usr/bin/env python
"""CLI per ingestione documenti normativi nel corpus RAG."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.rag.ingest import ingest_folder


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingesta PDF normativi in pgvector")
    parser.add_argument("--folder", required=True, help="Path alla cartella docs_corpus/")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print(f"Errore: cartella '{folder}' non trovata", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        count = ingest_folder(db, folder)
        print(f"Ingestione completata: {count} chunk inseriti")
    finally:
        db.close()


if __name__ == "__main__":
    main()

from unittest.mock import patch
from app.rag.ingest import chunk_text, ingest_folder
from app.models import Document


def test_chunk_text_splits_long_text():
    long_text = "parola " * 500
    chunks = chunk_text(long_text)
    assert len(chunks) > 1


def test_ingest_folder_inserts_documents(db, tmp_path):
    pdf_dir = tmp_path / "bdi"
    pdf_dir.mkdir()
    (pdf_dir / "relazione.pdf").touch()

    fake_text = "Testo normativo italiano. " * 30

    with patch("app.rag.ingest.extract_text", return_value=fake_text):
        with patch("app.rag.ingest.embed_chunks", side_effect=lambda chunks: [[0.1] * 1536] * len(chunks)):
            count = ingest_folder(db, tmp_path)

    assert count >= 1
    docs = db.query(Document).all()
    assert len(docs) >= 1
    assert docs[0].source == "BdI"


def test_ingest_folder_skips_duplicate_documents(db, tmp_path):
    pdf_dir = tmp_path / "ae"
    pdf_dir.mkdir()
    (pdf_dir / "circolare.pdf").touch()

    fake_text = "Testo unico finanza. " * 30

    with patch("app.rag.ingest.extract_text", return_value=fake_text):
        with patch("app.rag.ingest.embed_chunks", side_effect=lambda chunks: [[0.2] * 1536] * len(chunks)):
            count1 = ingest_folder(db, tmp_path)
            count2 = ingest_folder(db, tmp_path)

    assert count1 >= 1
    assert count2 == 0

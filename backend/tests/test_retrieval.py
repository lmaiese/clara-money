from unittest.mock import patch, MagicMock
from app.rag.retrieval import retrieve_context, retrieve_all_contexts, RETRIEVAL_QUERIES


def _fake_doc(title="relazione [1/10]", source="BdI", content="testo normativo"):
    doc = MagicMock()
    doc.title = title
    doc.source = source
    doc.content = content
    return doc


def test_retrieve_context_returns_docs_within_threshold(db):
    fake_embedding = [0.1] * 1536
    fake_doc = _fake_doc()

    with patch("app.rag.retrieval._embed_query", return_value=fake_embedding):
        with patch("app.rag.retrieval._cosine_search", return_value=[(fake_doc, 0.2)]):
            result = retrieve_context(db, "sicuro")

    assert len(result) == 1
    assert result[0].title == "relazione [1/10]"


def test_retrieve_context_excludes_docs_above_threshold(db):
    fake_embedding = [0.1] * 1536
    fake_doc = _fake_doc()

    with patch("app.rag.retrieval._embed_query", return_value=fake_embedding):
        with patch("app.rag.retrieval._cosine_search", return_value=[(fake_doc, 0.5)]):
            result = retrieve_context(db, "sicuro")

    assert result == []


def test_retrieve_all_contexts_silent_fallback_on_error(db):
    with patch("app.rag.retrieval._embed_query", side_effect=Exception("OpenAI down")):
        result = retrieve_all_contexts(db)

    assert result == {}

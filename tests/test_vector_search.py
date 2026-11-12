import retrieval.vector_search as vector_search
import pytest

class FakeRecord:
    def data(self):
        return {
            "trecho_id": "trecho-001",
            "texto": "Informações sobre imóveis rurais.",
            "pagina": 1,
            "documento_id": "doc-001",
            "score": 0.95,
        }


class FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def run(self, query, **parameters):
        assert "db.index.vector.queryNodes" in query
        assert parameters["top_k"] == 5
        assert parameters["embedding"] == [0.1, 0.2, 0.3]

        return [FakeRecord()]


class FakeDriver:
    def session(self):
        return FakeSession()

    def close(self):
        pass


def test_search_similar_chunks(monkeypatch):
    monkeypatch.setattr(
        vector_search,
        "generate_embeddings",
        lambda texts: [[0.1, 0.2, 0.3]],
    )

    monkeypatch.setattr(
        vector_search,
        "get_driver",
        lambda: FakeDriver(),
    )

    result = vector_search.search_similar_chunks(
        "Informações sobre propriedades rurais."
    )

    assert len(result) == 1
    assert result[0]["trecho_id"] == "trecho-001"
    assert result[0]["score"] == 0.95


def test_search_similar_chunks_query_vazia():
    with pytest.raises(ValueError):
        vector_search.search_similar_chunks(" ")


def test_search_similar_chunks_top_k_invalido():
    with pytest.raises(ValueError):
        vector_search.search_similar_chunks(
            "Imóveis rurais",
            top_k=0,
        )

# python -c "from retrieval.vector_search import search_similar_chunks; print(search_similar_chunks('Informações sobre imóveis rurais na Paraíba', top_k=5))"
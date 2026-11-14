import os
import pytest
from graph.repositories import save_chunks


@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Teste de integração ao vivo com Neo4j Aura (defina RUN_INTEGRATION_TESTS=1).",
)
def test_save_chunks():
    chunks = [{
        "id": "teste-agro-001",
        "text": "O milho é uma cultura agrícola importante.",
        "source": "teste_agro.pdf",
        "page": 1,
        "embedding": [0.01] * 1536,
    }]

    total = save_chunks(chunks)

    assert total == 1

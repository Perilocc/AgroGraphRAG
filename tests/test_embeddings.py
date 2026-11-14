import os
import pytest
from retrieval.embeddings import generate_embeddings
from utils.config import OPENAI_API_KEY


@pytest.mark.skipif(
    not (os.getenv("RUN_INTEGRATION_TESTS") and OPENAI_API_KEY),
    reason="Requer OPENAI_API_KEY e RUN_INTEGRATION_TESTS=1 para chamada real à API.",
)
def test_generate_embeddings():
    result = generate_embeddings([
        "O cultivo de milho é importante para o agronegócio brasileiro."
    ])

    assert len(result) == 1
    assert len(result[0]) == 1536

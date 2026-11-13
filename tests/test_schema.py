import os
import pytest
from graph.schema import create_schema


@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Teste de integração ao vivo com Neo4j Aura (defina RUN_INTEGRATION_TESTS=1).",
)
def test_create_schema():
    create_schema()

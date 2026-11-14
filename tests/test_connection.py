import os
import pytest
from graph.connection import test_connection as check_neo4j_connection


@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Teste de integração ao vivo com Neo4j Aura (defina RUN_INTEGRATION_TESTS=1).",
)
def test_neo4j_connection():
    assert check_neo4j_connection() is True

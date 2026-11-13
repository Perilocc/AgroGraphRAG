import os
from pathlib import Path
import pytest
from ingestion.sncr_transformer import transform_sncr
from graph.repositories import save_sncr_graph
from ingestion.sncr import read_sncr

CSV_PATH = Path("data/structured/sncr/Imoveis_2507507.csv")


@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Teste de integração ao vivo com Neo4j Aura (defina RUN_INTEGRATION_TESTS=1).",
)
def test_save_sncr_graph():
    df = read_sncr(CSV_PATH)

    sample = df.head(3)

    graph_data = transform_sncr(
        sample,
        source_name="teste_sncr.csv",
    )

    result = save_sncr_graph(graph_data)

    assert result["entities"] > 0
    assert result["relationships"] > 0

from ingestion.sncr_transformer import transform_sncr
from graph.repositories import save_sncr_graph
from ingestion.sncr import read_sncr
from pathlib import Path

CSV_PATH = Path("data/structured/sncr/Imoveis_2507507.csv")


def test_save_sncr_graph():
    df = read_sncr(CSV_PATH)

    sample = df.head(3) # Usa só 3 registros nesse teste aí e grava mesmo no neo4j

    graph_data = transform_sncr(
        sample,
        source_name="teste_sncr.csv",
    )

    result = save_sncr_graph(graph_data)

    assert result["entities"] > 0
    assert result["relationships"] > 0

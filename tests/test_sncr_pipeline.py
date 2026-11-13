import os
from pathlib import Path
import pytest
from ingestion.sncr_pipeline import ingest_sncr

CSV_PATH = Path(
    "data/structured/sncr/Imoveis_PB_01_11_2026.csv"
)


@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Teste de integração pesado ao vivo com Neo4j Aura (defina RUN_INTEGRATION_TESTS=1).",
)
def test_ingest_sncr():
    result = ingest_sncr(
        CSV_PATH,
        chunksize=500,
        batch_size=100,
        max_records=40000,
    )

    assert result["registros_lidos"] == 40000
    assert result["blocos_processados"] == 80
    assert result["entidades_processadas"] > 0
    assert result["relacionamentos_processados"] > 0

    print(result)

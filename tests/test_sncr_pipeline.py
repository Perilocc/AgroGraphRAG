from ingestion.sncr_pipeline import ingest_sncr
from pathlib import Path

CSV_PATH = Path(
    "data/structured/sncr/Imoveis_PB_01_11_2026.csv"
)

def test_ingest_sncr():
    result = ingest_sncr(
        CSV_PATH,
        chunksize=1000,
        batch_size=250,
        max_records=10000,
    )

    assert result["registros_lidos"] == 10000
    assert result["blocos_processados"] == 10
    assert result["entidades_processadas"] > 0
    assert result["relacionamentos_processados"] > 0

    print(result)

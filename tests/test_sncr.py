from ingestion.sncr import read_sncr
from pathlib import Path

CSV_PATH = Path("data/structured/sncr/Imoveis_2507507.csv")

def test_read_sncr():
    df = read_sncr(CSV_PATH)

    assert not df.empty
    assert len(df) == 652

    assert "codigo_imovel" in df.columns
    assert "titular" in df.columns
    assert "area_total" in df.columns
    assert "percentual_detencao" in df.columns

    assert df["codigo_imovel"].notna().all()

    assert df["area_total"].dtype.kind in "fi"
    assert df["percentual_detencao"].dtype.kind in "fi"

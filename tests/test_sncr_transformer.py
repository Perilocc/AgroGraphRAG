from ingestion.sncr_transformer import transform_sncr
from ingestion.sncr import read_sncr
from graph.ontology import (
    validate_entity,
    validate_relationship,
)
from pathlib import Path

CSV_PATH = Path("data/structured/sncr/Imoveis_2507507.csv")


def test_transform_sncr():
    df = read_sncr(CSV_PATH)

    result = transform_sncr(
        df,
        source_name=CSV_PATH.name,
    )

    assert len(result["entities"]) > 0
    assert len(result["relationships"]) > 0

    for entity in result["entities"]:
        assert validate_entity({
            "id": entity["id"],
            "name": entity["name"],
            "type": entity["type"],
        })

    for relationship in result["relationships"]:
        assert validate_relationship(relationship)

    types = {
        entity["type"]
        for entity in result["entities"]
    }

    assert "ImovelRural" in types
    assert "Municipio" in types
    assert "Detentor" in types
    assert "RegistroDetencao" in types
    assert "Documento" in types

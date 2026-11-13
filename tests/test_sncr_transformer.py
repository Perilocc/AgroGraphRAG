import pandas as pd
from pathlib import Path
from ingestion.sncr import read_sncr
from ingestion.sncr_transformer import transform_sncr
from graph.ontology import (
    validate_entity,
    validate_relationship,
)

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


def test_detentor_deduplication_and_municipio_normalization():
    df = pd.DataFrame([
        {
            "codigo_imovel": "1001",
            "denominacao": "Fazenda A",
            "codigo_municipio": "2507507",
            "municipio": "JOÃO PESSOA",
            "uf": "PB",
            "area_total": 10.0,
            "titular": "AGROPECUARIA NORDESTE LTDA",
            "natureza_juridica": "LTDA",
            "condicao_pessoa": "Proprietario",
            "percentual_detencao": 100.0,
        },
        {
            "codigo_imovel": "1002",
            "denominacao": "Fazenda B",
            "codigo_municipio": "2507507",
            "municipio": "JOÃO PESSOA",
            "uf": "PB",
            "area_total": 20.0,
            "titular": "AGROPECUARIA NORDESTE LTDA",
            "natureza_juridica": "LTDA",
            "condicao_pessoa": "Proprietario",
            "percentual_detencao": 100.0,
        },
        {
            "codigo_imovel": "1003",
            "denominacao": "Sítio C",
            "codigo_municipio": "2507507",
            "municipio": "JOÃO PESSOA",
            "uf": "PB",
            "area_total": 5.0,
            "titular": "JOSE ************",
            "natureza_juridica": "",
            "condicao_pessoa": "Proprietario",
            "percentual_detencao": 100.0,
        },
        {
            "codigo_imovel": "1004",
            "denominacao": "Sítio D",
            "codigo_municipio": "2507507",
            "municipio": "JOÃO PESSOA",
            "uf": "PB",
            "area_total": 8.0,
            "titular": "JOSE ************",
            "natureza_juridica": "",
            "condicao_pessoa": "Proprietario",
            "percentual_detencao": 100.0,
        },
    ])

    result = transform_sncr(df, source_name="teste.csv")
    detentores = [e for e in result["entities"] if e["type"] == "Detentor"]
    municipios = [e for e in result["entities"] if e["type"] == "Municipio"]

    # Sem '*': 1 detentor deduplicado; com '*': 2 detentores separados por linha
    assert len(detentores) == 3
    assert len(municipios) == 1
    assert municipios[0]["properties"]["nome_normalizado"] == "joao pessoa"

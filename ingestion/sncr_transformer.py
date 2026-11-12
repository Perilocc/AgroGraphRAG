import pandas as pd
import hashlib

def generate_id(prefix: str, value: str) -> str:
    content = f"{prefix}:{value}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def clean_value(value):
    if pd.isna(value):
        return None

    if isinstance(value, str):
        value = value.strip()
        return value if value else None

    return value


def transform_sncr(
    df: pd.DataFrame,
    source_name: str,
    start_index: int = 0
) -> dict:
    entities = {}
    relationships = {}

    document_id = generate_id("documento", source_name)

    entities[document_id] = {
        "id": document_id,
        "name": source_name,
        "type": "Documento",
        "properties": {
            "nome": source_name,
            "origem": "SNCR",
        },
    }

    for index, row in enumerate(
        df.to_dict(orient="records"),
        start=start_index + 2
    ):
        codigo = clean_value(row.get("codigo_imovel"))

        if not codigo:
            continue

        imovel_id = generate_id("imovel", codigo)

        municipio_codigo = clean_value(
            row.get("codigo_municipio")
        )
        municipio_nome = clean_value(row.get("municipio"))
        uf = clean_value(row.get("uf"))

        if not municipio_nome:
            continue

        municipio_key = (
            municipio_codigo
            or f"{municipio_nome}:{uf}"
        )

        municipio_id = generate_id(
            "municipio",
            municipio_key,
        )

        entities[imovel_id] = {
            "id": imovel_id,
            "name": clean_value(row.get("denominacao"))
            or f"Imóvel {codigo}",
            "type": "ImovelRural",
            "properties": {
                "codigo_sncr": codigo,
                "denominacao": clean_value(
                    row.get("denominacao")
                ),
                "area_total": clean_value(
                    row.get("area_total")
                ),
            },
        }

        entities[municipio_id] = {
            "id": municipio_id,
            "name": municipio_nome,
            "type": "Municipio",
            "properties": {
                "codigo_ibge": municipio_codigo,
                "nome": municipio_nome,
                "uf": uf,
            },
        }

        relationships[
            ("LOCALIZADO_EM", imovel_id, municipio_id)
        ] = {
            "type": "LOCALIZADO_EM",
            "source_type": "ImovelRural",
            "target_type": "Municipio",
            "source_id": imovel_id,
            "target_id": municipio_id,
        }

        relationships[
            ("EXTRAIDO_DE", imovel_id, document_id)
        ] = {
            "type": "EXTRAIDO_DE",
            "source_type": "ImovelRural",
            "target_type": "Documento",
            "source_id": imovel_id,
            "target_id": document_id,
        }

        titular = clean_value(row.get("titular"))

        detentor_id = generate_id(
            "detentor",
            f"{source_name}:{index}",
        )

        detencao_id = generate_id(
            "detencao",
            f"{source_name}:{index}",
        )

        entities[detentor_id] = {
            "id": detentor_id,
            "name": titular or f"Detentor não identificado - linha {index}",
            "type": "Detentor",
            "properties": {
                "identificador": detentor_id,
                "nome": titular,
                "natureza_juridica": clean_value(
                    row.get("natureza_juridica")
                ),
            },
        }

        entities[detencao_id] = {
            "id": detencao_id,
            "name": f"Detenção {codigo} - linha {index}",
            "type": "RegistroDetencao",
            "properties": {
                "condicao_pessoa": clean_value(
                    row.get("condicao_pessoa")
                ),
                "percentual_detencao": clean_value(
                    row.get("percentual_detencao")
                ),
            },
        }

        relationships[
            ("POSSUI_DETENCAO", imovel_id, detencao_id)
        ] = {
            "type": "POSSUI_DETENCAO",
            "source_type": "ImovelRural",
            "target_type": "RegistroDetencao",
            "source_id": imovel_id,
            "target_id": detencao_id,
        }

        relationships[
            ("REFERENTE_A", detencao_id, detentor_id)
        ] = {
            "type": "REFERENTE_A",
            "source_type": "RegistroDetencao",
            "target_type": "Detentor",
            "source_id": detencao_id,
            "target_id": detentor_id,
        }

    return {
        "entities": list(entities.values()),
        "relationships": list(relationships.values()),
    }

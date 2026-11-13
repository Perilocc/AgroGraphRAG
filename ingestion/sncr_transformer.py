import hashlib
import pandas as pd
from graph.ontology import normalize_text


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


def _build_detentor_id(
    titular: str | None,
    natureza_juridica: str | None,
    source_name: str,
    line_number: int,
) -> str:
    """
    Deduplica detentores apenas quando o nome estiver completo (sem máscara '*').
    Registros mascarados pelo INCRA mantêm chave determinística por linha global.
    """
    if titular and "*" not in titular:
        norm_name = normalize_text(titular)
        norm_nat = normalize_text(natureza_juridica or "")
        return generate_id("detentor", f"{norm_name}:{norm_nat}")

    return generate_id("detentor", f"{source_name}:{line_number}")


def transform_sncr(
    df: pd.DataFrame,
    source_name: str,
    start_index: int = 0,
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

    records = df.to_dict(orient="records")
    indices = list(df.index)

    for offset, (df_idx, row) in enumerate(zip(indices, records)):
        if isinstance(df_idx, int):
            line_number = df_idx + 2
        else:
            try:
                line_number = int(df_idx) + 2
            except (TypeError, ValueError):
                line_number = start_index + offset + 2

        codigo = clean_value(row.get("codigo_imovel"))
        if not codigo:
            continue

        imovel_id = generate_id("imovel", codigo)

        municipio_codigo = clean_value(row.get("codigo_municipio"))
        municipio_nome = clean_value(row.get("municipio"))
        uf = clean_value(row.get("uf"))

        if not municipio_nome:
            continue

        municipio_key = municipio_codigo or f"{municipio_nome}:{uf}"
        municipio_id = generate_id("municipio", municipio_key)

        entities[imovel_id] = {
            "id": imovel_id,
            "name": clean_value(row.get("denominacao")) or f"Imóvel {codigo}",
            "type": "ImovelRural",
            "properties": {
                "codigo_sncr": codigo,
                "denominacao": clean_value(row.get("denominacao")),
                "area_total": clean_value(row.get("area_total")),
            },
        }

        entities[municipio_id] = {
            "id": municipio_id,
            "name": municipio_nome,
            "type": "Municipio",
            "properties": {
                "codigo_ibge": municipio_codigo,
                "nome": municipio_nome,
                "nome_normalizado": normalize_text(municipio_nome),
                "uf": uf,
            },
        }

        relationships[("LOCALIZADO_EM", imovel_id, municipio_id)] = {
            "type": "LOCALIZADO_EM",
            "source_type": "ImovelRural",
            "target_type": "Municipio",
            "source_id": imovel_id,
            "target_id": municipio_id,
        }

        relationships[("EXTRAIDO_DE", imovel_id, document_id)] = {
            "type": "EXTRAIDO_DE",
            "source_type": "ImovelRural",
            "target_type": "Documento",
            "source_id": imovel_id,
            "target_id": document_id,
        }

        titular = clean_value(row.get("titular"))
        natureza_juridica = clean_value(row.get("natureza_juridica"))

        detentor_id = _build_detentor_id(
            titular=titular,
            natureza_juridica=natureza_juridica,
            source_name=source_name,
            line_number=line_number,
        )

        detencao_id = generate_id("detencao", f"{source_name}:{line_number}")

        entities[detentor_id] = {
            "id": detentor_id,
            "name": titular or f"Detentor não identificado - linha {line_number}",
            "type": "Detentor",
            "properties": {
                "identificador": detentor_id,
                "nome": titular,
                "natureza_juridica": natureza_juridica,
            },
        }

        entities[detencao_id] = {
            "id": detencao_id,
            "name": f"Detenção {codigo} - linha {line_number}",
            "type": "RegistroDetencao",
            "properties": {
                "condicao_pessoa": clean_value(row.get("condicao_pessoa")),
                "percentual_detencao": clean_value(row.get("percentual_detencao")),
            },
        }

        relationships[("POSSUI_DETENCAO", imovel_id, detencao_id)] = {
            "type": "POSSUI_DETENCAO",
            "source_type": "ImovelRural",
            "target_type": "RegistroDetencao",
            "source_id": imovel_id,
            "target_id": detencao_id,
        }

        relationships[("REFERENTE_A", detencao_id, detentor_id)] = {
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

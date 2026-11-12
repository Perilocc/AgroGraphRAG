ENTITIES = {
    "ImovelRural": {
        "description": "Imóvel rural cadastrado no SNCR.",
        "properties": [
            "codigo_sncr",
            "denominacao",
            "area_total",
        ],
    },
    "Municipio": {
        "description": "Município onde o imóvel rural está localizado.",
        "properties": [
            "codigo_ibge",
            "nome",
            "uf",
        ],
    },
    "Detentor": {
        "description": "Pessoa ou organização identificada como detentora no cadastro.",
        "properties": [
            "identificador",
            "nome",
            "natureza_juridica",
        ],
    },
    "RegistroDetencao": {
        "description": "Registro do vínculo entre um detentor e um imóvel.",
        "properties": [
            "condicao_pessoa",
            "percentual_detencao",
        ],
    },
    "Documento": {
        "description": "Fonte documental utilizada na construção do grafo.",
        "properties": [
            "nome",
            "origem",
        ],
    },
}


RELATIONSHIPS = {
    "LOCALIZADO_EM": {
        "source": "ImovelRural",
        "target": "Municipio",
    },
    "POSSUI_DETENCAO": {
        "source": "ImovelRural",
        "target": "RegistroDetencao",
    },
    "REFERENTE_A": {
        "source": "RegistroDetencao",
        "target": "Detentor",
    },
    "EXTRAIDO_DE": {
        "source": "ImovelRural",
        "target": "Documento",
    },
}


def validate_entity(entity: dict) -> bool:
    entity_type = entity.get("type")

    if entity_type not in ENTITIES:
        return False

    required = {"id", "name"}

    return required.issubset(entity.keys())


def validate_relationship(relationship: dict) -> bool:
    relation_type = relationship.get("type")

    if relation_type not in RELATIONSHIPS:
        return False

    definition = RELATIONSHIPS[relation_type]

    return (
        relationship.get("source_type") == definition["source"]
        and relationship.get("target_type") == definition["target"]
    )

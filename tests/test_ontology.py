from graph.ontology import (
    ENTITIES,
    RELATIONSHIPS,
    canonicalize_entity,
    normalize_text,
    sanitize_relation_type,
    validate_entity,
    validate_relationship,
)


def test_ontology_definitions():
    assert len(ENTITIES) == 15
    assert len(RELATIONSHIPS) == 5
    assert "CulturaAgricola" in ENTITIES
    assert "Praga" in ENTITIES
    assert "PraticaAgricola" in ENTITIES
    assert "PRODUZ" in RELATIONSHIPS
    assert "EXTRAIDO_DE" in RELATIONSHIPS


def test_valid_entity():
    entity = {
        "id": "123",
        "name": "Fazenda São João",
        "type": "ImovelRural",
    }

    assert validate_entity(entity) is True


def test_invalid_entity():
    entity = {
        "id": "123",
        "name": "Fazenda São João",
        "type": "Fazenda",
    }

    assert validate_entity(entity) is False


def test_valid_relationship():
    relationship = {
        "type": "LOCALIZADO_EM",
        "source_type": "ImovelRural",
        "target_type": "Municipio",
    }

    assert validate_relationship(relationship) is True


def test_extraido_de_allows_entities_and_trecho():
    assert validate_relationship({
        "type": "EXTRAIDO_DE",
        "source_type": "CulturaAgricola",
        "target_type": "Trecho",
    }) is True

    assert validate_relationship({
        "type": "EXTRAIDO_DE",
        "source_type": "ImovelRural",
        "target_type": "Documento",
    }) is True


def test_dynamic_llm_relationship_validation():
    assert validate_relationship({
        "type": "CONTROLA",
        "source_type": "PraticaAgricola",
        "target_type": "Praga",
    }) is True

    assert validate_relationship({
        "type": "relacionamento invalido",
        "source_type": "PraticaAgricola",
        "target_type": "Praga",
    }) is False


def test_invalid_relationship():
    relationship = {
        "type": "LOCALIZADO_EM",
        "source_type": "Detentor",
        "target_type": "Municipio",
    }

    assert validate_relationship(relationship) is False


def test_canonicalize_entity_and_synonyms():
    id_ibge, nome_ibge, tipo_ibge = canonicalize_entity("Milho (em grão)", "Cultura agrícola")
    id_pdf, nome_pdf, tipo_pdf = canonicalize_entity("Zea mays", "CulturaAgricola")

    assert id_ibge == id_pdf
    assert nome_ibge == "Milho"
    assert tipo_ibge == "CulturaAgricola"
    assert tipo_pdf == "CulturaAgricola"
    assert normalize_text("João Pessoa") == "joao pessoa"


def test_sanitize_relation_type():
    assert sanitize_relation_type("produzido em") == "PRODUZIDO_EM"
    assert sanitize_relation_type("EXTRAIDA_DE") == "EXTRAIDO_DE"
    assert sanitize_relation_type("controla-praga") == "CONTROLA_PRAGA"
    assert sanitize_relation_type("123") is None

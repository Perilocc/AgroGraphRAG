from graph.ontology import (
    ENTITIES,
    RELATIONSHIPS,
    validate_entity,
    validate_relationship,
)

def test_ontology_definitions():
    assert len(ENTITIES) == 5
    assert len(RELATIONSHIPS) == 4


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


def test_invalid_relationship():
    relationship = {
        "type": "LOCALIZADO_EM",
        "source_type": "Detentor",
        "target_type": "Municipio",
    }

    assert validate_relationship(relationship) is False

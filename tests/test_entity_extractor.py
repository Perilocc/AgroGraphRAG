
from ingestion.entity_extractor import extract_knowledge
from unittest.mock import patch, MagicMock

def test_extract_knowledge():
    fake_response = MagicMock()

    fake_response.choices[0].message.content = """
    {
        "entities": [
            {
                "name": "Milho",
                "type": "Cultura agrícola",
                "description": "Cultura agrícola."
            },
            {
                "name": "Paraíba",
                "type": "Estado",
                "description": "Estado brasileiro."
            }
        ],
        "relations": [
            {
                "source": "Milho",
                "target": "Paraíba",
                "type": "PRODUZIDO_EM"
            }
        ]
    }
    """

    with patch(
        "ingestion.entity_extractor.client.chat.completions.create",
        return_value=fake_response,
    ):
        result = extract_knowledge(
            "O milho é produzido na Paraíba.",
            "trecho-teste-001",
        )

    assert len(result["entities"]) == 2
    assert len(result["relations"]) == 1

    assert (
        result["relations"][0]["tipo"]
        == "PRODUZIDO_EM"
    )

    assert (
        result["entities"][0]["trecho_id"]
        == "trecho-teste-001"
    )

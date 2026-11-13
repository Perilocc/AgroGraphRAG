from unittest.mock import patch
from ingestion.pipeline import ingest_pdf, resolve_semantic_duplicates


def test_ingest_pdf(tmp_path):
    pdf_path = tmp_path / "teste.pdf"
    pdf_path.touch()

    fake_pages = [
        {
            "page": 1,
            "text": "O cultivo de milho é importante para o Brasil.",
            "needs_ocr": False,
        }
    ]

    fake_chunk_embedding = [[0.01] * 1536]
    fake_entity_embeddings = [[0.02] * 1536]

    fake_knowledge = {
        "entities": [
            {
                "id": "ent-milho",
                "nome": "Milho",
                "tipo": "CulturaAgricola",
                "descricao": "Cultura de grãos.",
                "trecho_id": "chunk-1",
            }
        ],
        "relations": [],
        "unresolved_municipalities": [],
    }

    with (
        patch(
            "ingestion.pipeline.read_document",
            return_value={
                "type": "pdf",
                "content": fake_pages,
            },
        ),
        patch(
            "ingestion.pipeline.generate_embeddings",
            side_effect=[fake_chunk_embedding, fake_entity_embeddings],
        ),
        patch(
            "ingestion.pipeline.save_chunks",
            return_value=1,
        ),
        patch(
            "ingestion.pipeline.get_pb_municipios_map",
            return_value={},
        ),
        patch(
            "ingestion.pipeline.extract_knowledge",
            return_value=fake_knowledge,
        ),
        patch(
            "ingestion.pipeline.find_similar_existing_entities",
            return_value=[],
        ),
        patch(
            "ingestion.pipeline.save_knowledge",
            return_value=1,
        ),
    ):
        result = ingest_pdf(pdf_path)

    assert result["chunks"] == 1
    assert result["saved"] == 1
    assert result["entities"] == 1
    assert result["relations"] == 0


def test_resolve_semantic_duplicates_cosine_and_llm():
    entities = [
        {
            "id": "e1",
            "nome": "Lagarta-do-cartucho",
            "tipo": "Praga",
            "descricao": "Praga do milho.",
            "trecho_id": "t1",
        },
        {
            "id": "e2",
            "nome": "Spodoptera frugiperda",
            "tipo": "Praga",
            "descricao": "Lepidóptero.",
            "trecho_id": "t1",
        },
    ]
    relations = [
        {
            "source_id": "e2",
            "target_id": "cult-milho",
            "tipo": "AFETA",
            "trecho_id": "t1",
        }
    ]

    # Vetores com similaridade ~0.82 (cai na faixa 0.75..0.90 -> confirma via LLM)
    vec_a = [1.0, 0.0, 0.0]
    vec_b = [0.82, 0.57, 0.0]

    with (
        patch("ingestion.pipeline.generate_embeddings", return_value=[vec_a, vec_b]),
        patch("ingestion.pipeline.find_similar_existing_entities", return_value=[]),
        patch(
            "ingestion.pipeline.confirm_entity_equivalence_llm",
            return_value=[("e2", "e1")],
        ),
    ):
        resolved_e, resolved_r, merges = resolve_semantic_duplicates(entities, relations)

    assert len(resolved_e) == 1
    assert resolved_e[0]["id"] == "e1"
    assert resolved_r[0]["source_id"] == "e1"
    assert len(merges) == 1

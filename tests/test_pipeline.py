from ingestion.pipeline import ingest_pdf
from unittest.mock import patch

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

    fake_embedding = [[0.01] * 1536]

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
            return_value=fake_embedding,
        ),
        patch(
            "ingestion.pipeline.save_chunks",
            return_value=1,
        ),
    ):
        result = ingest_pdf(pdf_path)

    assert result["chunks"] == 1
    assert result["saved"] == 1

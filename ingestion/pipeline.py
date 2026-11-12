from ingestion.entity_extractor import extract_knowledge
from retrieval.embeddings import generate_embeddings
from graph.repositories import save_knowledge
from ingestion.readers import read_document
from ingestion.chunking import chunk_pages
from graph.repositories import save_chunks
from pathlib import Path

def ingest_pdf(file_path: Path) -> dict:
    """Executa a ingestão completa de um PDF."""

    print(f"Processando: {file_path.name}")

    document = read_document(file_path)

    if document["type"] != "pdf":
        raise ValueError("Este pipeline aceita apenas PDFs.")

    chunks = chunk_pages(
        pages=document["content"],
        source=str(file_path.name),
    )

    if not chunks:
        return {
            "document": file_path.name,
            "chunks": 0,
            "saved": 0,
        }

    vectors = generate_embeddings([
        chunk["text"] for chunk in chunks
    ])

    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector

    saved = save_chunks(chunks)
    
    extracted_entities = 0
    extracted_relations = 0

    for chunk in chunks:
        knowledge = extract_knowledge(
            chunk["text"],
            chunk["id"]
        )

        save_knowledge(knowledge)

        extracted_entities += len(knowledge["entities"])
        extracted_relations += len(knowledge["relations"])

    return {
        "document": file_path.name,
        "chunks": len(chunks),
        "saved": saved,
        "entities": extracted_entities,
        "relations": extracted_relations
    }

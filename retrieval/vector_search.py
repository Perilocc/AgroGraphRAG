from retrieval.embeddings import generate_embeddings
from graph.connection import get_driver

def search_similar_chunks(query_text: str, top_k: int = 5) -> list[dict]:

    if not query_text or not query_text.strip():
        raise ValueError("A consulta não pode ser vazia.")

    if top_k <= 0:
        raise ValueError("top_k deve ser maior que zero.")

    embedding = generate_embeddings([query_text])[0]

    query = """
    CALL db.index.vector.queryNodes(
        'trecho_embedding',
        $top_k,
        $embedding
    )
    YIELD node, score

    OPTIONAL MATCH (d:Documento)-[:CONTEM]->(node)

    RETURN
        node.id AS trecho_id,
        node.texto AS texto,
        node.pagina AS pagina,
        d.id AS documento_id,
        score

    ORDER BY score DESC
    """

    driver = get_driver()

    try:
        with driver.session() as session:
            result = session.run(
                query,
                top_k=top_k,
                embedding=embedding,
            )

            return [record.data() for record in result]

    finally:
        driver.close()
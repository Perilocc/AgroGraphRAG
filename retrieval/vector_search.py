import re
from graph.connection import get_driver, get_session
from retrieval.embeddings import generate_embeddings

LUCENE_SPECIAL = re.compile(r'([+\-&|!(){}[\]^"~*?:\\/])')


def _escape_lucene_query(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    tokens = [LUCENE_SPECIAL.sub(r"\\\1", tok) for tok in cleaned.split() if len(tok) > 1]
    return " OR ".join(tokens) if tokens else LUCENE_SPECIAL.sub(r"\\\1", cleaned)


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
        coalesce(d.nome, node.fonte, 'Documento') AS fonte,
        score

    ORDER BY score DESC
    """

    driver = get_driver()

    with get_session(driver) as session:
        try:
            result = session.run(
                query,
                top_k=top_k,
                embedding=embedding,
            )
            return [record.data() for record in result]
        except Exception:
            return []


def search_fulltext_chunks(query_text: str, top_k: int = 5) -> list[dict]:
    """Busca lexical BM25 no índice fulltext trecho_busca."""
    if not query_text or not query_text.strip() or top_k <= 0:
        return []

    lucene_q = _escape_lucene_query(query_text)
    if not lucene_q:
        return []

    query = """
    CALL db.index.fulltext.queryNodes('trecho_busca', $lucene_q)
    YIELD node, score
    OPTIONAL MATCH (d:Documento)-[:CONTEM]->(node)
    RETURN
        node.id AS trecho_id,
        node.texto AS texto,
        node.pagina AS pagina,
        d.id AS documento_id,
        coalesce(d.nome, node.fonte, 'Documento') AS fonte,
        score
    ORDER BY score DESC
    LIMIT $top_k
    """

    driver = get_driver()

    with get_session(driver) as session:
        try:
            result = session.run(query, lucene_q=lucene_q, top_k=top_k)
            return [record.data() for record in result]
        except Exception:
            return []


def search_entities_hybrid(
    query_text: str,
    top_k: int = 6,
    query_embedding: list[float] | None = None,
) -> list[dict]:
    """
    Combina busca vetorial (entidade_embedding) e fulltext (entidade_busca)
    apenas sobre nós agronômicos e municípios, ignorando nós SNCR de alta cardinalidade.
    """
    if not query_text or not query_text.strip() or top_k <= 0:
        return []

    embedding = query_embedding or generate_embeddings([query_text])[0]
    lucene_q = _escape_lucene_query(query_text)

    vec_query = """
    CALL db.index.vector.queryNodes('entidade_embedding', $candidate_k, $embedding)
    YIELD node, score
    WHERE NOT node:ImovelRural AND NOT node:RegistroDetencao AND NOT node:Detentor AND NOT node:Documento
    RETURN node.id AS id, node.nome AS nome, node.tipo AS tipo, node.descricao AS descricao, score
    ORDER BY score DESC
    LIMIT $top_k
    """

    ft_query = """
    CALL db.index.fulltext.queryNodes('entidade_busca', $lucene_q)
    YIELD node, score
    WHERE NOT node:ImovelRural AND NOT node:RegistroDetencao AND NOT node:Detentor AND NOT node:Documento
    RETURN node.id AS id, node.nome AS nome, node.tipo AS tipo, node.descricao AS descricao, score
    ORDER BY score DESC
    LIMIT $top_k
    """

    combined: dict[str, dict] = {}
    driver = get_driver()

    with get_session(driver) as session:
        try:
            vec_rows = [
                r.data()
                for r in session.run(
                    vec_query,
                    candidate_k=max(top_k * 4, 15),
                    embedding=embedding,
                    top_k=top_k,
                )
            ]
        except Exception:
            vec_rows = []

        try:
            ft_rows = (
                [
                    r.data()
                    for r in session.run(ft_query, lucene_q=lucene_q, top_k=top_k)
                ]
                if lucene_q
                else []
            )
        except Exception:
            ft_rows = []

    max_ft = max((float(r["score"]) for r in ft_rows), default=1.0) or 1.0

    for row in vec_rows:
        combined[row["id"]] = {
            **row,
            "vector_score": float(row["score"]),
            "fulltext_score": 0.0,
            "hybrid_score": 0.65 * float(row["score"]),
        }

    for row in ft_rows:
        norm_ft = float(row["score"]) / max_ft
        if row["id"] in combined:
            combined[row["id"]]["fulltext_score"] = norm_ft
            combined[row["id"]]["hybrid_score"] += 0.35 * norm_ft
        else:
            combined[row["id"]] = {
                **row,
                "vector_score": 0.0,
                "fulltext_score": norm_ft,
                "hybrid_score": 0.35 * norm_ft,
            }

    ranked = sorted(
        combined.values(),
        key=lambda item: item["hybrid_score"],
        reverse=True,
    )
    return ranked[:top_k]

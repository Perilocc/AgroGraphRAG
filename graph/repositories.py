import hashlib
from graph.connection import get_driver, get_session
from graph.ontology import (
    canonicalize_entity_type,
    normalize_text,
    sanitize_relation_type,
)

_pb_municipios_cache: dict[str, str] | None = None


def invalidate_pb_municipios_cache():
    """Limpa o cache em memória de municípios da Paraíba."""
    global _pb_municipios_cache
    _pb_municipios_cache = None


def ensure_municipio_normalized_names() -> int:
    """Popula m.nome_normalizado em nós :Municipio existentes (idempotente)."""
    driver = get_driver()

    select_query = """
    MATCH (m:Municipio)
    WHERE m.nome_normalizado IS NULL AND m.nome IS NOT NULL
    RETURN m.id AS id, m.nome AS nome
    """

    update_query = """
    UNWIND $rows AS row
    MATCH (m:Municipio {id: row.id})
    SET m.nome_normalizado = row.nome_normalizado
    RETURN count(m) AS total
    """

    with get_session(driver) as session:
        records = list(session.run(select_query))
        if not records:
            return 0

        rows = [
            {
                "id": record["id"],
                "nome_normalizado": normalize_text(record["nome"]),
            }
            for record in records
        ]
        result = session.run(update_query, rows=rows).single()
        invalidate_pb_municipios_cache()
        return result["total"] if result else 0


def get_pb_municipios_map(force_refresh: bool = False) -> dict[str, str]:
    """Retorna {nome_normalizado: id} para todos os municípios PB no Neo4j."""
    global _pb_municipios_cache

    if _pb_municipios_cache is not None and not force_refresh:
        return _pb_municipios_cache

    ensure_municipio_normalized_names()
    driver = get_driver()

    query = """
    MATCH (m:Municipio {uf: 'PB'})
    WHERE m.nome_normalizado IS NOT NULL
    RETURN m.nome_normalizado AS nome_normalizado, m.id AS id
    """

    with get_session(driver) as session:
        result = session.run(query)
        mapping = {
            record["nome_normalizado"]: record["id"]
            for record in result
        }

    _pb_municipios_cache = mapping
    return mapping


def clean_knowledge_subgraph() -> dict:
    """
    Remove trechos, documentos não-SNCR, relações :RELACIONA legadas
    e entidades agronômicas antigas antes da reingestão limpa.
    Preserva integralmente o subgrafo SNCR (inclusive Documento SNCR).
    """
    queries = {
        "relacoes_legadas": """
            MATCH ()-[r:RELACIONA]->()
            CALL (r) { DELETE r } IN TRANSACTIONS OF 1000 ROWS
        """,
        "trechos": """
            MATCH (t:Trecho)
            CALL (t) { DETACH DELETE t } IN TRANSACTIONS OF 1000 ROWS
        """,
        "documentos_nao_sncr": """
            MATCH (d:Documento)
            WHERE d.origem IS NULL OR d.origem <> 'SNCR'
            CALL (d) { DETACH DELETE d } IN TRANSACTIONS OF 1000 ROWS
        """,
        "entidades_conhecimento": """
            MATCH (e:Entidade)
            WHERE NOT (
                e:ImovelRural OR e:Municipio OR e:RegistroDetencao OR e:Detentor
                OR (e:Documento AND e.origem = 'SNCR')
            )
            CALL (e) { DETACH DELETE e } IN TRANSACTIONS OF 1000 ROWS
        """,
    }

    driver = get_driver()
    stats = {}

    with get_session(driver) as session:
        for name, query in queries.items():
            summary = session.run(query).consume()
            counters = summary.counters
            stats[name] = {
                "nodes_deleted": counters.nodes_deleted,
                "relationships_deleted": counters.relationships_deleted,
            }

    return stats


def save_chunks(chunks: list[dict]) -> int:
    """
    Salva documentos de PDF e seus trechos no Neo4j.
    Cada chunk deve conter: id, text, source, page e embedding.
    """
    if not chunks:
        return 0

    query = """
        UNWIND $chunks AS item

        MERGE (d:Documento {id: item.document_id})
        ON CREATE SET d.nome = item.source, d.origem = 'Embrapa'
        ON MATCH SET d.nome = coalesce(d.nome, item.source)

        MERGE (t:Trecho {id: item.id})
        SET
            t.texto = item.text,
            t.pagina = item.page,
            t.fonte = item.source,
            t.embedding = item.embedding

        MERGE (d)-[:CONTEM]->(t)

        RETURN count(t) AS total
    """

    prepared_chunks = []

    for chunk in chunks:
        required = ["id", "text", "source", "page", "embedding"]

        if any(key not in chunk for key in required):
            raise ValueError("Chunk contém campos obrigatórios ausentes.")

        document_id = hashlib.sha256(
            chunk["source"].encode("utf-8")
        ).hexdigest()

        prepared_chunks.append({
            **chunk,
            "document_id": document_id,
        })

    driver = get_driver()

    with get_session(driver) as session:
        result = session.run(query, chunks=prepared_chunks)
        record = result.single()
        return record["total"] if record else 0


def save_knowledge(knowledge: dict) -> int:
    """
    Salva entidades com labels PascalCase nativos, embeddings opcionais,
    evidência EXTRAIDO_DE para Trecho e relacionamentos tipados no Neo4j.
    """
    entities = knowledge.get("entities", [])
    relations = knowledge.get("relations", [])

    entities_by_type: dict[str, list[dict]] = {}
    for item in entities:
        canonical_type = canonicalize_entity_type(item.get("tipo", ""))
        if not canonical_type:
            continue
        sanitized = {
            **item,
            "tipo": canonical_type,
        }
        entities_by_type.setdefault(canonical_type, []).append(sanitized)

    relations_by_type: dict[str, list[dict]] = {}
    for item in relations:
        rel_type = sanitize_relation_type(item.get("tipo", ""))
        if not rel_type:
            continue
        relations_by_type.setdefault(rel_type, []).append({
            **item,
            "tipo": rel_type,
        })

    driver = get_driver()

    with get_session(driver) as session:
        for label, group in entities_by_type.items():
            # Label validado contra a whitelist ENTITIES da ontologia
            if label == "Municipio":
                # Apenas conecta Municipio existente ao Trecho sem criar duplicatas
                mun_query = """
                UNWIND $entities AS item
                MATCH (e:Entidade:Municipio {id: item.id})
                WITH item, e
                MATCH (t:Trecho {id: item.trecho_id})
                MERGE (e)-[:EXTRAIDO_DE]->(t)
                RETURN count(e) AS total
                """
                session.run(mun_query, entities=group).consume()
                continue

            entity_query = f"""
            UNWIND $entities AS item

            MERGE (e:Entidade {{id: item.id}})
            SET e:{label}
            SET
                e.nome = item.nome,
                e.tipo = item.tipo,
                e.descricao = item.descricao
            FOREACH (_ IN CASE WHEN item.embedding IS NOT NULL THEN [1] ELSE [] END |
                SET e.embedding = item.embedding
            )

            WITH item, e
            MATCH (t:Trecho {{id: item.trecho_id}})
            MERGE (e)-[:EXTRAIDO_DE]->(t)

            RETURN count(e) AS total
            """
            session.run(entity_query, entities=group).consume()

        for rel_type, group in relations_by_type.items():
            # rel_type validado por sanitize_relation_type (^[A-Z][A-Z0-9_]*$)
            rel_query = f"""
            UNWIND $relations AS item

            MATCH (source:Entidade {{id: item.source_id}})
            MATCH (target:Entidade {{id: item.target_id}})

            MERGE (source)-[r:{rel_type}]->(target)
            SET r.trecho_id = item.trecho_id

            RETURN count(r) AS total
            """
            session.run(rel_query, relations=group).consume()

    return len(entities) + len(relations)


def find_similar_existing_entities(
    entity_type: str,
    embedding: list[float],
    top_k: int = 3,
    min_score: float = 0.75,
) -> list[dict]:
    """Busca entidades já persistidas no Neo4j do mesmo tipo via índice vetorial."""
    canonical_type = canonicalize_entity_type(entity_type)
    if not canonical_type or not embedding:
        return []

    query = """
    CALL db.index.vector.queryNodes(
        'entidade_embedding',
        $candidate_k,
        $embedding
    )
    YIELD node, score
    WHERE node.tipo = $entity_type AND score >= $min_score
    RETURN node.id AS id, node.nome AS nome, node.tipo AS tipo, score
    ORDER BY score DESC
    LIMIT $top_k
    """

    driver = get_driver()
    with get_session(driver) as session:
        try:
            result = session.run(
                query,
                candidate_k=max(top_k * 5, 10),
                embedding=embedding,
                entity_type=canonical_type,
                min_score=min_score,
                top_k=top_k,
            )
            return [record.data() for record in result]
        except Exception:
            return []


def save_sncr_graph(graph_data: dict, batch_size: int = 1000) -> dict:
    entities = graph_data.get("entities", [])
    relationships = graph_data.get("relationships", [])

    if batch_size <= 0:
        raise ValueError("batch_size deve ser maior que zero.")

    entity_query = """
    UNWIND $entities AS item
    MERGE (n:Entidade {id: item.id})
    SET n:$(item.type)
    SET
        n.nome = item.name,
        n.tipo = item.type,
        n += item.properties
    RETURN count(n) AS total
    """

    relationship_query = """
    UNWIND $relationships AS item
    MATCH (source:Entidade {id: item.source_id})
    MATCH (target:Entidade {id: item.target_id})
    MERGE (source)-[r:$(item.type)]->(target)
    SET
        r.origem_tipo = item.source_type,
        r.destino_tipo = item.target_type
    RETURN count(r) AS total
    """

    total_entities = 0
    total_relationships = 0

    driver = get_driver()

    with get_session(driver) as session:
        for start in range(0, len(entities), batch_size):
            batch = entities[start:start + batch_size]

            result = session.run(
                entity_query,
                entities=batch,
            ).single()

            if result:
                total_entities += result["total"]

        for start in range(0, len(relationships), batch_size):
            batch = relationships[start:start + batch_size]

            result = session.run(
                relationship_query,
                relationships=batch,
            ).single()

            if result:
                total_relationships += result["total"]

    invalidate_pb_municipios_cache()

    return {
        "entities": total_entities,
        "relationships": total_relationships,
    }

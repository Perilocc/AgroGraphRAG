from graph.connection import get_driver
import hashlib


def save_chunks(chunks: list[dict]) -> int:
    """
    Salva documentos e seus chunks no Neo4j.

    Cada chunk deve conter:
    id, text, source, page e embedding.
    """

    if not chunks:
        return 0

    query = """
        UNWIND $chunks AS item

        MERGE (d:Documento {id: item.document_id})
        ON CREATE SET d.nome = item.source

        MERGE (t:Trecho {id: item.id})
        SET
            t.texto = item.text,
            t.pagina = item.page,
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

    try:
        with driver.session() as session:
            result = session.run(
                query,
                chunks=prepared_chunks
            )

            record = result.single()
            return record["total"] if record else 0

    finally:
        driver.close()


def save_knowledge(knowledge: dict) -> int:
    """Salva entidades, relações e evidências no Neo4j."""

    query = """
    UNWIND $entities AS item

    MERGE (e:Entidade {id: item.id})
    SET
        e.nome = item.nome,
        e.tipo = item.tipo,
        e.descricao = item.descricao

    WITH item, e

    MATCH (t:Trecho {id: item.trecho_id})
    MERGE (e)-[:EXTRAIDA_DE]->(t)

    RETURN count(e) AS total
    """

    relation_query = """
    UNWIND $relations AS item

    MATCH (source:Entidade {id: item.source_id})
    MATCH (target:Entidade {id: item.target_id})

    MERGE (source)-[r:RELACIONA {
        tipo: item.tipo,
        trecho_id: item.trecho_id
    }]->(target)

    RETURN count(r) AS total
    """

    entities = knowledge.get("entities", [])
    relations = knowledge.get("relations", [])

    driver = get_driver()

    try:
        with driver.session() as session:
            if entities:
                session.run(
                    query,
                    entities=entities
                ).consume()

            if relations:
                session.run(
                    relation_query,
                    relations=relations
                ).consume()

        return len(entities) + len(relations)

    finally:
        driver.close()



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

    try:
        with driver.session() as session:

            for start in range(0, len(entities), batch_size):
                batch = entities[start:start + batch_size]

                result = session.run(
                    entity_query,
                    entities=batch
                ).single()

                if result:
                    total_entities += result["total"]

            for start in range(0, len(relationships), batch_size):
                batch = relationships[start:start + batch_size]

                result = session.run(
                    relationship_query,
                    relationships=batch
                ).single()

                if result:
                    total_relationships += result["total"]

        return {
            "entities": total_entities,
            "relationships": total_relationships,
        }

    finally:
        driver.close()




from graph.connection import get_driver


CONSTRAINTS = [
    """
    CREATE CONSTRAINT entidade_id IF NOT EXISTS
    FOR (e:Entidade)
    REQUIRE e.id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT documento_id IF NOT EXISTS
    FOR (d:Documento)
    REQUIRE d.id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT trecho_id IF NOT EXISTS
    FOR (t:Trecho)
    REQUIRE t.id IS UNIQUE
    """,
]

INDEXES = [
    """
    CREATE FULLTEXT INDEX entidade_busca IF NOT EXISTS
    FOR (e:Entidade)
    ON EACH [e.nome, e.descricao]
    """,
    """
    CREATE VECTOR INDEX trecho_embedding IF NOT EXISTS
    FOR (t:Trecho)
    ON t.embedding
    OPTIONS {
        indexConfig: {
            `vector.dimensions`: 1536,
            `vector.similarity_function`: 'cosine'
        }
    }
    """,
]


def create_schema():
    driver = get_driver()

    try:
        with driver.session() as session:
            for query in CONSTRAINTS + INDEXES:
                session.run(query).consume()

        print("Esquema do grafo criado com sucesso!")

    finally:
        driver.close()

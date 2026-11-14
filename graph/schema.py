from graph.connection import get_driver, get_session


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
    """
    CREATE CONSTRAINT municipio_codigo_ibge IF NOT EXISTS
    FOR (m:Municipio)
    REQUIRE m.codigo_ibge IS UNIQUE
    """,
]

INDEXES = [
    """
    CREATE INDEX municipio_nome_uf IF NOT EXISTS
    FOR (m:Municipio)
    ON (m.nome_normalizado, m.uf)
    """,
    """
    CREATE INDEX imovel_codigo_sncr IF NOT EXISTS
    FOR (i:ImovelRural)
    ON (i.codigo_sncr)
    """,
    """
    CREATE INDEX imovel_area_total IF NOT EXISTS
    FOR (i:ImovelRural)
    ON (i.area_total)
    """,
    """
    CREATE INDEX entidade_tipo IF NOT EXISTS
    FOR (e:Entidade)
    ON (e.tipo)
    """,
    """
    CREATE INDEX entidade_nome IF NOT EXISTS
    FOR (e:Entidade)
    ON (e.nome)
    """,
    """
    CREATE FULLTEXT INDEX entidade_busca IF NOT EXISTS
    FOR (e:Entidade)
    ON EACH [e.nome, e.descricao]
    """,
    """
    CREATE FULLTEXT INDEX trecho_busca IF NOT EXISTS
    FOR (t:Trecho)
    ON EACH [t.texto]
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
    """
    CREATE VECTOR INDEX entidade_embedding IF NOT EXISTS
    FOR (e:Entidade)
    ON e.embedding
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

    with get_session(driver) as session:
        for query in CONSTRAINTS + INDEXES:
            session.run(query).consume()

    print("Esquema do grafo criado com sucesso!")

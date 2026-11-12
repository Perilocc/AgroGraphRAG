from graph.connection import get_driver

def get_imoveis_por_municipio(limit: int = 10) -> list[dict]:
    if limit <= 0:
        raise ValueError("limit deve ser maior que zero.")

    query = """
    MATCH (i:Entidade:ImovelRural)-[:LOCALIZADO_EM]->
        (m:Entidade:Municipio)

    RETURN
        m.codigo_ibge AS codigo_ibge,
        m.nome AS municipio,
        m.uf AS uf,
        count(DISTINCT i) AS total_imoveis,
        sum(i.area_total) AS area_total_cadastrada

    ORDER BY total_imoveis DESC
    LIMIT $limit
    """

    driver = get_driver()

    try:
        with driver.session() as session:
            result = session.run(query, limit=limit)
            return [record.data() for record in result]
    finally:
        driver.close()


def get_imoveis_por_area(min_area: float, limit: int = 20) -> list[dict]:
    if min_area < 0:
        raise ValueError("min_area não pode ser negativa.")

    if limit <= 0:
        raise ValueError("limit deve ser maior que zero.")

    query = """
    MATCH (i:Entidade:ImovelRural)-[:LOCALIZADO_EM]->
        (m:Entidade:Municipio)

    WHERE i.area_total >= $min_area

    RETURN
        i.codigo_sncr AS codigo_sncr,
        i.denominacao AS denominacao,
        i.area_total AS area_total,
        m.nome AS municipio,
        m.uf AS uf

    ORDER BY area_total DESC
    LIMIT $limit
    """

    driver = get_driver()

    try:
        with driver.session() as session:
            result = session.run(
                query,
                min_area=min_area,
                limit=limit,
            )
            return [record.data() for record in result]
    finally:
        driver.close()


def get_imoveis_com_detentores(codigo_municipio: str, limit: int = 20) -> list[dict]:

    if not codigo_municipio:
        raise ValueError("codigo_municipio é obrigatório.")

    if limit <= 0:
        raise ValueError("limit deve ser maior que zero.")

    query = """
    MATCH (i:Entidade:ImovelRural)-[:LOCALIZADO_EM]->
        (m:Entidade:Municipio)

    WHERE m.codigo_ibge = $codigo_municipio

    MATCH (i)-[:POSSUI_DETENCAO]->
        (r:Entidade:RegistroDetencao)
        -[:REFERENTE_A]->
        (d:Entidade:Detentor)

    RETURN
        i.codigo_sncr AS codigo_sncr,
        i.denominacao AS imovel,
        i.area_total AS area_total,
        m.nome AS municipio,
        d.nome AS detentor,
        d.natureza_juridica AS natureza_juridica,
        r.condicao_pessoa AS condicao_pessoa,
        r.percentual_detencao AS percentual_detencao

    ORDER BY i.denominacao
    LIMIT $limit
    """

    driver = get_driver()

    try:
        with driver.session() as session:
            result = session.run(
                query,
                codigo_municipio=codigo_municipio,
                limit=limit,
            )
            return [record.data() for record in result]
    finally:
        driver.close()


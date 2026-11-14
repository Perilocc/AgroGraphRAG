from graph.connection import get_driver, get_session


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

    with get_session(driver) as session:
        result = session.run(query, limit=limit)
        return [record.data() for record in result]


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

    with get_session(driver) as session:
        result = session.run(
            query,
            min_area=min_area,
            limit=limit,
        )
        return [record.data() for record in result]


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

    with get_session(driver) as session:
        result = session.run(
            query,
            codigo_municipio=codigo_municipio,
            limit=limit,
        )
        return [record.data() for record in result]


def _pick_node_group(labels: list[str]) -> str:
    """Seleciona o label mais específico do nó, evitando 'Entidade' quando houver outro."""
    specific = [lbl for lbl in labels if lbl != "Entidade"]
    return specific[0] if specific else (labels[0] if labels else "Entidade")


def _pick_node_title(props: dict, fallback_id: str) -> str:
    """Extrai um rótulo legível para exibição no grafo."""
    for key in ("denominacao", "nome", "titulo", "codigo_sncr", "codigo_ibge", "id"):
        val = props.get(key)
        if val:
            return str(val)
    return fallback_id


def get_subgraph(
    label: str | None = None,
    codigo_municipio: str | None = None,
    limit: int = 80,
) -> dict:
    """Retorna nós e arestas do Neo4j formatados para visualização (ex.: PyVis)."""
    if limit <= 0:
        raise ValueError("limit deve ser maior que zero.")

    if codigo_municipio:
        query = """
        MATCH (i:Entidade:ImovelRural)-[:LOCALIZADO_EM]->(m:Entidade:Municipio {codigo_ibge: $codigo_municipio})
        OPTIONAL MATCH (i)-[r1:POSSUI_DETENCAO]->(reg:Entidade:RegistroDetencao)-[r2:REFERENTE_A]->(d:Entidade:Detentor)
        WITH i, m, reg, d
        LIMIT $limit
        UNWIND [i, m, reg, d] AS n
        WITH DISTINCT n WHERE n IS NOT NULL
        OPTIONAL MATCH (n)-[rel]->(t)
        RETURN n, rel, t
        LIMIT $edge_limit
        """
        params = {"codigo_municipio": codigo_municipio, "limit": limit, "edge_limit": limit * 3}
    elif label and label != "Todos":
        query = f"""
        MATCH (n:`{label}`)
        WITH n LIMIT $limit
        OPTIONAL MATCH (n)-[rel]->(t)
        RETURN n, rel, t
        LIMIT $edge_limit
        """
        params = {"limit": limit, "edge_limit": limit * 3}
    else:
        query = """
        MATCH (n)-[rel]->(t)
        RETURN n, rel, t
        LIMIT $edge_limit
        """
        params = {"edge_limit": limit * 2}

    driver = get_driver()
    nodes_map: dict[str, dict] = {}
    edges_map: dict[tuple[str, str, str], dict] = {}

    with get_session(driver) as session:
        result = session.run(query, **params)
        for record in result:
            for node_key in ("n", "t"):
                node = record.get(node_key)
                if node is not None:
                    nid = str(node.element_id)
                    if nid not in nodes_map:
                        labels = list(node.labels)
                        props = dict(node)
                        nodes_map[nid] = {
                            "id": nid,
                            "label": _pick_node_title(props, nid),
                            "group": _pick_node_group(labels),
                            "labels": labels,
                            "properties": props,
                        }
            rel = record.get("rel")
            if rel is not None and record.get("n") is not None and record.get("t") is not None:
                src = str(record["n"].element_id)
                tgt = str(record["t"].element_id)
                rtype = str(rel.type)
                key = (src, tgt, rtype)
                if key not in edges_map:
                    edges_map[key] = {"source": src, "target": tgt, "type": rtype}

    return {"nodes": list(nodes_map.values()), "edges": list(edges_map.values())}


def get_distribuicao_condicoes_detencao() -> list[dict]:
    """Consulta 4: Distribuição das condições de detenção nos registros SNCR."""
    query = """
    MATCH (i:Entidade:ImovelRural)-[:POSSUI_DETENCAO]->
        (r:Entidade:RegistroDetencao)

    RETURN
        coalesce(r.condicao_pessoa, 'Não informado') AS condicao_pessoa,
        count(r) AS total_registros,
        count(DISTINCT i) AS total_imoveis,
        round(avg(coalesce(r.percentual_detencao, 0.0)), 2) AS percentual_medio_detencao

    ORDER BY total_registros DESC
    """

    driver = get_driver()

    with get_session(driver) as session:
        result = session.run(query)
        return [record.data() for record in result]


def get_imoveis_por_condicao_detencao(condicao: str, limit: int = 20) -> list[dict]:
    """Consulta 5: Imóveis rurais associados a determinada condição de detenção."""
    if not condicao or not condicao.strip():
        raise ValueError("condicao é obrigatória.")

    if limit <= 0:
        raise ValueError("limit deve ser maior que zero.")

    query = """
    MATCH (i:Entidade:ImovelRural)-[:POSSUI_DETENCAO]->
        (r:Entidade:RegistroDetencao)-[:REFERENTE_A]->(d:Entidade:Detentor)
    MATCH (i)-[:LOCALIZADO_EM]->(m:Entidade:Municipio)

    WHERE toLower(coalesce(r.condicao_pessoa, '')) CONTAINS toLower($condicao)

    RETURN
        i.codigo_sncr AS codigo_sncr,
        i.denominacao AS imovel,
        i.area_total AS area_total,
        m.nome AS municipio,
        m.uf AS uf,
        d.nome AS detentor,
        r.condicao_pessoa AS condicao_pessoa,
        r.percentual_detencao AS percentual_detencao

    ORDER BY i.area_total DESC
    LIMIT $limit
    """

    driver = get_driver()

    with get_session(driver) as session:
        result = session.run(query, condicao=condicao.strip(), limit=limit)
        return [record.data() for record in result]


def get_producao_agricola_municipios(
    cultura: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Retorna os municípios da PB com maior produção agrícola (IBGE PAM)."""
    if limit <= 0:
        raise ValueError("limit deve ser maior que zero.")

    where_clause = ""
    params: dict = {"limit": limit}
    if cultura and cultura.strip() and cultura.strip() != "Todas":
        where_clause = "WHERE toLower(c.nome) = toLower($cultura)"
        params["cultura"] = cultura.strip()

    query = f"""
    MATCH (m:Entidade:Municipio)-[r:PRODUZ]->(c:Entidade:CulturaAgricola)
    {where_clause}
    RETURN
        m.codigo_ibge AS codigo_ibge,
        m.nome AS municipio,
        m.uf AS uf,
        c.nome AS cultura,
        r.ano AS ano,
        r.area_plantada_ha AS area_plantada_ha,
        r.quantidade_ton AS quantidade_ton
    ORDER BY coalesce(r.quantidade_ton, 0) DESC, coalesce(r.area_plantada_ha, 0) DESC
    LIMIT $limit
    """

    driver = get_driver()

    with get_session(driver) as session:
        result = session.run(query, **params)
        return [record.data() for record in result]


def get_resumo_grafo() -> dict:
    """Retorna contagens de nós por label e relacionamentos por tipo."""
    nodes_query = """
    CALL () {
        MATCH (n)
        UNWIND labels(n) AS label
        RETURN label, count(*) AS total
    }
    RETURN label, total
    ORDER BY total DESC
    """

    rels_query = """
    MATCH ()-[r]->()
    RETURN type(r) AS tipo, count(r) AS total
    ORDER BY total DESC
    """

    driver = get_driver()

    with get_session(driver) as session:
        nodes = [record.data() for record in session.run(nodes_query)]
        relationships = [record.data() for record in session.run(rels_query)]

    return {
        "labels": nodes,
        "relationships": relationships,
    }

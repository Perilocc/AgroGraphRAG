import networkx as nx
from graph.connection import get_driver, get_session


def fetch_agronomic_subgraph(
    node_ids: list[str] | None = None,
    limit: int = 500,
) -> tuple[list[dict], list[dict]]:
    """
    Carrega apenas nós e arestas do subgrafo agronômico/conhecimento,
    excluindo estritamente ImovelRural, RegistroDetencao, Detentor, Trecho e Documento.
    """
    driver = get_driver()

    if node_ids:
        query = """
        MATCH (a:Entidade)-[r]->(b:Entidade)
        WHERE a.id IN $node_ids AND b.id IN $node_ids
          AND NOT a:ImovelRural AND NOT a:RegistroDetencao AND NOT a:Detentor AND NOT a:Trecho AND NOT a:Documento
          AND NOT b:ImovelRural AND NOT b:RegistroDetencao AND NOT b:Detentor AND NOT b:Trecho AND NOT b:Documento
        RETURN
            a.id AS src_id, a.nome AS src_nome, a.tipo AS src_tipo, a.descricao AS src_desc,
            b.id AS tgt_id, b.nome AS tgt_nome, b.tipo AS tgt_tipo, b.descricao AS tgt_desc,
            type(r) AS rel_tipo
        LIMIT $limit
        """
        params = {"node_ids": node_ids, "limit": limit}
    else:
        query = """
        MATCH (a:Entidade)-[r]->(b:Entidade)
        WHERE NOT a:ImovelRural AND NOT a:RegistroDetencao AND NOT a:Detentor AND NOT a:Trecho AND NOT a:Documento
          AND NOT b:ImovelRural AND NOT b:RegistroDetencao AND NOT b:Detentor AND NOT b:Trecho AND NOT b:Documento
        RETURN
            a.id AS src_id, a.nome AS src_nome, a.tipo AS src_tipo, a.descricao AS src_desc,
            b.id AS tgt_id, b.nome AS tgt_nome, b.tipo AS tgt_tipo, b.descricao AS tgt_desc,
            type(r) AS rel_tipo
        LIMIT $limit
        """
        params = {"limit": limit}

    nodes_map: dict[str, dict] = {}
    edges: list[dict] = []

    with get_session(driver) as session:
        for rec in session.run(query, **params):
            row = rec.data()
            nodes_map[row["src_id"]] = {
                "id": row["src_id"],
                "nome": row["src_nome"],
                "tipo": row["src_tipo"],
                "descricao": row.get("src_desc") or "",
            }
            nodes_map[row["tgt_id"]] = {
                "id": row["tgt_id"],
                "nome": row["tgt_nome"],
                "tipo": row["tgt_tipo"],
                "descricao": row.get("tgt_desc") or "",
            }
            edges.append({
                "source_id": row["src_id"],
                "target_id": row["tgt_id"],
                "tipo": row["rel_tipo"],
            })

    return list(nodes_map.values()), edges


def compute_subgraph_pagerank(
    nodes: list[dict] | None = None,
    edges: list[dict] | None = None,
    top_k: int = 15,
) -> list[dict]:
    """Calcula PageRank apenas sobre o subgrafo recuperado ou agronômico."""
    if nodes is None or edges is None:
        nodes, edges = fetch_agronomic_subgraph()

    if not nodes:
        return []

    graph = nx.DiGraph()
    node_lookup = {}
    for node in nodes:
        nid = node["id"]
        node_lookup[nid] = node
        graph.add_node(nid)

    for edge in edges:
        src = edge.get("source_id")
        tgt = edge.get("target_id")
        if src in node_lookup and tgt in node_lookup:
            graph.add_edge(src, tgt, tipo=edge.get("tipo", ""))

    if graph.number_of_nodes() == 0:
        return []

    scores = (
        nx.pagerank(graph, alpha=0.85)
        if graph.number_of_edges() > 0
        else {nid: round(1.0 / len(nodes), 6) for nid in node_lookup}
    )

    ranked = []
    for nid, score in scores.items():
        item = dict(node_lookup[nid])
        item["pagerank"] = round(float(score), 6)
        ranked.append(item)

    ranked.sort(key=lambda x: x["pagerank"], reverse=True)
    return ranked[:top_k] if top_k > 0 else ranked


def detect_subgraph_communities(
    nodes: list[dict] | None = None,
    edges: list[dict] | None = None,
) -> list[dict]:
    """Detecta comunidades (Louvain) sobre o subgrafo agronômico."""
    if nodes is None or edges is None:
        nodes, edges = fetch_agronomic_subgraph()

    if not nodes:
        return []

    graph = nx.Graph()
    node_lookup = {}
    for node in nodes:
        nid = node["id"]
        node_lookup[nid] = node
        graph.add_node(nid)

    for edge in edges:
        src = edge.get("source_id")
        tgt = edge.get("target_id")
        if src in node_lookup and tgt in node_lookup:
            graph.add_edge(src, tgt)

    if graph.number_of_edges() == 0:
        communities = [{nid} for nid in node_lookup]
    else:
        communities = list(nx.community.louvain_communities(graph, seed=42))

    result = []
    for idx, comm in enumerate(
        sorted(communities, key=len, reverse=True),
        start=1,
    ):
        members = [node_lookup[nid] for nid in comm if nid in node_lookup]
        result.append({
            "community_id": idx,
            "size": len(members),
            "members": members,
        })

    return result


def find_shortest_path(
    source_id: str,
    target_id: str,
    max_hops: int = 4,
) -> dict:
    """
    Encontra o caminho mais curto entre duas entidades via Neo4j,
    bloqueando expansão através dos hubs SNCR (ImovelRural/RegistroDetencao/Detentor).
    """
    if not source_id or not target_id:
        raise ValueError("source_id e target_id são obrigatórios.")

    hops = max(1, min(int(max_hops), 6))

    query = f"""
    MATCH (a:Entidade {{id: $source_id}}), (b:Entidade {{id: $target_id}})
    WHERE NOT a:ImovelRural AND NOT a:RegistroDetencao AND NOT a:Detentor
      AND NOT b:ImovelRural AND NOT b:RegistroDetencao AND NOT b:Detentor
    MATCH path = SHORTEST 1 (a)
      (()-[r:!LOCALIZADO_EM&!POSSUI_DETENCAO&!REFERENTE_A&!CONTEM&!EXTRAIDO_DE]-(n:Entidade&!ImovelRural&!RegistroDetencao&!Detentor&!Trecho&!Documento)){{1,{hops}}}
      (b)
    RETURN
        [node IN nodes(path) | {{id: node.id, nome: node.nome, tipo: node.tipo, descricao: node.descricao}}] AS nodes,
        [rel IN relationships(path) | {{source_id: startNode(rel).id, target_id: endNode(rel).id, tipo: type(rel)}}] AS edges
    """

    driver = get_driver()

    with get_session(driver) as session:
        record = session.run(
            query,
            source_id=source_id,
            target_id=target_id,
        ).single()

    if not record:
        return {"found": False, "nodes": [], "edges": [], "hops": 0}

    data = record.data()
    return {
        "found": True,
        "nodes": data["nodes"],
        "edges": data["edges"],
        "hops": len(data["edges"]),
    }

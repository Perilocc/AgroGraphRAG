from graph.algorithms import compute_subgraph_pagerank
from graph.connection import get_driver, get_session
from retrieval.embeddings import generate_embeddings
from retrieval.vector_search import (
    search_entities_hybrid,
    search_fulltext_chunks,
    search_similar_chunks,
)


def _merge_chunks(vector_chunks: list[dict], fulltext_chunks: list[dict], top_k: int) -> list[dict]:
    merged: dict[str, dict] = {}
    max_ft = max((float(c["score"]) for c in fulltext_chunks), default=1.0) or 1.0

    for item in vector_chunks:
        tid = item["trecho_id"]
        merged[tid] = {
            **item,
            "vector_score": float(item["score"]),
            "fulltext_score": 0.0,
            "score": 0.75 * float(item["score"]),
        }

    for item in fulltext_chunks:
        tid = item["trecho_id"]
        norm_ft = float(item["score"]) / max_ft
        if tid in merged:
            merged[tid]["fulltext_score"] = norm_ft
            merged[tid]["score"] += 0.25 * norm_ft
        else:
            merged[tid] = {
                **item,
                "vector_score": 0.0,
                "fulltext_score": norm_ft,
                "score": 0.25 * norm_ft,
            }

    ranked = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]


def hybrid_retrieve(
    query_text: str,
    top_k: int = 5,
    max_hops: int = 2,
) -> dict:
    """
    Busca Híbrida + Travessia Multi-hop Anti-Hub + PageRank Local + Proveniência.
    """
    if not query_text or not query_text.strip():
        raise ValueError("A consulta não pode ser vazia.")

    hops = max(1, min(int(max_hops), 3))
    query_embedding = generate_embeddings([query_text])[0]

    # 1. Busca híbrida em trechos (Vetor + Fulltext)
    vec_chunks = search_similar_chunks(query_text, top_k=top_k)
    ft_chunks = search_fulltext_chunks(query_text, top_k=top_k)
    chunks = _merge_chunks(vec_chunks, ft_chunks, top_k=top_k)

    # 2. Ancoragem híbrida de entidades (Vetor + Fulltext)
    seed_entities = search_entities_hybrid(
        query_text,
        top_k=6,
        query_embedding=query_embedding,
    )

    chunk_ids = [c["trecho_id"] for c in chunks]
    driver = get_driver()

    # Entidades ligadas diretamente aos trechos recuperados também servem de semente
    chunk_seed_query = """
    UNWIND $chunk_ids AS cid
    MATCH (e:Entidade)-[:EXTRAIDO_DE]->(t:Trecho {id: cid})
    WHERE NOT e:ImovelRural AND NOT e:RegistroDetencao AND NOT e:Detentor AND NOT e:Documento
    RETURN DISTINCT e.id AS id, e.nome AS nome, e.tipo AS tipo, e.descricao AS descricao
    LIMIT 12
    """

    nodes_map: dict[str, dict] = {
        e["id"]: {
            "id": e["id"],
            "nome": e["nome"],
            "tipo": e["tipo"],
            "descricao": e.get("descricao") or "",
            "seed_score": round(float(e.get("hybrid_score", 0.0)), 4),
        }
        for e in seed_entities
    }

    with get_session(driver) as session:
        if chunk_ids:
            for rec in session.run(chunk_seed_query, chunk_ids=chunk_ids):
                row = rec.data()
                nodes_map.setdefault(
                    row["id"],
                    {
                        "id": row["id"],
                        "nome": row["nome"],
                        "tipo": row["tipo"],
                        "descricao": row.get("descricao") or "",
                        "seed_score": 0.25,
                    },
                )

        seed_ids = list(nodes_map.keys())
        edges_map: dict[tuple[str, str, str], dict] = {}
        paths_text: list[str] = []

        # 3. Travessia Multi-hop com filtro anti-hub inline no padrão quantificado
        if seed_ids:
            multihop_query = f"""
            UNWIND $seed_ids AS seed_id
            MATCH (e:Entidade {{id: seed_id}})
            WHERE NOT e:ImovelRural AND NOT e:RegistroDetencao AND NOT e:Detentor AND NOT e:Documento
            MATCH path = (e)
              (()-[r:!LOCALIZADO_EM&!POSSUI_DETENCAO&!REFERENTE_A&!CONTEM&!EXTRAIDO_DE]-(n:Entidade&!ImovelRural&!RegistroDetencao&!Detentor&!Trecho&!Documento)){{1,{hops}}}
              (v:Entidade&!ImovelRural&!RegistroDetencao&!Detentor&!Trecho&!Documento)
            RETURN
                [node IN nodes(path) | {{id: node.id, nome: node.nome, tipo: node.tipo, descricao: node.descricao}}] AS path_nodes,
                [rel IN relationships(path) | {{
                    source_id: startNode(rel).id,
                    source_nome: startNode(rel).nome,
                    target_id: endNode(rel).id,
                    target_nome: endNode(rel).nome,
                    tipo: type(rel),
                    ano: rel.ano,
                    area_plantada_ha: rel.area_plantada_ha,
                    quantidade_ton: rel.quantidade_ton
                }}] AS path_rels
            LIMIT 60
            """

            seen_paths = set()
            for rec in session.run(multihop_query, seed_ids=seed_ids):
                row = rec.data()
                for n in row["path_nodes"]:
                    nodes_map.setdefault(
                        n["id"],
                        {
                            "id": n["id"],
                            "nome": n["nome"],
                            "tipo": n["tipo"],
                            "descricao": n.get("descricao") or "",
                            "seed_score": 0.0,
                        },
                    )
                triples = []
                for rel in row["path_rels"]:
                    ekey = (rel["source_id"], rel["tipo"], rel["target_id"])
                    edges_map.setdefault(ekey, rel)
                    extra = ""
                    if rel.get("tipo") == "PRODUZ":
                        area = rel.get("area_plantada_ha")
                        ton = rel.get("quantidade_ton")
                        ano = rel.get("ano")
                        extra = f" (ano={ano}, area_ha={area}, ton={ton})"
                    triples.append(
                        f"[{rel['source_nome']}] --({rel['tipo']}{extra})--> [{rel['target_nome']}]"
                    )
                formatted = " | ".join(triples)
                if formatted and formatted not in seen_paths:
                    seen_paths.add(formatted)
                    paths_text.append(formatted)

        # 4. Proveniência documental em 2ª etapa (fora do path anti-hub)
        all_node_ids = list(nodes_map.keys())
        if all_node_ids:
            prov_query = """
            UNWIND $node_ids AS nid
            MATCH (e:Entidade {id: nid})-[:EXTRAIDO_DE]->(t:Trecho)<-[:CONTEM]-(d:Documento)
            RETURN DISTINCT
                t.id AS trecho_id,
                t.texto AS texto,
                t.pagina AS pagina,
                d.id AS documento_id,
                coalesce(d.nome, t.fonte, 'Documento') AS fonte
            LIMIT 15
            """
            existing_chunk_ids = {c["trecho_id"] for c in chunks}
            for rec in session.run(prov_query, node_ids=all_node_ids):
                pdata = rec.data()
                if pdata["trecho_id"] not in existing_chunk_ids:
                    existing_chunk_ids.add(pdata["trecho_id"])
                    chunks.append({
                        **pdata,
                        "score": 0.5,
                        "vector_score": 0.0,
                        "fulltext_score": 0.0,
                        "provenance_only": True,
                    })

        # 5. Agregação SNCR leve para municípios presentes no subgrafo
        municipio_ids = [
            nid for nid, ndata in nodes_map.items()
            if ndata.get("tipo") == "Municipio"
        ]
        sncr_aggregates = []
        if municipio_ids:
            sncr_agg_query = """
            UNWIND $mun_ids AS mid
            MATCH (m:Entidade:Municipio {id: mid})
            OPTIONAL MATCH (i:Entidade:ImovelRural)-[:LOCALIZADO_EM]->(m)
            RETURN
                m.nome AS municipio,
                m.uf AS uf,
                m.codigo_ibge AS codigo_ibge,
                count(DISTINCT i) AS imoveis_amostra_40k,
                round(sum(coalesce(i.area_total, 0.0)), 2) AS area_total_amostra_ha
            """
            sncr_aggregates = [
                rec.data()
                for rec in session.run(sncr_agg_query, mun_ids=municipio_ids)
            ]

    nodes_list = list(nodes_map.values())
    edges_list = list(edges_map.values())

    # 6. Enriquecimento com PageRank local no subgrafo recuperado
    ranked_nodes = compute_subgraph_pagerank(
        nodes=nodes_list,
        edges=edges_list,
        top_k=len(nodes_list),
    )
    pr_by_id = {n["id"]: n["pagerank"] for n in ranked_nodes}
    for n in nodes_list:
        n["pagerank"] = pr_by_id.get(n["id"], 0.0)
    nodes_list.sort(key=lambda x: (x.get("seed_score", 0.0) + x.get("pagerank", 0.0)), reverse=True)

    # Cálculo objetivo do nível de confiança (0.0 a 1.0)
    top_vec = max((c.get("vector_score", 0.0) for c in chunks), default=0.0)
    entity_cov = min(len(seed_entities) / 3.0, 1.0)
    path_cov = min(len(paths_text) / 5.0, 1.0)
    confidence = round(min(1.0, 0.45 * top_vec + 0.30 * entity_cov + 0.25 * path_cov), 4)

    return {
        "chunks": chunks,
        "nodes": nodes_list,
        "edges": edges_list,
        "paths": paths_text[:30],
        "sncr_aggregates": sncr_aggregates,
        "confidence": confidence,
        "seed_entities": seed_entities,
    }

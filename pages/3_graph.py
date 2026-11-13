import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from graph.algorithms import (
    compute_subgraph_pagerank,
    detect_subgraph_communities,
    fetch_agronomic_subgraph,
    find_shortest_path,
)
from graph.queries import (
    get_distribuicao_condicoes_detencao,
    get_imoveis_com_detentores,
    get_imoveis_por_area,
    get_imoveis_por_condicao_detencao,
    get_imoveis_por_municipio,
    get_producao_agricola_municipios,
    get_resumo_grafo,
)
from utils.graph_vis import render_interactive_graph

st.set_page_config(page_title="Explorador do Grafo", page_icon="🕸️", layout="wide")

st.title("🕸️ Explorador do Grafo & Algoritmos")
st.caption(
    "Métricas estruturais do Neo4j, consultas fundiárias/agrícolas e algoritmos de grafos "
    "(PageRank, Louvain e Shortest Path) aplicados sobre o subgrafo agronômico."
)
st.divider()

# Resumo geral do grafo
if st.button("🔄 Atualizar Estatísticas do Grafo"):
    st.session_state.pop("graph_summary", None)

if "graph_summary" not in st.session_state:
    try:
        st.session_state["graph_summary"] = get_resumo_grafo()
    except Exception as exc:
        st.error(f"Não foi possível consultar o Neo4j: {exc}")
        st.stop()

summary = st.session_state["graph_summary"]

col_l, col_r = st.columns(2)
with col_l:
    st.subheader("Nós por Rótulo (Labels)")
    labels_df = pd.DataFrame(summary.get("labels", []))
    if not labels_df.empty:
        st.dataframe(labels_df, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum nó encontrado no grafo.")

with col_r:
    st.subheader("Relacionamentos por Tipo")
    rels_df = pd.DataFrame(summary.get("relationships", []))
    if not rels_df.empty:
        st.dataframe(rels_df, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum relacionamento encontrado no grafo.")

st.divider()

tab_queries, tab_algos = st.tabs([
    "📊 Consultas Estruturadas (SNCR + IBGE)",
    "🧮 Algoritmos de Grafo (Subgrafo Agronômico)",
])

with tab_queries:
    st.info(
        "ℹ️ **Nota Metodológica:** As consultas fundiárias do SNCR-PB operam sobre a "
        "**amostra uniforme 1/6 (~39.500 registros)** respeitando o limite do Neo4j Aura Free. "
        "As estimativas expandidas (×6) são indicadas separadamente."
    )

    query_choice = st.selectbox(
        "Selecione a consulta analítica:",
        [
            "1. Quantidade e área de imóveis rurais por município",
            "2. Imóveis rurais com área superior a um limite (ha)",
            "3. Imóveis e detentores por código IBGE do município",
            "4. Distribuição das condições de detenção",
            "5. Imóveis por condição de detenção",
            "6. Produção agrícola municipal na Paraíba (IBGE PAM)",
        ],
    )

    if query_choice.startswith("1."):
        limit = st.slider("Top municípios", 5, 50, 15)
        if st.button("Executar Consulta 1"):
            rows = get_imoveis_por_municipio(limit=limit)
            df = pd.DataFrame(rows)
            if not df.empty:
                df["imoveis_estimados_total (x6)"] = df["total_imoveis"] * 6
                df["area_estimada_ha (x6)"] = (df["area_total_cadastrada"] * 6).round(2)
            st.dataframe(df, use_container_width=True, hide_index=True)

    elif query_choice.startswith("2."):
        c1, c2 = st.columns(2)
        min_area = c1.number_input("Área mínima (hectares)", min_value=0.0, value=500.0, step=100.0)
        limit = c2.slider("Limite de resultados", 5, 100, 20)
        if st.button("Executar Consulta 2"):
            rows = get_imoveis_por_area(min_area=min_area, limit=limit)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    elif query_choice.startswith("3."):
        c1, c2 = st.columns(2)
        cod_mun = c1.text_input("Código IBGE do município (ex.: 2507507 para João Pessoa)", value="2507507")
        limit = c2.slider("Limite", 5, 100, 20)
        if st.button("Executar Consulta 3"):
            rows = get_imoveis_com_detentores(codigo_municipio=cod_mun.strip(), limit=limit)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    elif query_choice.startswith("4."):
        if st.button("Executar Consulta 4"):
            rows = get_distribuicao_condicoes_detencao()
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    elif query_choice.startswith("5."):
        c1, c2 = st.columns(2)
        condicao = c1.text_input("Condição da pessoa (ex.: Proprietario, Posseiro, Condomino)", value="Proprietario")
        limit = c2.slider("Limite", 5, 100, 20)
        if st.button("Executar Consulta 5"):
            rows = get_imoveis_por_condicao_detencao(condicao=condicao, limit=limit)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    elif query_choice.startswith("6."):
        c1, c2 = st.columns(2)
        cultura = c1.selectbox("Cultura Agrícola", ["Todas", "Milho", "Soja", "Café"])
        limit = c2.slider("Top municípios", 5, 50, 20)
        if st.button("Executar Consulta IBGE"):
            rows = get_producao_agricola_municipios(cultura=cultura, limit=limit)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

with tab_algos:
    st.caption(
        "Executados exclusivamente sobre o subgrafo agronômico/conhecimento "
        "(excluindo nós SNCR de alta cardinalidade)."
    )

    algo_choice = st.radio(
        "Algoritmo:",
        ["PageRank (Centralidade)", "Comunidades (Louvain)", "Caminho Mais Curto (Shortest Path)"],
        horizontal=True,
    )

    if algo_choice == "PageRank (Centralidade)":
        top_k = st.slider("Top entidades centrais", 5, 40, 15)
        if st.button("▶️ Calcular PageRank"):
            with st.spinner("Calculando PageRank no subgrafo agronômico..."):
                nodes, edges = fetch_agronomic_subgraph(limit=400)
                ranked = compute_subgraph_pagerank(nodes=nodes, edges=edges, top_k=top_k)
                if not ranked:
                    st.warning("Subgrafo agronômico vazio. Execute a ingestão IBGE/PDFs primeiro.")
                else:
                    st.dataframe(
                        pd.DataFrame(ranked)[["nome", "tipo", "pagerank", "descricao"]],
                        use_container_width=True,
                        hide_index=True,
                    )
                    top_ids = {n["id"] for n in ranked}
                    sub_edges = [e for e in edges if e["source_id"] in top_ids and e["target_id"] in top_ids]
                    html = render_interactive_graph(ranked, sub_edges, height=500)
                    components.html(html, height=520, scrolling=False)

    elif algo_choice == "Comunidades (Louvain)":
        if st.button("▶️ Detectar Comunidades (Louvain)"):
            with st.spinner("Detectando comunidades no subgrafo agronômico..."):
                nodes, edges = fetch_agronomic_subgraph(limit=400)
                communities = detect_subgraph_communities(nodes=nodes, edges=edges)
                if not communities:
                    st.warning("Subgrafo agronômico vazio.")
                else:
                    comm_map = {}
                    rows = []
                    for comm in communities:
                        cid = comm["community_id"]
                        for m in comm["members"]:
                            comm_map[m["id"]] = cid
                        sample_names = ", ".join(m["nome"] for m in comm["members"][:8])
                        rows.append({
                            "Comunidade": f"Cluster #{cid}",
                            "Tamanho": comm["size"],
                            "Principais Entidades": sample_names,
                        })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    html = render_interactive_graph(nodes[:120], edges, height=520, community_map=comm_map)
                    components.html(html, height=540, scrolling=False)

    else:
        nodes, _ = fetch_agronomic_subgraph(limit=300)
        if len(nodes) < 2:
            st.warning("Carregue os dados do IBGE e PDFs para explorar caminhos no grafo.")
        else:
            sorted_nodes = sorted(nodes, key=lambda n: f"{n['nome']} ({n['tipo']})")
            c1, c2, c3 = st.columns([2, 2, 1])
            src_node = c1.selectbox(
                "Entidade de Origem",
                options=sorted_nodes,
                format_func=lambda n: f"{n['nome']} ({n['tipo']})",
            )
            tgt_node = c2.selectbox(
                "Entidade de Destino",
                options=sorted_nodes,
                index=min(1, len(sorted_nodes) - 1),
                format_func=lambda n: f"{n['nome']} ({n['tipo']})",
            )
            max_hops = c3.number_input("Máx. saltos", min_value=1, max_value=6, value=4)

            if st.button("🔎 Encontrar Caminho Mais Curto"):
                if src_node["id"] == tgt_node["id"]:
                    st.warning("Escolha duas entidades diferentes.")
                else:
                    with st.spinner("Executando SHORTEST PATH anti-hub..."):
                        res = find_shortest_path(src_node["id"], tgt_node["id"], max_hops=int(max_hops))
                        if not res["found"]:
                            st.info("Nenhum caminho encontrado dentro do limite de saltos.")
                        else:
                            st.success(f"Caminho encontrado em **{res['hops']} salto(s)**!")
                            html = render_interactive_graph(res["nodes"], res["edges"], height=420)
                            components.html(html, height=440, scrolling=False)
                            st.json(res["edges"])

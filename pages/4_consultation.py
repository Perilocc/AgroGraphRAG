import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from retrieval.kag_engine import answer_question
from ui import (
    apply_global_styles,
    render_confidence_badge,
    render_entity_legend,
    render_kpi_row,
    render_page_header,
)
from utils.graph_vis import render_interactive_graph

apply_global_styles()

render_page_header(
    title="Consulta Inteligente — GraphRAG & KAG",
    subtitle=(
        "Busca Híbrida (Vetorial + Fulltext + Travessia Multi-hop + PageRank + Text-to-Cypher) "
        "com rastreabilidade explícita e mitigação de alucinações."
    ),
    icon=":material/travel_explore:",
)

SUGGESTED_QUESTIONS = [
    "Quais municípios da Paraíba produzem milho e quais pragas afetam essa cultura segundo a Embrapa?",
    "Como controlar a lagarta-do-cartucho no milho e quais práticas agrícolas são recomendadas?",
    "Quais estratégias de manejo e rotação de culturas são recomendadas para a soja?",
    "Quais são os 5 municípios da Paraíba com maior área rural cadastrada na amostra SNCR e o que eles produzem?",
    "Quais práticas reduzem danos por percevejo-marrom na cultura da soja?",
]

with st.expander("Sugestões de perguntas multi-hop para demonstração", icon=":material/lightbulb:"):
    cols = st.columns(len(SUGGESTED_QUESTIONS))
    for idx, q in enumerate(SUGGESTED_QUESTIONS):
        if cols[idx].button(f"Exemplo {idx + 1}", key=f"ex_{idx}", use_container_width=True):
            st.session_state["question_input"] = q

with st.container(border=True):
    question = st.text_area(
        "Faça sua pergunta sobre dados fundiários (PB), produção agrícola ou manejo técnico:",
        value=st.session_state.get("question_input", ""),
        height=90,
        placeholder="Ex.: Quais municípios da Paraíba produzem milho e como controlar pragas nessa cultura?",
    )

    c1, c2, c3 = st.columns([2, 1, 1])
    mode_label = c1.selectbox(
        "Modo de Recuperação",
        [
            "Híbrido GraphRAG & KAG",
            "Baseline Vetorial (Apenas Trechos)",
            "Comparar Híbrido vs. Vector",
        ],
    )
    max_hops = c2.slider("Saltos Multi-hop", 1, 3, 2)
    top_k = c3.slider("Top-K Trechos", 3, 10, 5)

    submitted = st.button("Consultar AgroGraph", type="primary", icon=":material/search:")


def _render_result_panel(result: dict, title: str):
    st.subheader(title)
    confidence = float(result.get("confidence", 0.0))
    render_confidence_badge(confidence)

    render_kpi_row(
        [
            {"label": "Confiança", "value": f"{int(confidence * 100)}%"},
            {"label": "Nós no Subgrafo", "value": len(result.get("subgraph_nodes", []))},
            {"label": "Caminhos Multi-hop", "value": len(result.get("paths", []))},
            {"label": "Trechos de Evidência", "value": len(result.get("chunks", []))},
        ]
    )

    with st.container(border=True):
        st.markdown("### :material/auto_awesome: Resposta Fundamentada")
        st.markdown(result["answer"])

    if result.get("subgraph_nodes"):
        with st.container(border=True):
            st.markdown("### :material/hub: Subgrafo de Contexto Utilizado")
            render_entity_legend()
            html = render_interactive_graph(
                result["subgraph_nodes"],
                result["subgraph_edges"],
                height=460,
            )
            components.html(html, height=480, scrolling=False)

    st.markdown("### :material/fact_check: Painel de Rastreabilidade (Provenance)")

    if result.get("paths"):
        with st.expander(f"Caminhos do Grafo Utilizados ({len(result['paths'])})", expanded=True, icon=":material/route:"):
            for p in result["paths"]:
                st.markdown(f"- `{p}`")

    if result.get("cypher_generated"):
        with st.expander("Cypher Query Gerada via LLM (Somente Leitura)", icon=":material/code:"):
            st.code(result["cypher_generated"], language="cypher")
            if result.get("cypher_error"):
                st.warning(f"Aviso na execução Cypher: {result['cypher_error']}")
            elif result.get("cypher_results"):
                st.dataframe(
                    pd.DataFrame(result["cypher_results"]),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("A consulta Cypher retornou 0 registros.")

    if result.get("subgraph_nodes"):
        with st.expander(f"Nós Consultados & PageRank ({len(result['subgraph_nodes'])})", icon=":material/account_tree:"):
            nodes_df = pd.DataFrame([
                {
                    "Entidade": n.get("nome"),
                    "Tipo": n.get("tipo"),
                    "PageRank": n.get("pagerank", 0.0),
                    "Score Semente": n.get("seed_score", 0.0),
                }
                for n in result["subgraph_nodes"]
            ])
            st.dataframe(nodes_df, use_container_width=True, hide_index=True)

    if result.get("chunks"):
        with st.expander(f"Trechos Documentais Consultados ({len(result['chunks'])})", icon=":material/description:"):
            for c in result["chunks"]:
                st.markdown(
                    f"**{c.get('fonte', 'Documento')}** — Página `{c.get('pagina', '?')}` "
                    f"| Score: `{float(c.get('score', 0.0)):.4f}`"
                )
                st.caption(c.get("texto", ""))
                st.divider()


if submitted:
    if not question.strip():
        st.warning("Digite uma pergunta antes de consultar.", icon=":material/warning:")
        st.stop()

    st.session_state["question_input"] = question

    try:
        if mode_label == "Comparar Híbrido vs. Vector":
            with st.spinner("Executando GraphRAG Híbrido e Baseline Vetorial..."):
                res_hybrid = answer_question(question, mode="hybrid", top_k=top_k, max_hops=max_hops)
                res_vector = answer_question(question, mode="vector", top_k=top_k, max_hops=max_hops)

            col_h, col_v = st.columns(2)
            with col_h:
                _render_result_panel(res_hybrid, "Modo Híbrido (GraphRAG & KAG)")
            with col_v:
                _render_result_panel(res_vector, "Baseline Vetorial (Vector Search)")
        else:
            mode = "hybrid" if mode_label.startswith("Híbrido") else "vector"
            with st.spinner("Consultando grafo de conhecimento e gerando resposta fundamentada..."):
                res = answer_question(question, mode=mode, top_k=top_k, max_hops=max_hops)
            _render_result_panel(res, f"Resultado — {mode_label}")
    except Exception as exc:
        st.error(f"Erro durante a consulta: {exc}", icon=":material/error:")

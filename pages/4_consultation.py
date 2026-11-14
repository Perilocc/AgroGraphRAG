import html
import pandas as pd
import streamlit as st

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

SUGGESTED_QUESTIONS = {
    "Milho & Pragas (PB)": "Quais municípios da Paraíba produzem milho e quais pragas afetam essa cultura segundo a Embrapa?",
    "Lagarta-do-cartucho": "Como controlar a lagarta-do-cartucho no milho e quais práticas agrícolas são recomendadas?",
    "Manejo & Rotação (Soja)": "Quais estratégias de manejo e rotação de culturas são recomendadas para a soja?",
    "Top Áreas SNCR × Produção": "Quais são os 5 municípios da Paraíba com maior área rural cadastrada na amostra SNCR e o que eles produzem?",
    "Percevejo-marrom": "Quais práticas reduzem danos por percevejo-marrom na cultura da soja?",
}

with st.container(border=True):
    st.markdown("#### :material/search: Pergunta")
    selected_pill = st.pills(
        "Sugestões multi-hop",
        options=list(SUGGESTED_QUESTIONS.keys()),
        selection_mode="single",
    )
    if selected_pill and st.session_state.get("last_pill") != selected_pill:
        st.session_state["question_input"] = SUGGESTED_QUESTIONS[selected_pill]
        st.session_state["last_pill"] = selected_pill

    question = st.text_area(
        "Faça sua pergunta sobre dados fundiários (PB), produção agrícola ou manejo técnico:",
        value=st.session_state.get("question_input", ""),
        height=90,
        placeholder="Ex.: Quais municípios da Paraíba produzem milho e como controlar pragas nessa cultura?",
    )

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1.2], vertical_alignment="bottom")
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
    submitted = c4.button(
        "Consultar",
        type="primary",
        icon=":material/play_arrow:",
        width="stretch",
    )


def _render_result_panel(result: dict, title: str, compact: bool = False) -> None:
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
        st.markdown(result.get("answer", ""))

    sub_nodes = result.get("subgraph_nodes", [])
    sub_edges = result.get("subgraph_edges", [])
    if sub_nodes:
        with st.container(border=True):
            st.markdown("### :material/hub: Subgrafo de Contexto Utilizado")
            present_types = sorted({str(n.get("tipo") or n.get("type") or "Entidade") for n in sub_nodes})
            render_entity_legend(present_types)
            graph_height = 400 if compact else 480
            graph_html = render_interactive_graph(sub_nodes, sub_edges, height=graph_height)
            st.iframe(graph_html, height=graph_height + 20)

    st.markdown("### :material/fact_check: Rastreabilidade & Proveniência")
    tab_chunks, tab_paths, tab_cypher, tab_nodes = st.tabs(
        [
            f":material/article: Trechos ({len(result.get('chunks', []))})",
            f":material/route: Caminhos ({len(result.get('paths', []))})",
            ":material/code: Cypher Gerada",
            f":material/account_tree: Nós & PageRank ({len(sub_nodes)})",
        ]
    )

    with tab_chunks:
        chunks = result.get("chunks", [])
        if not chunks:
            st.info("Nenhum trecho documental recuperado.", icon=":material/info:")
        else:
            for idx, c in enumerate(chunks, start=1):
                fonte = html.escape(str(c.get("fonte") or c.get("documento_id") or "Documento"))
                pagina = html.escape(str(c.get("pagina", "?")))
                score = float(c.get("score", 0.0))
                texto = html.escape(str(c.get("texto", "")).strip())
                st.html(
                    f"""
                    <div class="agro-chunk-card">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                            <strong style="color:#18221B;font-size:0.9rem;">#{idx} • {fonte} (pág. {pagina})</strong>
                            <span style="font-family:'JetBrains Mono',monospace;font-size:0.78rem;color:#1F6E43;background:#E7F4EC;padding:2px 8px;border-radius:999px;">
                                score {score:.4f}
                            </span>
                        </div>
                        <div style="color:#4B594F;font-size:0.9rem;line-height:1.5;">{texto}</div>
                    </div>
                    """
                )

    with tab_paths:
        paths = result.get("paths", [])
        if not paths:
            st.info("Nenhum caminho multi-hop registrado para este modo.", icon=":material/info:")
        else:
            for p in paths:
                st.markdown(f"- `{p}`")

    with tab_cypher:
        cypher = result.get("cypher_generated")
        if not cypher:
            st.info("Nenhuma query Cypher gerada para esta consulta.", icon=":material/info:")
        else:
            st.badge("Read-Only Validated", icon=":material/verified_user:", color="green")
            st.code(cypher, language="cypher")
            if result.get("cypher_error"):
                st.warning(f"Aviso na execução Cypher: {result['cypher_error']}", icon=":material/warning:")
            elif result.get("cypher_results"):
                st.dataframe(pd.DataFrame(result["cypher_results"]), width="stretch", hide_index=True)
            else:
                st.info("A consulta Cypher retornou 0 registros.")

    with tab_nodes:
        if not sub_nodes:
            st.info("Nenhum nó no subgrafo para este modo.", icon=":material/info:")
        else:
            nodes_df = pd.DataFrame(
                [
                    {
                        "Entidade": n.get("nome"),
                        "Tipo": n.get("tipo"),
                        "PageRank": round(float(n.get("pagerank", 0.0)), 4),
                        "Score Semente": round(float(n.get("seed_score", 0.0)), 4),
                    }
                    for n in sub_nodes
                ]
            )
            st.dataframe(nodes_df, width="stretch", hide_index=True)


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

            col_h, col_v = st.columns(2, gap="large")
            with col_h:
                _render_result_panel(res_hybrid, "Modo Híbrido (GraphRAG & KAG)", compact=True)
            with col_v:
                _render_result_panel(res_vector, "Baseline Vetorial (Vector Search)", compact=True)
        else:
            mode = "hybrid" if mode_label.startswith("Híbrido") else "vector"
            with st.spinner("Consultando grafo de conhecimento e gerando resposta fundamentada..."):
                res = answer_question(question, mode=mode, top_k=top_k, max_hops=max_hops)
            _render_result_panel(res, f"Resultado — {mode_label}")
    except Exception as exc:
        st.error(f"Erro durante a consulta: {exc}", icon=":material/error:")

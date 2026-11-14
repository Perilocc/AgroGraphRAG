import html
import streamlit as st

from retrieval.vector_search import search_similar_chunks
from ui import (
    apply_global_styles,
    render_confidence_badge,
    render_kpi_row,
    render_page_header,
)

apply_global_styles()

render_page_header(
    title="Consulta GraphRAG & KAG",
    subtitle="Busca semântica em conhecimento técnico (Embrapa) com rastreabilidade de trechos e preparação para multi-hop.",
    icon=":material/travel_explore:",
    badge_text="Modo Vetorial Ativo",
    badge_color="blue",
)

EXAMPLE_QUESTIONS = [
    "Quais estratégias de manejo são recomendadas para controle de pragas no milho?",
    "Como realizar o monitoramento de pragas na cultura da soja?",
    "Quais fatores afetam a viabilidade econômica do cultivo de milho?",
    "Quais técnicas de produção aumentam a produtividade da soja?",
]

with st.container(border=True):
    st.markdown("#### :material/search: Pergunta")
    selected_example = st.pills(
        "Exemplos rápidos",
        options=EXAMPLE_QUESTIONS,
        selection_mode="single",
    )

    col_q, col_k, col_btn = st.columns([4, 0.9, 1.1], vertical_alignment="bottom")
    with col_q:
        query_text = st.text_input(
            "Digite sua pergunta em linguagem natural",
            value=selected_example or "",
            placeholder="Ex.: Quais práticas de manejo reduzem perdas por lagarta no milho?",
        )
    with col_k:
        top_k = st.number_input("Top-K", min_value=1, max_value=20, value=5, step=1)
    with col_btn:
        run_search = st.button(
            "Consultar",
            type="primary",
            icon=":material/play_arrow:",
            width="stretch",
        )

if run_search:
    if not query_text.strip():
        st.warning("Digite ou selecione uma pergunta antes de consultar.", icon=":material/warning:")
    else:
        with st.spinner("Consultando índice vetorial no Neo4j..."):
            try:
                chunks = search_similar_chunks(query_text.strip(), top_k=int(top_k))
                st.session_state.consultation_chunks = chunks
                st.session_state.consultation_query = query_text.strip()
                st.session_state.consultation_error = None
            except Exception as exc:
                st.session_state.consultation_chunks = []
                st.session_state.consultation_error = str(exc)

if st.session_state.get("consultation_error"):
    st.error(
        f"Erro ao executar busca vetorial: {st.session_state.consultation_error}",
        icon=":material/error:",
    )
elif "consultation_chunks" in st.session_state:
    chunks = st.session_state.consultation_chunks
    if not chunks:
        st.info("Nenhum trecho relevante encontrado para a pergunta.", icon=":material/info:")
    else:
        scores = [float(c.get("score", 0.0)) for c in chunks]
        avg_score = sum(scores) / len(scores)
        max_score = max(scores)
        unique_docs = len({c.get("documento_id") for c in chunks if c.get("documento_id")})

        col_badge, _ = st.columns([1.5, 3.5])
        with col_badge:
            render_confidence_badge(max_score)

        render_kpi_row(
            [
                {"label": "Trechos Recuperados", "value": len(chunks)},
                {"label": "Documentos Distintos", "value": unique_docs},
                {"label": "Maior Similaridade", "value": f"{max_score:.3f}"},
                {"label": "Média de Score", "value": f"{avg_score:.3f}"},
            ]
        )

        tab_chunks, tab_cypher, tab_subgraph = st.tabs(
            [
                ":material/article: Trechos & Fontes",
                ":material/code: Cypher Gerada",
                ":material/hub: Subgrafo de Contexto",
            ]
        )

        with tab_chunks:
            for idx, chunk in enumerate(chunks, start=1):
                doc_id = html.escape(str(chunk.get("documento_id", "Documento")))
                pagina = html.escape(str(chunk.get("pagina", "-")))
                score = float(chunk.get("score", 0.0))
                texto = html.escape(str(chunk.get("texto", "")).strip())
                st.html(
                    f"""
                    <div class="agro-chunk-card">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                            <strong style="color:#18221B;font-size:0.9rem;">#{idx} • {doc_id} (pág. {pagina})</strong>
                            <span style="font-family:'JetBrains Mono',monospace;font-size:0.78rem;color:#1F6E43;background:#E7F4EC;padding:2px 8px;border-radius:999px;">
                                score {score:.4f}
                            </span>
                        </div>
                        <div style="color:#4B594F;font-size:0.9rem;line-height:1.5;">{texto}</div>
                    </div>
                    """
                )

        with tab_cypher:
            st.info(
                "A geração de Cypher read-only (Text-to-Cypher) será exibida aqui após a implementação da Fase C.",
                icon=":material/info:",
            )

        with tab_subgraph:
            st.info(
                "O subgrafo de contexto (multi-hop + algoritmo de grafo) será renderizado aqui após a implementação do `rag_pipeline` na Fase C.",
                icon=":material/info:",
            )

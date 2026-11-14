import streamlit as st
from ui import apply_global_styles, render_kpi_row
from utils.file_utils import discover_files, get_source_info


def render_home() -> None:
    """Página inicial editorial do AgroGraph Intelligence."""
    st.html(
        """
        <div class="agro-hero">
            <span class="agro-hero-kicker">GraphRAG &amp; KAG • Inteligência Agrícola</span>
            <h1>AgroGraph Intelligence</h1>
            <p>
                Plataforma de análise e explicabilidade agronômica que integra
                dados cadastrais rurais (SNCR), séries produtivas (IBGE/CONAB)
                e conhecimento técnico (Embrapa) em um grafo de conhecimento auditável.
            </p>
        </div>
        """
    )

    col_cta1, col_cta2, _ = st.columns([1.2, 1.2, 3])
    with col_cta1:
        st.page_link(
            "pages/4_consultation.py",
            label="Consultar Grafo",
            icon=":material/travel_explore:",
            width="stretch",
        )
    with col_cta2:
        st.page_link(
            "pages/1_data.py",
            label="Explorar Fontes",
            icon=":material/dataset:",
            width="stretch",
        )

    files = discover_files()
    institutions = {get_source_info(f)[1].upper() for f in files} if files else set()
    total_mb = round(sum(f.stat().st_size for f in files) / (1024 * 1024), 2) if files else 0.0

    render_kpi_row(
        [
            {"label": "Arquivos Catalogados", "value": len(files), "help": "Total descoberto em data/"},
            {"label": "Instituições Conectadas", "value": len(institutions), "help": "Embrapa, SNCR, IBGE, CONAB"},
            {"label": "Volume em Disco", "value": f"{total_mb} MB", "help": "Dados estruturados e PDFs"},
        ]
    )

    st.subheader("Fluxo da Plataforma")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        with st.container(border=True):
            st.markdown("#### :material/dataset: 1. Catálogo")
            st.caption("Inspeção de PDFs técnicos, cadastros SNCR e séries IBGE/CONAB.")
            st.page_link("pages/1_data.py", label="Abrir Fontes", icon=":material/arrow_forward:")

    with c2:
        with st.container(border=True):
            st.markdown("#### :material/sync: 2. Ingestão & Schema")
            st.caption("Extração NER/RE, chunking, embeddings e carga LPG no Neo4j.")
            st.page_link("pages/2_ingestion.py", label="Abrir Ingestão", icon=":material/arrow_forward:")

    with c3:
        with st.container(border=True):
            st.markdown("#### :material/hub: 3. Grafo Híbrido")
            st.caption("Exploração visual interativa de nós, relações e centralidade.")
            st.page_link("pages/3_graph.py", label="Abrir Grafo", icon=":material/arrow_forward:")

    with c4:
        with st.container(border=True):
            st.markdown("#### :material/travel_explore: 4. GraphRAG & KAG")
            st.caption("Perguntas multi-hop com subgrafo, Cypher e proveniência.")
            st.page_link("pages/4_consultation.py", label="Abrir Consulta", icon=":material/arrow_forward:")


st.set_page_config(
    page_title="AgroGraph Intelligence",
    page_icon="assets/icon.svg",
    layout="wide",
)

st.logo("assets/logo.svg", icon_image="assets/icon.svg", size="large")
apply_global_styles()

pg = st.navigation(
    {
        "Visão Geral": [
            st.Page(render_home, title="Início", icon=":material/eco:", default=True),
        ],
        "Dados & Grafo": [
            st.Page("pages/1_data.py", title="Fontes de Dados", icon=":material/dataset:"),
            st.Page("pages/2_ingestion.py", title="Ingestão & Schema", icon=":material/sync:"),
            st.Page("pages/3_graph.py", title="Explorador de Grafo", icon=":material/hub:"),
        ],
        "Inteligência": [
            st.Page("pages/4_consultation.py", title="Consulta GraphRAG", icon=":material/travel_explore:"),
        ],
    }
)
pg.run()

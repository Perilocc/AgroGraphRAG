import streamlit as st
from ui import apply_global_styles, render_page_header

apply_global_styles()

render_page_header(
    title="Ingestão & Schema",
    subtitle="Inicialização de constraints/índices no Neo4j e disparo dos pipelines Embrapa, SNCR, IBGE e CONAB.",
    icon=":material/sync:",
    badge_text="Task D1 • Pendente",
    badge_color="orange",
)

st.info(
    "Esta tela será conectada aos pipelines de ingestão e criação de schema na Task D1.",
    icon=":material/info:",
)

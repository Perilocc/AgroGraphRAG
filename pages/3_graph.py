import streamlit as st
from ui import apply_global_styles, render_entity_legend, render_page_header

apply_global_styles()

render_page_header(
    title="Explorador de Grafo",
    subtitle="Visualização interativa do Labeled Property Graph com filtros por label, município e cultura.",
    icon=":material/hub:",
    badge_text="Task D2 • Pendente",
    badge_color="orange",
)

render_entity_legend()

st.info(
    "O explorador visual com PyVis e métricas de grafo será implementado na Task D2.",
    icon=":material/info:",
)

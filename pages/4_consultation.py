import streamlit as st
from ui import apply_global_styles, render_page_header

apply_global_styles()

render_page_header(
    title="Consulta GraphRAG & KAG",
    subtitle="Perguntas em linguagem natural com travessia multi-hop, subgrafo de contexto e proveniência explícita.",
    icon=":material/travel_explore:",
    badge_text="Task D3 • Pendente",
    badge_color="orange",
)

st.info(
    "A interface de consulta híbrida, subgrafo PyVis e painel de rastreabilidade será implementada na Task D3.",
    icon=":material/info:",
)

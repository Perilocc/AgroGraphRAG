from pathlib import Path
import streamlit as st

CSS_PATH = Path(__file__).parent / "styles.css"

# Paleta semântica sincronizada entre UI e PyVis (DESIGN_SYSTEM.md Seção 2.4)
ENTITY_COLORS: dict[str, dict[str, str]] = {
    "ImovelRural": {"fill": "#1F6E43", "border": "#144A2C", "label": "Imóvel Rural"},
    "Municipio": {"fill": "#1E6B8C", "border": "#13485F", "label": "Município"},
    "Estado": {"fill": "#1E6B8C", "border": "#13485F", "label": "Estado"},
    "Detentor": {"fill": "#5B6B5E", "border": "#3B473D", "label": "Detentor"},
    "RegistroDetencao": {"fill": "#5B6B5E", "border": "#3B473D", "label": "Registro Detenção"},
    "Cultura": {"fill": "#D48817", "border": "#9C610B", "label": "Cultura"},
    "Praga": {"fill": "#C0392B", "border": "#8E281E", "label": "Praga"},
    "PraticaAgricola": {"fill": "#2E8B57", "border": "#1E5E3A", "label": "Prática Agrícola"},
    "Safra": {"fill": "#7D5BA6", "border": "#563B76", "label": "Safra"},
    "Documento": {"fill": "#64748B", "border": "#475569", "label": "Documento"},
    "Trecho": {"fill": "#64748B", "border": "#475569", "label": "Trecho"},
    "Entidade": {"fill": "#2F7A78", "border": "#1F5452", "label": "Entidade"},
}

ENTITY_ICONS: dict[str, str] = {
    "ImovelRural": ":material/agriculture:",
    "Municipio": ":material/location_on:",
    "Estado": ":material/map:",
    "Detentor": ":material/badge:",
    "RegistroDetencao": ":material/badge:",
    "Cultura": ":material/grass:",
    "Praga": ":material/pest_control:",
    "PraticaAgricola": ":material/eco:",
    "Safra": ":material/bar_chart:",
    "Documento": ":material/description:",
    "Trecho": ":material/article:",
    "Entidade": ":material/hub:",
}


def apply_global_styles() -> None:
    """Injeta o CSS complementar do Design System na página atual."""
    if CSS_PATH.exists():
        css = CSS_PATH.read_text(encoding="utf-8")
        st.html(f"<style>{css}</style>")

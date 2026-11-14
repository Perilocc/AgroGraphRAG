from pathlib import Path
import streamlit as st

CSS_PATH = Path(__file__).parent / "styles.css"

# Paleta semântica sincronizada entre UI, Legenda e PyVis
ENTITY_COLORS: dict[str, dict[str, str]] = {
    "ImovelRural": {"fill": "#1F6E43", "border": "#144A2C", "label": "Imóvel Rural"},
    "Municipio": {"fill": "#1E6B8C", "border": "#13485F", "label": "Município"},
    "Estado": {"fill": "#2563EB", "border": "#1D4ED8", "label": "Estado"},
    "Regiao": {"fill": "#0284C7", "border": "#0369A1", "label": "Região"},
    "Bioma": {"fill": "#2F7A78", "border": "#1F5452", "label": "Bioma"},
    "Detentor": {"fill": "#5B6B5E", "border": "#3B473D", "label": "Detentor"},
    "RegistroDetencao": {"fill": "#6B7280", "border": "#4B5563", "label": "Registro Detenção"},
    "Pessoa": {"fill": "#4B5563", "border": "#374151", "label": "Pessoa"},
    "Instituicao": {"fill": "#9C610B", "border": "#713F12", "label": "Instituição"},
    "CulturaAgricola": {"fill": "#D48817", "border": "#9C610B", "label": "Cultura Agrícola"},
    "Cultura": {"fill": "#D48817", "border": "#9C610B", "label": "Cultura"},
    "ProdutoAgricola": {"fill": "#7D5BA6", "border": "#563B76", "label": "Produto Agrícola"},
    "Safra": {"fill": "#7D5BA6", "border": "#563B76", "label": "Safra"},
    "CondicaoAmbiental": {"fill": "#E67E22", "border": "#B85D11", "label": "Condição Ambiental"},
    "Praga": {"fill": "#C0392B", "border": "#8E281E", "label": "Praga"},
    "PraticaAgricola": {"fill": "#2E8B57", "border": "#1E5E3A", "label": "Prática Agrícola"},
    "Documento": {"fill": "#64748B", "border": "#475569", "label": "Documento"},
    "Trecho": {"fill": "#94A3B8", "border": "#64748B", "label": "Trecho"},
    "Entidade": {"fill": "#2F7A78", "border": "#1F5452", "label": "Entidade"},
}

ENTITY_ICONS: dict[str, str] = {
    "ImovelRural": ":material/agriculture:",
    "Municipio": ":material/location_on:",
    "Estado": ":material/map:",
    "Regiao": ":material/public:",
    "Bioma": ":material/forest:",
    "Detentor": ":material/badge:",
    "RegistroDetencao": ":material/badge:",
    "Pessoa": ":material/person:",
    "Instituicao": ":material/account_balance:",
    "CulturaAgricola": ":material/grass:",
    "Cultura": ":material/grass:",
    "ProdutoAgricola": ":material/inventory_2:",
    "Safra": ":material/bar_chart:",
    "CondicaoAmbiental": ":material/wb_sunny:",
    "Praga": ":material/pest_control:",
    "PraticaAgricola": ":material/eco:",
    "Documento": ":material/description:",
    "Trecho": ":material/article:",
    "Entidade": ":material/hub:",
}


def apply_global_styles() -> None:
    """Injeta o CSS complementar do Design System na página atual."""
    if CSS_PATH.exists():
        css = CSS_PATH.read_text(encoding="utf-8")
        st.html(f"<style>{css}</style>")

import json
import streamlit as st
from ui.theme import ENTITY_COLORS


def render_page_header(
    title: str,
    subtitle: str,
    icon: str,
    badge_text: str | None = None,
    badge_color: str = "green",
) -> None:
    """Cabeçalho padronizado para todas as páginas do AgroGraph Intelligence."""
    col_title, col_badge = st.columns([5, 1.4], vertical_alignment="center")
    with col_title:
        st.markdown(f"# {icon} {title}")
        st.caption(subtitle)
    with col_badge:
        if badge_text:
            st.badge(badge_text, color=badge_color)
    st.divider()


def render_kpi_row(metrics: list[dict]) -> None:
    """Renderiza uma linha uniforme de cards KPI com borda."""
    cols = st.columns(len(metrics))
    for col, item in zip(cols, metrics):
        with col:
            with st.container(border=True):
                st.metric(
                    label=item["label"],
                    value=item["value"],
                    delta=item.get("delta"),
                    help=item.get("help"),
                )


def render_confidence_badge(score: float) -> None:
    """Exibe badge semântico de confiança para respostas do GraphRAG."""
    pct = int(round(max(0.0, min(1.0, score)) * 100))
    if score >= 0.75:
        st.badge(f"Confiança Alta • {pct}%", icon=":material/verified_user:", color="green")
    elif score >= 0.45:
        st.badge(f"Confiança Moderada • {pct}%", icon=":material/info:", color="orange")
    else:
        st.badge(f"Evidência Limitada • {pct}%", icon=":material/warning:", color="red")


def render_entity_legend(labels: list[str] | None = None) -> None:
    """Renderiza legenda horizontal com as cores semânticas dos nós do grafo."""
    target_labels = labels or list(ENTITY_COLORS.keys())
    pills = []
    for label in target_labels:
        cfg = ENTITY_COLORS.get(label, ENTITY_COLORS["Entidade"])
        display = cfg.get("label", label)
        pills.append(
            f'<span class="agro-legend-pill">'
            f'<span class="agro-legend-dot" style="background-color:{cfg["fill"]};"></span>'
            f"{display}</span>"
        )
    st.html(f'<div class="agro-legend">{"".join(pills)}</div>')


def get_pyvis_network_config() -> str:
    """Retorna JSON de opções visuais padronizadas para instâncias pyvis.Network."""
    options = {
        "nodes": {
            "shape": "dot",
            "size": 18,
            "borderWidth": 2,
            "font": {
                "face": "Inter, sans-serif",
                "size": 13,
                "color": "#18221B",
            },
        },
        "edges": {
            "color": {"color": "#94A3B8", "highlight": "#1F6E43", "hover": "#1F6E43"},
            "width": 1.4,
            "smooth": {"type": "dynamic"},
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.6}},
            "font": {
                "face": "Inter, sans-serif",
                "size": 10,
                "color": "#4B594F",
                "align": "middle",
            },
        },
        "physics": {
            "barnesHut": {
                "gravitationalConstant": -3200,
                "centralGravity": 0.25,
                "springLength": 130,
                "springConstant": 0.04,
            },
            "stabilization": {"iterations": 120},
        },
        "interaction": {
            "hover": True,
            "tooltipDelay": 120,
            "navigationButtons": False,
        },
    }
    return json.dumps(options)

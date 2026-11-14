import json
from pyvis.network import Network

from ui.components import get_pyvis_network_config
from ui.theme import ENTITY_COLORS

TYPE_COLORS = {k: v["fill"] for k, v in ENTITY_COLORS.items()}

COMMUNITY_PALETTE = [
    "#1F6E43",
    "#1E6B8C",
    "#D48817",
    "#7D5BA6",
    "#C0392B",
    "#2F7A78",
    "#2E8B57",
    "#5B6B5E",
    "#475569",
    "#9C610B",
]


def render_interactive_graph(
    nodes: list[dict],
    edges: list[dict],
    height: int = 540,
    community_map: dict[str, int] | None = None,
) -> str:
    """
    Gera HTML interativo com PyVis, hover limpo em texto puro,
    toolbar flutuante (Zoom +/-, Resetar, Filtro) e painel lateral de detalhes.
    Aceita tanto o formato de algorithms/kag_engine quanto o de get_subgraph().
    """
    net = Network(
        height=f"{height}px",
        width="100%",
        bgcolor="#FFFFFF",
        font_color="#18221B",
        directed=True,
    )
    net.set_options(get_pyvis_network_config())

    added_nodes: set[str] = set()
    node_details: dict[str, dict] = {}
    max_pr = max((float(n.get("pagerank", 0.0)) for n in nodes), default=0.0) or 1.0

    for node in nodes:
        nid = str(node.get("id", ""))
        if not nid or nid in added_nodes:
            continue
        added_nodes.add(nid)

        label = str(node.get("nome") or node.get("name") or node.get("label") or nid[:12])
        ntype = str(node.get("tipo") or node.get("type") or node.get("group") or "Entidade")
        desc = str(node.get("descricao") or "")
        pr = float(node.get("pagerank", 0.0))
        props = dict(node.get("properties") or {})

        palette = ENTITY_COLORS.get(ntype, ENTITY_COLORS["Entidade"])
        if community_map and nid in community_map:
            comm_idx = community_map[nid]
            fill_color = COMMUNITY_PALETTE[(comm_idx - 1) % len(COMMUNITY_PALETTE)]
            border_color = fill_color
            comm_label = f"Comunidade #{comm_idx}"
        else:
            fill_color = palette["fill"]
            border_color = palette["border"]
            comm_label = ""

        size = 18 + int((pr / max_pr) * 20) if pr > 0 else 19

        # Tooltip em texto puro (evita vazamento de tags HTML no vis-network)
        tooltip_lines = [f"[{ntype}] {label}"]
        if pr > 0:
            tooltip_lines.append(f"PageRank: {pr:.4f}")
        if comm_label:
            tooltip_lines.append(comm_label)
        if desc:
            tooltip_lines.append(desc[:140])
        elif props:
            for k, v in list(props.items())[:4]:
                tooltip_lines.append(f"{k}: {str(v)[:90]}")
        tooltip = "\n".join(tooltip_lines)

        net.add_node(
            nid,
            label=label[:28] + ("…" if len(label) > 28 else ""),
            title=tooltip,
            color={"background": fill_color, "border": border_color},
            size=size,
        )

        detail_props = {str(k): str(v) for k, v in props.items()}
        if pr > 0:
            detail_props.setdefault("PageRank", f"{pr:.4f}")
        if comm_label:
            detail_props.setdefault("Comunidade", comm_label)
        if desc:
            detail_props.setdefault("Descrição", desc)

        node_details[nid] = {
            "id": nid,
            "label": label,
            "group": palette.get("label", ntype),
            "color": fill_color,
            "properties": detail_props,
        }

    for edge in edges:
        src = str(edge.get("source_id") or edge.get("source") or "")
        tgt = str(edge.get("target_id") or edge.get("target") or "")
        rel_type = str(edge.get("tipo") or edge.get("type") or "RELACIONA")

        if src not in added_nodes or tgt not in added_nodes:
            continue

        edge_tooltip = rel_type
        if rel_type == "PRODUZ" and edge.get("ano"):
            edge_tooltip = (
                f"PRODUZ ({edge.get('ano')})\n"
                f"Área: {edge.get('area_plantada_ha')} ha\n"
                f"Produção: {edge.get('quantidade_ton')} t"
            )

        net.add_edge(
            src,
            tgt,
            label=rel_type,
            title=edge_tooltip,
            color={"color": "#94A3B8", "highlight": "#1F6E43", "hover": "#1F6E43"},
            font={"size": 10, "color": "#4B594F", "strokeWidth": 0},
        )

    raw_html = net.generate_html()
    details_json = json.dumps(node_details, ensure_ascii=False)
    panel_max_h = max(260, height - 40)

    ux_overlay = f"""
    <style>
      #agro-toolbar {{
        position: absolute; top: 12px; left: 12px; z-index: 20;
        display: flex; align-items: center; gap: 6px;
        background: rgba(255,255,255,0.96); border: 1px solid #DCE3D5;
        border-radius: 8px; padding: 6px 8px; box-shadow: 0 2px 8px rgba(24,34,27,0.08);
        font-family: Inter, sans-serif;
      }}
      #agro-toolbar button {{
        border: 1px solid #DCE3D5; background: #F6F7F3; color: #18221B;
        border-radius: 6px; padding: 4px 9px; font-size: 13px; font-weight: 600;
        cursor: pointer; line-height: 1.2;
      }}
      #agro-toolbar button:hover {{ background: #EDF1E8; border-color: #1F6E43; color: #1F6E43; }}
      #agro-search {{
        border: 1px solid #DCE3D5; border-radius: 6px; padding: 4px 8px;
        font-size: 12px; width: 165px; outline: none; color: #18221B; background: #FFFFFF;
      }}
      #agro-search:focus {{ border-color: #1F6E43; }}
      #agro-detail-panel {{
        position: absolute; top: 12px; right: 12px; z-index: 20;
        width: 270px; max-height: {panel_max_h}px; overflow-y: auto;
        background: rgba(255,255,255,0.97); border: 1px solid #DCE3D5;
        border-radius: 8px; padding: 12px 14px; box-shadow: 0 4px 14px rgba(24,34,27,0.1);
        font-family: Inter, sans-serif; font-size: 12.5px; color: #18221B;
        display: none;
      }}
      #agro-detail-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
      #agro-detail-badge {{
        display: inline-block; padding: 2px 8px; border-radius: 999px;
        color: #FFFFFF; font-size: 11px; font-weight: 600;
      }}
      #agro-detail-close {{
        border: none; background: transparent; cursor: pointer; font-size: 16px; color: #6E7C72;
      }}
      #agro-detail-title {{ font-size: 14px; font-weight: 700; margin: 4px 0 10px 0; word-break: break-word; }}
      .agro-prop-row {{ border-top: 1px solid #EDF1E8; padding: 5px 0; }}
      .agro-prop-key {{ font-size: 11px; color: #6E7C72; font-weight: 600; }}
      .agro-prop-val {{ font-size: 12px; color: #18221B; word-break: break-word; }}
    </style>
    <div id="agro-toolbar">
      <button id="btn-zoom-in" title="Aproximar">+</button>
      <button id="btn-zoom-out" title="Afastar">−</button>
      <button id="btn-reset" title="Resetar visualização">Resetar</button>
      <input id="agro-search" type="text" placeholder="Filtrar nó no grafo..." />
    </div>
    <div id="agro-detail-panel">
      <div id="agro-detail-header">
        <span id="agro-detail-badge"></span>
        <button id="agro-detail-close" title="Fechar">&times;</button>
      </div>
      <div id="agro-detail-title"></div>
      <div id="agro-detail-props"></div>
    </div>
    <script>
      (function() {{
        const details = {details_json};
        const panel = document.getElementById("agro-detail-panel");
        const badgeEl = document.getElementById("agro-detail-badge");
        const titleEl = document.getElementById("agro-detail-title");
        const propsEl = document.getElementById("agro-detail-props");

        function escHtml(str) {{
          return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
        }}

        document.getElementById("agro-detail-close").onclick = () => {{ panel.style.display = "none"; }};
        document.getElementById("btn-zoom-in").onclick = () => {{
          if (typeof network !== "undefined") network.moveTo({{ scale: network.getScale() * 1.25, animation: true }});
        }};
        document.getElementById("btn-zoom-out").onclick = () => {{
          if (typeof network !== "undefined") network.moveTo({{ scale: network.getScale() * 0.8, animation: true }});
        }};
        document.getElementById("btn-reset").onclick = () => {{
          document.getElementById("agro-search").value = "";
          if (typeof nodes !== "undefined") {{
            nodes.forEach((n) => nodes.update({{ id: n.id, hidden: false }}));
          }}
          if (typeof network !== "undefined") network.fit({{ animation: true }});
        }};
        document.getElementById("agro-search").addEventListener("input", function(e) {{
          const q = e.target.value.trim().toLowerCase();
          if (typeof nodes === "undefined") return;
          nodes.forEach((n) => {{
            const info = details[n.id];
            const fullLabel = info ? info.label.toLowerCase() : (n.label || "").toLowerCase();
            const match = !q || fullLabel.includes(q);
            nodes.update({{ id: n.id, hidden: !match }});
          }});
        }});

        if (typeof network !== "undefined") {{
          network.on("click", function(params) {{
            if (params.nodes && params.nodes.length > 0) {{
              const info = details[params.nodes[0]];
              if (!info) return;
              badgeEl.textContent = info.group;
              badgeEl.style.backgroundColor = info.color;
              titleEl.textContent = info.label;
              const entries = Object.entries(info.properties);
              propsEl.innerHTML = entries.length
                ? entries.map(([k, v]) => `<div class="agro-prop-row"><div class="agro-prop-key">${{escHtml(k)}}</div><div class="agro-prop-val">${{escHtml(v)}}</div></div>`).join("")
                : "<div class='agro-prop-val'>Sem propriedades adicionais.</div>";
              panel.style.display = "block";
            }} else {{
              panel.style.display = "none";
            }}
          }});
        }}
      }})();
    </script>
    """
    return raw_html.replace("</body>", f"{ux_overlay}</body>")

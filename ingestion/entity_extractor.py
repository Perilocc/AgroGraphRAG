import json
from openai import OpenAI

from graph.ontology import (
    canonicalize_entity,
    normalize_text,
    sanitize_relation_type,
)
from utils.config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY or "not-configured")

SYSTEM_PROMPT = """
Você é um especialista em extração de conhecimento agrícola (NER & RE) para construção de grafos LPG.

Analise o texto e extraia exclusivamente:

1. Entidades relevantes usando APENAS os seguintes tipos exatos (PascalCase):
   - CulturaAgricola (ex.: Milho, Soja, Café, Sorgo, Feijão)
   - Praga (ex.: Lagarta-do-cartucho, Percevejo-marrom, Ferrugem-asiática)
   - PraticaAgricola (ex.: Plantio direto, Rotação de culturas, Manejo Integrado de Pragas)
   - ProdutoAgricola (ex.: Inseticida, Fungicida, Inoculante, Semente tratada)
   - CondicaoAmbiental (ex.: Déficit hídrico, Temperatura elevada, Solo ácido)
   - Municipio (nome do município citado)
   - Estado (nome do estado brasileiro)
   - Regiao (ex.: Nordeste, Cerrado brasileiro, Agreste)
   - Bioma (ex.: Caatinga, Cerrado, Mata Atlântica)
   - Instituicao (ex.: Embrapa, MAPA, CONAB)
   - Pessoa (pesquisadores ou autores relevantes)

2. Relacionamentos explícitos entre as entidades extraídas.

Regras obrigatórias:
- Não invente informações nem crie relações por suposição.
- Use exclusivamente os tipos listados acima no campo "type" de cada entidade.
- Preserve nomes próprios e evite entidades genéricas (ex.: "produtor", "área", "estudo").
- Os relacionamentos devem usar verbos curtos em MAIÚSCULAS com underscore (ex.: AFETA, CONTROLA, RECOMENDA, PRODUZIDO_EM, MANEJADA_COM, CAUSA, OCORRE_EM).

Retorne exclusivamente um JSON neste formato:

{
    "entities": [
        {
            "name": "Milho",
            "type": "CulturaAgricola",
            "description": "Cultura agrícola de grãos mencionada no texto."
        }
    ],
    "relations": [
        {
            "source": "Milho",
            "target": "Paraíba",
            "type": "PRODUZIDO_EM"
        }
    ]
}
"""


def generate_entity_id(name: str, entity_type: str) -> str:
    """Gera identificador determinístico e canônico para uma entidade."""
    canonical = canonicalize_entity(name, entity_type)
    if canonical:
        return canonical[0]
    import hashlib
    normalized = normalize_text(name)
    value = f"{entity_type.casefold()}:{normalized}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def extract_knowledge(
    text: str,
    chunk_id: str,
    pb_municipios_map: dict[str, str] | None = None,
) -> dict:
    """
    Extrai entidades e relacionamentos sanitizados de um trecho.
    Quando pb_municipios_map é informado, resolve menções a Municipio em memória
    para o ID oficial do SNCR ou descarta municípios fora da PB.
    """
    if not text.strip():
        return {"entities": [], "relations": [], "unresolved_municipalities": []}

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )

    content = response.choices[0].message.content

    if not content:
        raise ValueError("A OpenAI retornou uma resposta vazia.")

    data = json.loads(content)

    entities = []
    entity_map: dict[str, dict] = {}
    unresolved_municipalities: list[str] = []

    for item in data.get("entities", []):
        raw_name = item.get("name", "").strip()
        raw_type = item.get("type", "").strip()

        canonical = canonicalize_entity(raw_name, raw_type)
        if not canonical:
            continue

        entity_id, canonical_name, canonical_type = canonical

        if canonical_type == "Municipio" and pb_municipios_map is not None:
            norm_mun = normalize_text(canonical_name)
            official_id = pb_municipios_map.get(norm_mun)
            if not official_id:
                unresolved_municipalities.append(canonical_name)
                continue
            entity_id = official_id

        entity = {
            "id": entity_id,
            "nome": canonical_name,
            "tipo": canonical_type,
            "descricao": item.get("description", "").strip(),
            "trecho_id": chunk_id,
        }

        entities.append(entity)
        entity_map[normalize_text(raw_name)] = entity
        entity_map[normalize_text(canonical_name)] = entity

    relations = []
    seen_relations = set()

    for item in data.get("relations", []):
        source = entity_map.get(normalize_text(item.get("source", "")))
        target = entity_map.get(normalize_text(item.get("target", "")))
        relation_type = sanitize_relation_type(item.get("type", ""))

        if not source or not target or not relation_type:
            continue
        if source["id"] == target["id"]:
            continue

        rel_key = (source["id"], relation_type, target["id"], chunk_id)
        if rel_key in seen_relations:
            continue
        seen_relations.add(rel_key)

        relations.append({
            "source_id": source["id"],
            "target_id": target["id"],
            "tipo": relation_type,
            "trecho_id": chunk_id,
        })

    return {
        "entities": entities,
        "relations": relations,
        "unresolved_municipalities": unresolved_municipalities,
    }


def confirm_entity_equivalence_llm(pairs: list[dict]) -> list[tuple[str, str]]:
    """
    Confirma via LLM se pares candidatos com similaridade intermediária (0.75..0.90)
    representam exatamente o mesmo conceito agronômico (ex.: nome popular vs. científico).
    Retorna a lista de pares (source_id, canonical_id) confirmados.
    """
    if not pairs:
        return []

    prompt_items = [
        {
            "pair_index": idx,
            "tipo": p["tipo"],
            "entidade_a": p["name_a"],
            "entidade_b": p["name_b"],
        }
        for idx, p in enumerate(pairs)
    ]

    instruction = (
        "Você é um especialista em ontologia agronômica e resolução de entidades.\n"
        "Para cada par do mesmo tipo abaixo, responda true APENAS se ambos os nomes "
        "designarem exatamente a mesma entidade, espécie ou conceito (ex.: nome popular "
        "e nome científico da mesma praga, sigla e nome completo).\n"
        "Responda false se forem espécies diferentes, culturas diferentes ou práticas distintas.\n"
        'Retorne JSON: {"decisions": [{"pair_index": 0, "equivalent": true}]}'
    )

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": json.dumps(prompt_items, ensure_ascii=False)},
            ],
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
    except Exception:
        return []

    confirmed = []
    for decision in parsed.get("decisions", []):
        idx = decision.get("pair_index")
        if decision.get("equivalent") is True and isinstance(idx, int) and 0 <= idx < len(pairs):
            pair = pairs[idx]
            confirmed.append((pair["source_id"], pair["target_id"]))

    return confirmed

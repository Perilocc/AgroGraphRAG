from utils.config import OPENAI_API_KEY, OPENAI_MODEL
from openai import OpenAI
import hashlib, json, re

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
Você é um especialista em extração de conhecimento agrícola.

Analise o texto e extraia:

1. Entidades relevantes, como:
   - Cultura agrícola
   - Pessoa
   - Propriedade rural
   - Município
   - Estado
   - Região
   - Bioma
   - Instituição
   - Produto agrícola
   - Prática agrícola
   - Condição ambiental

2. Relacionamentos explícitos entre as entidades.

Regras:
- Não invente informações.
- Extraia somente informações presentes no texto.
- Não crie relações apenas por associação ou suposição.
- Evite entidades genéricas ou sem relevância.
- Preserve nomes próprios.
- Utilize nomes consistentes para os tipos.
- Os relacionamentos devem ter nomes curtos em MAIÚSCULAS,
  usando underscore quando necessário.

Retorne exclusivamente um JSON neste formato:

{
    "entities": [
        {
            "name": "Milho",
            "type": "Cultura agrícola",
            "description": "Cultura agrícola mencionada no texto."
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
    """Gera identificador determinístico para uma entidade."""

    normalized = re.sub(r"\s+", " ", name.strip().casefold())

    value = f"{entity_type.casefold()}:{normalized}"

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def extract_knowledge(text: str, chunk_id: str) -> dict:
    """Extrai entidades e relacionamentos de um trecho."""

    if not text.strip():
        return {"entities": [], "relations": []}

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
    entity_map = {}

    for item in data.get("entities", []):
        name = item.get("name", "").strip()
        entity_type = item.get("type", "").strip()

        if not name or not entity_type:
            continue

        entity_id = generate_entity_id(name, entity_type)

        entity = {
            "id": entity_id,
            "nome": name,
            "tipo": entity_type,
            "descricao": item.get("description", ""),
            "trecho_id": chunk_id,
        }

        entities.append(entity)
        entity_map[name.casefold()] = entity

    relations = []

    for item in data.get("relations", []):
        source = entity_map.get(
            item.get("source", "").strip().casefold()
        )
        target = entity_map.get(
            item.get("target", "").strip().casefold()
        )

        relation_type = item.get("type", "").strip().upper()

        if not source or not target or not relation_type:
            continue

        relations.append({
            "source_id": source["id"],
            "target_id": target["id"],
            "tipo": relation_type,
            "trecho_id": chunk_id,
        })

    return {
        "entities": entities,
        "relations": relations,
    }

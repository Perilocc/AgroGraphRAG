import json
import re
from neo4j import Query

from graph.connection import get_driver, get_session
from utils.config import OPENAI_API_KEY, OPENAI_MODEL
from utils.llm import create_chat_completion, create_openai_client

client = create_openai_client(OPENAI_API_KEY)

FORBIDDEN_CYPHER = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|CALL|LOAD\s+CSV|FOREACH|ALTER|GRANT|DENY|REVOKE|TERMINATE)\b",
    re.IGNORECASE,
)

SCHEMA_DESCRIPTION = """
Nós (Labels):
- (:Entidade:ImovelRural {id, codigo_sncr, denominacao, area_total})  [AMOSTRA UNIFORME 1/6 da PB ~39.5k imóveis]
- (:Entidade:Municipio {id, codigo_ibge, nome, nome_normalizado, uf})
- (:Entidade:RegistroDetencao {id, condicao_pessoa, percentual_detencao})
- (:Entidade:Detentor {id, identificador, nome, natureza_juridica})
- (:Entidade:CulturaAgricola {id, nome, descricao})  [ex.: Milho, Soja, Café]
- (:Entidade:Praga {id, nome, descricao})
- (:Entidade:PraticaAgricola {id, nome, descricao})
- (:Entidade:ProdutoAgricola {id, nome, descricao})
- (:Entidade:CondicaoAmbiental {id, nome, descricao})
- (:Documento {id, nome, origem})
- (:Trecho {id, texto, pagina, fonte})

Relacionamentos:
- (ImovelRural)-[:LOCALIZADO_EM]->(Municipio)
- (ImovelRural)-[:POSSUI_DETENCAO]->(RegistroDetencao)
- (RegistroDetencao)-[:REFERENTE_A]->(Detentor)
- (ImovelRural)-[:EXTRAIDO_DE]->(Documento)
- (Municipio)-[:PRODUZ {ano, area_plantada_ha, quantidade_ton, fonte}]->(CulturaAgricola)
- Relações semânticas entre entidades dos PDFs (ex.: AFETA, CONTROLA, RECOMENDA, MANEJADA_COM, PRODUZIDO_EM)
- (Entidade)-[:EXTRAIDO_DE]->(Trecho)<-[:CONTEM]-(Documento)

Regras:
- Gere apenas consultas Cypher somente-leitura (MATCH / OPTIONAL MATCH / WHERE / WITH / RETURN / ORDER BY / LIMIT).
- Para buscar por nomes de municípios/entidades, use toLower(...) CONTAINS toLower(...) ou m.nome_normalizado.
- Sempre inclua LIMIT <= 25.
- NUNCA use CREATE, MERGE, DELETE, SET, CALL ou procedimentos.
"""

SYSTEM_PROMPT = f"""
Você é um tradutor especializado de perguntas em linguagem natural para Cypher no Neo4j.
Dado o schema LPG abaixo, decida se a pergunta requer ou se beneficia de uma consulta Cypher estruturada (ex.: contagens, rankings, áreas, produção IBGE, municípios, detentores, relacionamentos diretos no grafo).

{SCHEMA_DESCRIPTION}

Retorne exclusivamente JSON no formato:
{{
    "needs_cypher": true,
    "cypher": "MATCH ... RETURN ... LIMIT 15"
}}
Se a pergunta for puramente textual sem necessidade de Cypher estruturado, retorne:
{{"needs_cypher": false, "cypher": ""}}
"""


def validate_cypher_safety(cypher_query: str) -> str:
    """Camada 1: Validação sintática e bloqueio estrito de mutação/CALL."""
    if not cypher_query or not cypher_query.strip():
        raise ValueError("Consulta Cypher vazia.")

    cleaned = cypher_query.strip().rstrip(";")
    if FORBIDDEN_CYPHER.search(cleaned):
        raise ValueError("Consulta Cypher bloqueada por conter comando não permitido.")

    if "RETURN" not in cleaned.upper():
        raise ValueError("Consulta Cypher deve conter cláusula RETURN.")

    return cleaned


def execute_safe_cypher(cypher_query: str, max_rows: int = 50, timeout: float = 10.0) -> list[dict]:
    """
    Camada 2 & 3: Valida query_type == 'r' via EXPLAIN antes de executar,
    impõe timeout no servidor e limita retorno com result.fetch(max_rows).
    """
    cleaned = validate_cypher_safety(cypher_query)
    driver = get_driver()

    with get_session(driver) as session:
        explain_summary = session.run(f"EXPLAIN {cleaned}").consume()
        if explain_summary.query_type != "r":
            raise ValueError(
                f"Consulta rejeitada pelo planejador Neo4j (query_type={explain_summary.query_type})."
            )

        result = session.run(Query(cleaned, timeout=timeout))
        records = result.fetch(max_rows)
        return [record.data() for record in records]


def generate_and_run_cypher(question: str) -> dict:
    """Gera consulta Cypher via LLM e a executa de forma segura (somente leitura)."""
    if not question or not question.strip():
        return {"cypher": "", "rows": [], "error": "Pergunta vazia."}

    try:
        response = create_chat_completion(
            client,
            model=OPENAI_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
    except Exception as exc:
        return {"cypher": "", "rows": [], "error": str(exc)}

    if not parsed.get("needs_cypher") or not parsed.get("cypher"):
        return {"cypher": "", "rows": [], "error": None}

    cypher_query = parsed["cypher"].strip()
    try:
        rows = execute_safe_cypher(cypher_query)
        return {"cypher": cypher_query, "rows": rows, "error": None}
    except Exception as exc:
        return {"cypher": cypher_query, "rows": [], "error": str(exc)}

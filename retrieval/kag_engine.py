import json
from openai import OpenAI

from retrieval.cypher_generator import generate_and_run_cypher
from retrieval.hybrid_search import hybrid_retrieve
from retrieval.vector_search import search_similar_chunks
from utils.config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY or "not-configured")

HYBRID_SYSTEM_PROMPT = """
Você é o assistente técnico AgroGraph Intelligence (GraphRAG & KAG).
Responda à pergunta do usuário utilizando EXCLUSIVAMENTE os fatos presentes no contexto fornecido (Trechos Documentais, Subgrafo Multi-hop, Dados Agrícolas IBGE e Resultados Cypher do SNCR).

Regras obrigatórias de Mitigação de Alucinações e Grounding Semântico:
1. Nunca invente números, municípios, pragas, defensivos ou recomendações que não estejam explicitamente no contexto abaixo.
2. Se o contexto não contiver informação suficiente para responder a alguma parte da pergunta, declare explicitamente o que não foi encontrado nas fontes.
3. Cite explicitamente os caminhos do grafo utilizados no formato: [Entidade A] --(RELACAO)--> [Entidade B].
4. Cite as fontes documentais utilizadas no formato: [Fonte: nome_do_arquivo.pdf, p. X].
5. Sempre que citar contagens de imóveis rurais ou áreas do SNCR-PB, informe que os números refletem a amostra uniforme de 1/6 do SNCR-PB (~39,5 mil registros no Neo4j Aura).
"""

VECTOR_SYSTEM_PROMPT = """
Você é um assistente técnico agrícola operando no modo RAG Vetorial baseline.
Responda à pergunta utilizando EXCLUSIVAMENTE os trechos de texto recuperados abaixo.
Se a informação não estiver presente nos trechos, diga explicitamente que os trechos recuperados não respondem à pergunta.
Cite a fonte e página no formato [Fonte: nome_do_arquivo.pdf, p. X].
"""


def _format_hybrid_context(retrieval: dict, cypher_res: dict) -> str:
    sections = []

    if retrieval.get("paths"):
        sections.append("### Caminhos Multi-hop no Grafo (Conhecimento Estruturado):")
        for p in retrieval["paths"][:20]:
            sections.append(f"- {p}")

    if retrieval.get("nodes"):
        sections.append("\n### Entidades Mais Centrais no Subgrafo (PageRank):")
        for n in retrieval["nodes"][:12]:
            sections.append(
                f"- {n['nome']} ({n['tipo']}) | PageRank={n.get('pagerank', 0):.4f} | {n.get('descricao', '')}"
            )

    if retrieval.get("sncr_aggregates"):
        sections.append("\n### Resumo Fundiário SNCR-PB (Amostra Uniforme 1/6):")
        sections.append(json.dumps(retrieval["sncr_aggregates"], ensure_ascii=False, indent=2))

    if cypher_res.get("rows"):
        sections.append(f"\n### Resultado da Consulta Cypher ({cypher_res.get('cypher', '')}):")
        sections.append(json.dumps(cypher_res["rows"][:20], ensure_ascii=False, indent=2))

    if retrieval.get("chunks"):
        sections.append("\n### Trechos Documentais de Evidência:")
        for c in retrieval["chunks"][:8]:
            sections.append(
                f"[Fonte: {c.get('fonte', 'Documento')}, p. {c.get('pagina', '?')}] "
                f"(score={c.get('score', 0):.3f}):\n{c.get('texto', '')}"
            )

    return "\n".join(sections)


def _format_vector_context(chunks: list[dict]) -> str:
    if not chunks:
        return "Nenhum trecho recuperado."
    lines = ["### Trechos Recuperados (Busca Vetorial Pura):"]
    for c in chunks:
        lines.append(
            f"[Fonte: {c.get('fonte', 'Documento')}, p. {c.get('pagina', '?')}] "
            f"(score={c.get('score', 0):.3f}):\n{c.get('texto', '')}"
        )
    return "\n".join(lines)


def answer_question(
    question: str,
    mode: str = "hybrid",
    top_k: int = 5,
    max_hops: int = 2,
) -> dict:
    """
    Executa a consulta no modo escolhido:
    - 'no_context': LLM puro sem contexto (baseline de alucinação)
    - 'vector': Busca vetorial pura em trechos
    - 'hybrid': GraphRAG/KAG completo (Vector + Fulltext + Multi-hop + PageRank + Text-to-Cypher)
    """
    if not question or not question.strip():
        raise ValueError("A pergunta não pode ser vazia.")

    if mode == "no_context":
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "Responda de forma objetiva à pergunta agrícola/fundiária.",
                },
                {"role": "user", "content": question},
            ],
        )
        return {
            "mode": mode,
            "question": question,
            "answer": response.choices[0].message.content or "",
            "confidence": 0.0,
            "context_text": "",
            "chunks": [],
            "subgraph_nodes": [],
            "subgraph_edges": [],
            "paths": [],
            "sncr_aggregates": [],
            "cypher_generated": "",
            "cypher_results": [],
            "cypher_error": None,
        }

    if mode == "vector":
        chunks = search_similar_chunks(question, top_k=top_k)
        context_text = _format_vector_context(chunks)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": VECTOR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Contexto:\n{context_text}\n\nPergunta: {question}",
                },
            ],
        )
        top_score = max((float(c.get("score", 0.0)) for c in chunks), default=0.0)
        return {
            "mode": mode,
            "question": question,
            "answer": response.choices[0].message.content or "",
            "confidence": round(top_score, 4),
            "context_text": context_text,
            "chunks": chunks,
            "subgraph_nodes": [],
            "subgraph_edges": [],
            "paths": [],
            "sncr_aggregates": [],
            "cypher_generated": "",
            "cypher_results": [],
            "cypher_error": None,
        }

    if mode != "hybrid":
        raise ValueError(f"Modo inválido: {mode}")

    retrieval = hybrid_retrieve(question, top_k=top_k, max_hops=max_hops)
    cypher_res = generate_and_run_cypher(question)
    context_text = _format_hybrid_context(retrieval, cypher_res)

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": HYBRID_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Contexto Recuperado:\n{context_text}\n\nPergunta: {question}",
            },
        ],
    )

    confidence = retrieval["confidence"]
    if cypher_res.get("rows"):
        confidence = round(min(1.0, max(confidence, 0.75) + 0.15), 4)

    return {
        "mode": mode,
        "question": question,
        "answer": response.choices[0].message.content or "",
        "confidence": confidence,
        "context_text": context_text,
        "chunks": retrieval["chunks"],
        "subgraph_nodes": retrieval["nodes"],
        "subgraph_edges": retrieval["edges"],
        "paths": retrieval["paths"],
        "sncr_aggregates": retrieval["sncr_aggregates"],
        "cypher_generated": cypher_res.get("cypher", ""),
        "cypher_results": cypher_res.get("rows", []),
        "cypher_error": cypher_res.get("error"),
    }

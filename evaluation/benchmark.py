import json
import re
import time
from pathlib import Path

from graph.ontology import normalize_text
from retrieval.kag_engine import answer_question
from utils.config import OPENAI_API_KEY, OPENAI_JUDGE_MODEL
from utils.llm import create_chat_completion, create_openai_client

client = create_openai_client(OPENAI_API_KEY)


def _call_with_cooldown(fn, *args, **kwargs):
    """Executa chamada com espera progressiva (15s, 30s, 60s) para erros transitórios 429/503."""
    cooldowns = (15, 30, 60)
    for attempt in range(len(cooldowns) + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            err_text = f"{type(exc).__name__}: {exc}"
            is_transient = any(
                token in err_text for token in ("429", "RateLimit", "503")
            )
            if not is_transient or attempt >= len(cooldowns):
                raise
            wait_sec = cooldowns[attempt]
            print(
                f"Limite/instabilidade transitória ({type(exc).__name__}); "
                f"aguardando {wait_sec}s antes de tentar novamente...",
                flush=True,
            )
            time.sleep(wait_sec)

QUESTIONS_PATH = Path(__file__).resolve().parent / "questions.json"
REPORT_MD_PATH = Path(__file__).resolve().parent / "resultados_comparativos.md"
REPORT_JSON_PATH = Path(__file__).resolve().parent / "resultados_comparativos.json"

GRAPH_CITATION_RE = re.compile(r"\[[^\]]+\]\s*--\([^)]+\)-->\s*\[[^\]]+\]")
DOC_CITATION_RE = re.compile(r"\[Fonte:\s*[^\]]+\]", re.IGNORECASE)

JUDGE_SYSTEM_PROMPT = """
Você é um avaliador rigoroso de fidelidade factual (Hallucination Judge) para sistemas RAG/GraphRAG.
Você receberá APENAS:
1. A pergunta feita;
2. O contexto recuperado pelo sistema (ou '[SEM CONTEXTO]' no modo LLM puro);
3. A resposta gerada pelo sistema.

NÃO utilize conhecimento prévio externo para validar fatos. Julgue exclusivamente se todas as afirmações factuais, números, municípios, pragas e recomendações na resposta estão estritamente ancorados no contexto fornecido.
- Se não houver contexto ('[SEM CONTEXTO]') e o modelo inventar números específicos, fontes ou dados não fornecidos, faithfulness deve ser próximo de 0.0.
- Se o modelo responder honestamente que o contexto não traz a informação (sem inventar), faithfulness = 1.0.
- Se cada afirmação factual da resposta estiver suportada no contexto recuperado, faithfulness = 1.0.

Retorne exclusivamente JSON:
{
  "faithfulness": 0.0,
  "unsupported_claims": ["..."],
  "rationale": "Resumo curto da avaliação."
}
"""


def compute_entity_recall(answer: str, expected_entities: list[str]) -> float:
    """Calcula a proporção de termos/entidades esperadas presentes na resposta."""
    if not expected_entities:
        return 1.0
    norm_answer = normalize_text(answer)
    hits = sum(
        1 for term in expected_entities if normalize_text(term) in norm_answer
    )
    return round(hits / len(expected_entities), 4)


def compute_citation_score(answer: str) -> float:
    """Mede presença de citações explícitas de caminhos do grafo e fontes documentais."""
    has_graph_cite = bool(GRAPH_CITATION_RE.search(answer or ""))
    has_doc_cite = bool(DOC_CITATION_RE.search(answer or ""))
    if has_graph_cite and has_doc_cite:
        return 1.0
    if has_graph_cite or has_doc_cite:
        return 0.5
    return 0.0


def judge_faithfulness(
    question: str,
    context_text: str,
    answer: str,
) -> dict:
    """Avalia fidelidade estritamente contra o contexto recuperado usando OPENAI_JUDGE_MODEL."""
    shown_context = context_text.strip() if context_text and context_text.strip() else "[SEM CONTEXTO]"

    payload = (
        f"Pergunta:\n{question}\n\n"
        f"Contexto Recuperado:\n{shown_context}\n\n"
        f"Resposta Gerada:\n{answer}"
    )

    try:
        response = _call_with_cooldown(
            create_chat_completion,
            client,
            model=OPENAI_JUDGE_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": payload},
            ],
        )
        parsed = json.loads(response.choices[0].message.content or "{}")
        score = float(parsed.get("faithfulness", 0.0))
        score = max(0.0, min(1.0, score))
        return {
            "faithfulness": round(score, 4),
            "unsupported_claims": parsed.get("unsupported_claims", []),
            "rationale": parsed.get("rationale", ""),
        }
    except Exception as exc:
        return {
            "faithfulness": 0.0,
            "unsupported_claims": [],
            "rationale": f"Erro no avaliador: {exc}",
        }


def load_questions(path: Path = QUESTIONS_PATH) -> list[dict]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_summary(records: list[dict], modes: tuple[str, ...]) -> dict:
    summary = {}
    for mode in modes:
        mode_items = [
            r["results"][mode]
            for r in records
            if mode in r.get("results", {})
        ]
        n = len(mode_items) or 1
        avg_faith = sum(m["faithfulness"] for m in mode_items) / n
        summary[mode] = {
            "avg_faithfulness": round(avg_faith, 4),
            "hallucination_rate": round(1.0 - avg_faith, 4),
            "avg_entity_recall": round(
                sum(m["entity_recall"] for m in mode_items) / n, 4
            ),
            "avg_citation_score": round(
                sum(m["citation_score"] for m in mode_items) / n, 4
            ),
            "avg_confidence": round(
                sum(m["confidence"] for m in mode_items) / n, 4
            ),
        }
    return summary


def run_benchmark(
    questions_path: Path = QUESTIONS_PATH,
    output_md: Path = REPORT_MD_PATH,
    output_json: Path = REPORT_JSON_PATH,
    modes: tuple[str, ...] = ("no_context", "vector", "hybrid"),
    resume: bool = True,
) -> dict:
    """Executa o benchmark comparativo e exporta relatórios Markdown e JSON."""
    questions = load_questions(questions_path)
    out_json_path = Path(output_json)
    records_by_id: dict[str, dict] = {}

    if resume and out_json_path.exists():
        try:
            saved = json.loads(out_json_path.read_text(encoding="utf-8"))
            for prev in saved.get("records", []):
                if all(m in prev.get("results", {}) for m in modes):
                    records_by_id[prev["id"]] = prev
        except Exception:
            records_by_id = {}

    for idx, item in enumerate(questions, start=1):
        if item["id"] in records_by_id:
            print(
                f"[{idx}/{len(questions)}] {item['id']} ({item['category']}) restaurada do checkpoint",
                flush=True,
            )
            continue

        row = {
            "id": item["id"],
            "category": item["category"],
            "question": item["question"],
            "results": {},
        }
        for mode in modes:
            res = _call_with_cooldown(answer_question, item["question"], mode=mode)
            judge = judge_faithfulness(
                question=item["question"],
                context_text=res.get("context_text", ""),
                answer=res.get("answer", ""),
            )
            recall = compute_entity_recall(
                res.get("answer", ""),
                item.get("expected_entities", []),
            )
            cite = compute_citation_score(res.get("answer", ""))
            row["results"][mode] = {
                "answer": res.get("answer", ""),
                "confidence": res.get("confidence", 0.0),
                "entity_recall": recall,
                "faithfulness": judge["faithfulness"],
                "citation_score": cite,
                "paths_count": len(res.get("paths", [])),
                "chunks_count": len(res.get("chunks", [])),
                "cypher_generated": res.get("cypher_generated", ""),
                "rationale": judge["rationale"],
            }

        records_by_id[item["id"]] = row
        checkpoint_records = [
            records_by_id[q["id"]] for q in questions if q["id"] in records_by_id
        ]
        out_json_path.write_text(
            json.dumps(
                {
                    "summary": _build_summary(checkpoint_records, modes),
                    "records": checkpoint_records,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(
            f"[{idx}/{len(questions)}] {item['id']} ({item['category']}) concluída",
            flush=True,
        )

    records = [records_by_id[q["id"]] for q in questions if q["id"] in records_by_id]
    summary = _build_summary(records, modes)

    md_lines = [
        "# Benchmark Comparativo de Alucinação — AgroGraphRAG\n",
        f"Total de perguntas avaliadas: **{len(records)}**\n",
        "## Resumo Agregado (3 Modos)\n",
        "| Modo | Fidelidade Média (Faithfulness) | Taxa de Alucinação | Entity Recall | Citação Estrutural/Fonte | Confiança Média |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
    ]
    for mode in modes:
        s = summary[mode]
        md_lines.append(
            f"| `{mode}` | {s['avg_faithfulness']:.2%} | {s['hallucination_rate']:.2%} | "
            f"{s['avg_entity_recall']:.2%} | {s['avg_citation_score']:.2%} | {s['avg_confidence']:.2%} |"
        )

    md_lines.append("\n## Resultados por Pergunta\n")
    md_lines.append("| ID | Categoria | No-Context (Faith/Recall) | Vector (Faith/Recall) | Hybrid GraphRAG (Faith/Recall/Cite) |")
    md_lines.append("| :--- | :--- | :---: | :---: | :---: |")

    for r in records:
        nc = r["results"].get("no_context", {})
        vc = r["results"].get("vector", {})
        hy = r["results"].get("hybrid", {})
        md_lines.append(
            f"| {r['id']} | {r['category']} | "
            f"{nc.get('faithfulness', 0):.2f} / {nc.get('entity_recall', 0):.2f} | "
            f"{vc.get('faithfulness', 0):.2f} / {vc.get('entity_recall', 0):.2f} | "
            f"{hy.get('faithfulness', 0):.2f} / {hy.get('entity_recall', 0):.2f} / {hy.get('citation_score', 0):.2f} |"
        )

    Path(output_md).write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    Path(output_json).write_text(
        json.dumps({"summary": summary, "records": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {"summary": summary, "records": records}


if __name__ == "__main__":
    result = run_benchmark()
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))

# Benchmark Comparativo de Alucinação — AgroGraphRAG

Total de perguntas avaliadas: **12**

## Resumo Agregado (3 Modos)

| Modo | Fidelidade Média (Faithfulness) | Taxa de Alucinação | Entity Recall | Citação Estrutural/Fonte | Confiança Média |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `no_context` | 16.67% | 83.33% | 81.94% | 0.00% | 0.00% |
| `vector` | 100.00% | 0.00% | 56.94% | 41.67% | 49.59% |
| `hybrid` | 100.00% | 0.00% | 83.33% | 58.33% | 61.71% |

## Resultados por Pergunta

| ID | Categoria | No-Context (Faith/Recall) | Vector (Faith/Recall) | Hybrid GraphRAG (Faith/Recall/Cite) |
| :--- | :--- | :---: | :---: | :---: |
| Q01 | sncr | 0.00 / 0.67 | 1.00 / 0.00 | 1.00 / 1.00 / 0.50 |
| Q02 | sncr | 0.00 / 1.00 | 1.00 / 0.00 | 1.00 / 0.50 / 0.50 |
| Q03 | sncr | 1.00 / 0.50 | 1.00 / 1.00 | 1.00 / 1.00 / 0.50 |
| Q04 | ibge | 0.00 / 0.50 | 1.00 / 0.50 | 1.00 / 0.50 / 0.50 |
| Q05 | ibge | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 / 0.50 |
| Q06 | ibge | 0.00 / 1.00 | 1.00 / 0.33 | 1.00 / 0.33 / 1.00 |
| Q07 | embrapa | 0.00 / 1.00 | 1.00 / 0.50 | 1.00 / 1.00 / 0.50 |
| Q08 | embrapa | 0.00 / 1.00 | 1.00 / 0.33 | 1.00 / 0.67 / 0.50 |
| Q09 | embrapa | 0.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 / 0.50 |
| Q10 | multihop | 0.00 / 0.67 | 1.00 / 0.67 | 1.00 / 1.00 / 0.50 |
| Q11 | multihop | 0.00 / 0.50 | 1.00 / 0.50 | 1.00 / 1.00 / 0.50 |
| Q12 | multihop | 0.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |

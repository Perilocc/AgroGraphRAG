Queries de Teste:

MATCH (n:Entidade)
RETURN n.tipo AS tipo, count(n) AS quantidade
ORDER BY tipo;

MATCH (a:Entidade)-[r:RELACIONA]->(b:Entidade)
RETURN
    a.tipo AS origem,
    r.tipo AS relacionamento,
    b.tipo AS destino,
    count(r) AS quantidade
ORDER BY relacionamento;

MATCH (i:Entidade {tipo: 'ImovelRural'})
    -[r1:RELACIONA {tipo: 'LOCALIZADO_EM'}]->
    (m:Entidade)
RETURN i, r1, m
LIMIT 10;
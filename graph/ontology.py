import hashlib
import re
import unicodedata

ENTITIES = {
    "ImovelRural": {
        "description": "Imóvel rural cadastrado no SNCR.",
        "properties": ["codigo_sncr", "denominacao", "area_total"],
    },
    "Municipio": {
        "description": "Município onde o imóvel rural está localizado ou onde há produção agrícola.",
        "properties": ["codigo_ibge", "nome", "nome_normalizado", "uf"],
    },
    "Detentor": {
        "description": "Pessoa ou organização identificada como detentora no cadastro.",
        "properties": ["identificador", "nome", "natureza_juridica"],
    },
    "RegistroDetencao": {
        "description": "Registro do vínculo entre um detentor e um imóvel.",
        "properties": ["condicao_pessoa", "percentual_detencao"],
    },
    "Documento": {
        "description": "Fonte documental utilizada na construção do grafo.",
        "properties": ["nome", "origem"],
    },
    "CulturaAgricola": {
        "description": "Cultura agrícola cultivada ou estudada (ex.: Milho, Soja, Café).",
        "properties": ["nome", "tipo"],
    },
    "Praga": {
        "description": "Praga, doença ou organismo prejudicial às culturas agrícolas.",
        "properties": ["nome", "tipo"],
    },
    "PraticaAgricola": {
        "description": "Técnica de manejo, conservação ou controle agrícola.",
        "properties": ["nome", "tipo"],
    },
    "ProdutoAgricola": {
        "description": "Insumo, defensivo, bioinsumo, cultivar ou produto derivado.",
        "properties": ["nome", "tipo"],
    },
    "CondicaoAmbiental": {
        "description": "Condição climática, edáfica, hídrica ou de solo.",
        "properties": ["nome", "tipo"],
    },
    "Bioma": {
        "description": "Bioma ou ecossistema regional.",
        "properties": ["nome", "tipo"],
    },
    "Regiao": {
        "description": "Região geográfica ou microrregião agrícola.",
        "properties": ["nome", "tipo"],
    },
    "Estado": {
        "description": "Unidade Federativa do Brasil.",
        "properties": ["nome", "uf"],
    },
    "Instituicao": {
        "description": "Órgão de pesquisa, ensino, extensão ou fomento agrícola.",
        "properties": ["nome", "tipo"],
    },
    "Pessoa": {
        "description": "Autor, pesquisador, técnico ou produtor citado em documentos.",
        "properties": ["nome", "tipo"],
    },
}

RELATIONSHIPS = {
    "LOCALIZADO_EM": {
        "source": "ImovelRural",
        "target": "Municipio",
        "allowed_pairs": [("ImovelRural", "Municipio")],
    },
    "POSSUI_DETENCAO": {
        "source": "ImovelRural",
        "target": "RegistroDetencao",
        "allowed_pairs": [("ImovelRural", "RegistroDetencao")],
    },
    "REFERENTE_A": {
        "source": "RegistroDetencao",
        "target": "Detentor",
        "allowed_pairs": [("RegistroDetencao", "Detentor")],
    },
    "EXTRAIDO_DE": {
        "source": "ImovelRural",
        "target": "Documento",
        "allowed_pairs": [("*", "Documento"), ("*", "Trecho")],
    },
    "PRODUZ": {
        "source": "Municipio",
        "target": "CulturaAgricola",
        "allowed_pairs": [("Municipio", "CulturaAgricola")],
    },
}

RELATION_TYPE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


def normalize_text(text: str) -> str:
    """Remove acentos, normaliza espaços e converte para minúsculas."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(text).strip())
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    collapsed = re.sub(r"\s+", " ", stripped.casefold())
    return collapsed.strip()


TYPE_ALIASES = {
    "imovelrural": "ImovelRural",
    "imovel rural": "ImovelRural",
    "propriedade rural": "ImovelRural",
    "propriedade": "ImovelRural",
    "municipio": "Municipio",
    "cidade": "Municipio",
    "detentor": "Detentor",
    "registrodetencao": "RegistroDetencao",
    "registro de detencao": "RegistroDetencao",
    "documento": "Documento",
    "culturaagricola": "CulturaAgricola",
    "cultura agricola": "CulturaAgricola",
    "cultura": "CulturaAgricola",
    "praga": "Praga",
    "doenca": "Praga",
    "praticaagricola": "PraticaAgricola",
    "pratica agricola": "PraticaAgricola",
    "pratica": "PraticaAgricola",
    "manejo": "PraticaAgricola",
    "produtoagricola": "ProdutoAgricola",
    "produto agricola": "ProdutoAgricola",
    "insumo": "ProdutoAgricola",
    "condicaoambiental": "CondicaoAmbiental",
    "condicao ambiental": "CondicaoAmbiental",
    "clima": "CondicaoAmbiental",
    "solo": "CondicaoAmbiental",
    "bioma": "Bioma",
    "regiao": "Regiao",
    "estado": "Estado",
    "uf": "Estado",
    "instituicao": "Instituicao",
    "organizacao": "Instituicao",
    "pessoa": "Pessoa",
}

SYNONYM_MAP = {
    ("CulturaAgricola", "milho"): "Milho",
    ("CulturaAgricola", "milho (em grao)"): "Milho",
    ("CulturaAgricola", "cultura do milho"): "Milho",
    ("CulturaAgricola", "zea mays"): "Milho",
    ("CulturaAgricola", "milho safrinha"): "Milho",
    ("CulturaAgricola", "milho segunda safra"): "Milho",
    ("CulturaAgricola", "soja"): "Soja",
    ("CulturaAgricola", "soja (em grao)"): "Soja",
    ("CulturaAgricola", "cultura da soja"): "Soja",
    ("CulturaAgricola", "glycine max"): "Soja",
    ("CulturaAgricola", "cafe"): "Café",
    ("CulturaAgricola", "cafe (em grao) total"): "Café",
    ("CulturaAgricola", "cultura do cafe"): "Café",
    ("CulturaAgricola", "coffea"): "Café",
    ("CulturaAgricola", "sorgo"): "Sorgo",
    ("CulturaAgricola", "feijao"): "Feijão",
    ("CulturaAgricola", "algodao"): "Algodão",
    ("Praga", "lagarta-do-cartucho"): "Lagarta-do-cartucho",
    ("Praga", "lagarta do cartucho"): "Lagarta-do-cartucho",
    ("Praga", "lagarta-do-cartucho do milho"): "Lagarta-do-cartucho",
    ("Praga", "spodoptera frugiperda"): "Lagarta-do-cartucho",
    ("Praga", "percevejo-marrom"): "Percevejo-marrom",
    ("Praga", "percevejo marrom"): "Percevejo-marrom",
    ("Praga", "euschistus heros"): "Percevejo-marrom",
    ("Praga", "cigarrinha-do-milho"): "Cigarrinha-do-milho",
    ("Praga", "cigarrinha do milho"): "Cigarrinha-do-milho",
    ("Praga", "dalbulus maidis"): "Cigarrinha-do-milho",
    ("Praga", "lagarta-da-soja"): "Lagarta-da-soja",
    ("Praga", "lagarta da soja"): "Lagarta-da-soja",
    ("Praga", "anticarsia gemmatalis"): "Lagarta-da-soja",
    ("Praga", "helicoverpa armigera"): "Helicoverpa armigera",
    ("Praga", "lagarta helicoverpa"): "Helicoverpa armigera",
    ("Instituicao", "embrapa"): "Embrapa",
    ("Instituicao", "empresa brasileira de pesquisa agropecuaria"): "Embrapa",
    ("Estado", "pb"): "Paraíba",
    ("Estado", "paraiba"): "Paraíba",
    ("Estado", "pr"): "Paraná",
    ("Estado", "parana"): "Paraná",
    ("Estado", "mt"): "Mato Grosso",
    ("Estado", "mato grosso"): "Mato Grosso",
    ("Estado", "go"): "Goiás",
    ("Estado", "goias"): "Goiás",
    ("Estado", "rs"): "Rio Grande do Sul",
    ("Estado", "sp"): "São Paulo",
    ("Estado", "mg"): "Minas Gerais",
    ("Estado", "pe"): "Pernambuco",
    ("Estado", "rn"): "Rio Grande do Norte",
    ("Estado", "ce"): "Ceará",
}


def canonicalize_entity_type(raw_type: str) -> str | None:
    """Converte um tipo textual para o label PascalCase da ontologia."""
    if not raw_type:
        return None
    cleaned = raw_type.strip()
    if cleaned in ENTITIES:
        return cleaned
    return TYPE_ALIASES.get(normalize_text(cleaned))


def canonicalize_entity_name(name: str, canonical_type: str) -> str:
    """Aplica o dicionário de sinônimos mantendo a forma canônica."""
    cleaned = re.sub(r"\s+", " ", (name or "").strip())
    norm = normalize_text(cleaned)
    return SYNONYM_MAP.get((canonical_type, norm), cleaned)


def canonicalize_entity(name: str, raw_type: str) -> tuple[str, str, str] | None:
    """Retorna (id_deterministico, nome_canonico, tipo_pascal) para uma entidade."""
    canonical_type = canonicalize_entity_type(raw_type)
    if not canonical_type or not name or not name.strip():
        return None

    canonical_name = canonicalize_entity_name(name, canonical_type)
    norm_name = normalize_text(canonical_name)
    if not norm_name:
        return None

    content = f"{canonical_type.casefold()}:{norm_name}"
    entity_id = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return entity_id, canonical_name, canonical_type


def sanitize_relation_type(raw_rel: str) -> str | None:
    """Sanitiza um tipo de relacionamento para MAIUSCULAS_COM_UNDERSCORE."""
    if not raw_rel:
        return None
    decomposed = unicodedata.normalize("NFKD", str(raw_rel).strip())
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    upper = re.sub(r"[^A-Za-z0-9]+", "_", upper_str := ascii_only.upper()).strip("_")
    upper = re.sub(r"_+", "_", upper)
    if upper == "EXTRAIDA_DE":
        upper = "EXTRAIDO_DE"
    if not RELATION_TYPE_PATTERN.match(upper):
        return None
    return upper


def validate_entity(entity: dict) -> bool:
    entity_type = entity.get("type")

    if entity_type not in ENTITIES:
        return False

    required = {"id", "name"}
    return required.issubset(entity.keys())


def validate_relationship(relationship: dict) -> bool:
    relation_type = relationship.get("type")
    source_type = relationship.get("source_type")
    target_type = relationship.get("target_type")

    if not relation_type or not RELATION_TYPE_PATTERN.match(relation_type):
        return False

    if relation_type in RELATIONSHIPS:
        definition = RELATIONSHIPS[relation_type]
        allowed_pairs = definition.get(
            "allowed_pairs",
            [(definition["source"], definition["target"])],
        )
        for src_rule, tgt_rule in allowed_pairs:
            src_ok = (src_rule == "*" and source_type in ENTITIES) or (source_type == src_rule)
            tgt_ok = (tgt_rule == "*" and target_type in ENTITIES) or (target_type == tgt_rule)
            if src_ok and tgt_ok:
                return True
        return False

    return source_type in ENTITIES and target_type in ENTITIES

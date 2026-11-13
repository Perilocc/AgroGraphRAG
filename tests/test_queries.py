from graph import queries
import pytest


class FakeRecord:
    def __init__(self, payload=None):
        self._payload = payload or {
            "codigo_ibge": "2507507",
            "municipio": "João Pessoa",
            "uf": "PB",
            "total_imoveis": 100,
            "area_total_cadastrada": 5000.0,
            "codigo_sncr": "123456",
            "denominacao": "Fazenda Teste",
            "area_total": 5000.0,
            "condicao_pessoa": "Proprietario Ou Posseiro Individual",
            "total_registros": 90,
            "percentual_medio_detencao": 100.0,
            "cultura": "Milho",
            "ano": 2025,
            "area_plantada_ha": 120.0,
            "quantidade_ton": 240.0,
            "label": "ImovelRural",
            "tipo": "LOCALIZADO_EM",
            "total": 100,
        }

    def data(self):
        return self._payload


class FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def run(self, query, **parameters):
        return [FakeRecord()]


class FakeDriver:
    def session(self):
        return FakeSession()

    def close(self):
        pass


def test_get_imoveis_por_municipio():
    original_driver = queries.get_driver
    queries.get_driver = lambda: FakeDriver()

    try:
        result = queries.get_imoveis_por_municipio(limit=10)

        assert len(result) == 1
        assert result[0]["municipio"] == "João Pessoa"
        assert result[0]["total_imoveis"] == 100
    finally:
        queries.get_driver = original_driver


def test_get_imoveis_por_municipio_limite_invalido():
    with pytest.raises(ValueError):
        queries.get_imoveis_por_municipio(limit=0)


def test_get_imoveis_por_area():
    original_driver = queries.get_driver
    queries.get_driver = lambda: FakeDriver()

    try:
        result = queries.get_imoveis_por_area(
            min_area=100,
            limit=10,
        )

        assert len(result) == 1
        assert result[0]["area_total"] == 5000.0
    finally:
        queries.get_driver = original_driver


def test_get_imoveis_por_area_limite_invalido():
    with pytest.raises(ValueError):
        queries.get_imoveis_por_area(min_area=100, limit=0)


def test_get_imoveis_por_area_area_negativa():
    with pytest.raises(ValueError):
        queries.get_imoveis_por_area(min_area=-1)


def test_get_imoveis_com_detentores():
    original_driver = queries.get_driver
    queries.get_driver = lambda: FakeDriver()

    try:
        result = queries.get_imoveis_com_detentores(
            codigo_municipio="2507507",
            limit=10,
        )

        assert len(result) == 1
        assert result[0]["municipio"] == "João Pessoa"

    finally:
        queries.get_driver = original_driver


def test_get_imoveis_com_detentores_codigo_vazio():
    with pytest.raises(ValueError):
        queries.get_imoveis_com_detentores(
            codigo_municipio="",
        )


def test_get_distribuicao_condicoes_detencao():
    original_driver = queries.get_driver
    queries.get_driver = lambda: FakeDriver()

    try:
        result = queries.get_distribuicao_condicoes_detencao()
        assert len(result) == 1
        assert result[0]["total_registros"] == 90
    finally:
        queries.get_driver = original_driver


def test_get_imoveis_por_condicao_detencao():
    original_driver = queries.get_driver
    queries.get_driver = lambda: FakeDriver()

    try:
        result = queries.get_imoveis_por_condicao_detencao(condicao="Proprietario", limit=5)
        assert len(result) == 1
        assert result[0]["codigo_sncr"] == "123456"
    finally:
        queries.get_driver = original_driver


def test_get_imoveis_por_condicao_detencao_invalido():
    with pytest.raises(ValueError):
        queries.get_imoveis_por_condicao_detencao(condicao="")


def test_get_producao_agricola_municipios():
    original_driver = queries.get_driver
    queries.get_driver = lambda: FakeDriver()

    try:
        result = queries.get_producao_agricola_municipios(cultura="Milho", limit=5)
        assert len(result) == 1
        assert result[0]["cultura"] == "Milho"
    finally:
        queries.get_driver = original_driver


def test_get_resumo_grafo():
    original_driver = queries.get_driver
    queries.get_driver = lambda: FakeDriver()

    try:
        result = queries.get_resumo_grafo()
        assert "labels" in result
        assert "relationships" in result
        assert result["labels"][0]["total"] == 100
    finally:
        queries.get_driver = original_driver

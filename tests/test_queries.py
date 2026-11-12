from graph import queries
import pytest

class FakeRecord:
    def data(self):
        return {
            "codigo_ibge": "2507507",
            "municipio": "João Pessoa",
            "uf": "PB",
            "total_imoveis": 100,
            "area_total_cadastrada": 5000.0,
            "codigo_sncr": "123456",
            "denominacao": "Fazenda Teste",
            "area_total": 5000.0,
        }


class FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def run(self, query, **parameters):
        assert "LOCALIZADO_EM" in query
        assert parameters["limit"] == 10
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
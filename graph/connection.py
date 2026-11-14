import atexit
import logging
import os
import threading
import certifi
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired

logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    if os.environ.get("SSL_CERT_FILE") in (None, "", "/etc/ssl/cert.pem"):
        os.environ["SSL_CERT_FILE"] = certifi.where()

from utils.config import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    NEO4J_DATABASE,
    validate_config,
)

_driver = None
_driver_lock = threading.Lock()


def get_driver():
    """Retorna uma instância singleton em cache do driver Neo4j."""
    global _driver

    if _driver is None:
        with _driver_lock:
            if _driver is None:
                validate_config(require_openai=False)
                _driver = GraphDatabase.driver(
                    NEO4J_URI,
                    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
                    max_connection_lifetime=300,
                    liveness_check_timeout=30.0,
                    connection_timeout=30.0,
                    keep_alive=True,
                )

    return _driver


def reset_driver():
    """Descarta o driver em cache para forçar reconexão limpa em caso de socket obsoleto."""
    close_driver()


def is_transient_neo4j_error(exc: Exception) -> bool:
    """Identifica erros transitórios de leitura/conexão com o Neo4j Aura."""
    if isinstance(exc, (ServiceUnavailable, SessionExpired, TimeoutError, OSError)):
        return True
    msg = str(exc).lower()
    return any(
        token in msg
        for token in ("defunct connection", "timed out", "connection reset", "broken pipe", "service unavailable")
    )


def get_session(driver=None):
    """Abre uma sessão configurada com NEO4J_DATABASE quando definido."""
    drv = driver or get_driver()

    if NEO4J_DATABASE:
        try:
            return drv.session(database=NEO4J_DATABASE)
        except TypeError:
            return drv.session()

    return drv.session()


def close_driver():
    """Fecha o driver em cache ao encerrar a aplicação."""
    global _driver

    with _driver_lock:
        if _driver is not None:
            _driver.close()
            _driver = None


atexit.register(close_driver)


def test_connection() -> bool:
    driver = get_driver()
    driver.verify_connectivity()
    return True

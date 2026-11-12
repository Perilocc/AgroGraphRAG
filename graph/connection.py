from neo4j import GraphDatabase

from utils.config import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    validate_config,
)


def get_driver():
    validate_config()

    return GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )


def test_connection():
    driver = get_driver()

    try:
        driver.verify_connectivity()
        return True
    finally:
        driver.close()

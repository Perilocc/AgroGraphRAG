from graph.connection import test_connection as check_neo4j_connection

def test_neo4j_connection():
    assert check_neo4j_connection() is True
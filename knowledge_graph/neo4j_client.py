from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from utils.config import Settings


@contextmanager
def neo4j_session(settings: Settings) -> Iterator:
    try:
        from neo4j import GraphDatabase
    except ImportError as error:
        raise RuntimeError("Install the neo4j package or set USE_MOCK_NEO4J=true.") from error

    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    try:
        with driver.session(database=settings.neo4j_database) as session:
            yield session
    finally:
        driver.close()


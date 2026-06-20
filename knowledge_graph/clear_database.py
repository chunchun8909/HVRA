from __future__ import annotations

from utils.config import Settings
from .neo4j_client import neo4j_session


def clear_database(settings: Settings) -> None:
    if settings.use_mock_neo4j:
        print("[HVRA][Mock Neo4j] clear_database skipped.")
        return

    with neo4j_session(settings) as session:
        session.run("MATCH (n) DETACH DELETE n")


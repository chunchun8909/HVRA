from __future__ import annotations


MINIMUM_SCHEMA = [
    "(Case)-[:HAS_ROOM]->(Room)",
    "(Room)-[:HAS_WALL]->(Wall)",
    "(Wall)-[:HAS_WINDOW]->(Window)",
    "(Wall)-[:HAS_DOOR]->(Door)",
    "(Room)-[:HAS_DOOR]->(Door)",
    "(Wall)-[:HAS_FURNITURE]->(Furniture)",
    "(Room)-[:HAS_FURNITURE]->(Furniture)",
    "(Room)-[:HAS_PROBLEM]->(Problem)",
    "(Window)-[:CONTRIBUTES_TO]->(Problem)",
    "(Problem)-[:CAN_BE_ADDRESSED_BY]->(Strategy)",
    "(UserSelection)-[:SELECTS]->(Strategy)",
    "(UserSelection)-[:RESPONDS_TO]->(Problem)",
]

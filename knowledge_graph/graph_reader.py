from __future__ import annotations


VISUALIZATION_QUERIES = {
    "case_path": "MATCH p=(:Building)-[:HAS_ROOM]->(:Room)-[*1..5]->() RETURN p LIMIT 50",
    "problem_strategy": "MATCH p=(:Problem)-[:CAN_BE_ADDRESSED_BY]->(:Strategy) RETURN p LIMIT 50",
}


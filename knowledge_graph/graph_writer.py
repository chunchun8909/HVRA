from __future__ import annotations

import json
from typing import Any

from utils.config import Settings
from .cypher_templates import CONSTRAINTS
from .neo4j_client import neo4j_session


def _flat(properties: dict[str, Any]) -> dict[str, Any]:
    flat = {}
    for key, value in properties.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            flat[key] = value
        else:
            flat[key] = json.dumps(value, ensure_ascii=False)
    return flat


def _mock_write(label: str, payload: dict) -> None:
    print(f"[HVRA][Mock Neo4j] {label}: {json.dumps(payload, ensure_ascii=False)[:600]}")


def _component_index(component_id: str, prefix: str) -> int | None:
    try:
        return int(component_id.rsplit(f"_{prefix}_", 1)[1])
    except (IndexError, ValueError):
        try:
            return int(component_id.rsplit("_", 1)[1])
        except (IndexError, ValueError):
            return None


def _component_props(
    component: dict,
    typology: str,
    prefix: str,
    wall_id_map: dict[str, str],
    wall_display_map: dict[str, str],
    sequence_index: int | None = None,
) -> dict:
    wall_id = wall_id_map.get(component.get("wall_id"), component.get("wall_id"))
    index = sequence_index or _component_index(component.get("id", ""), prefix)
    local_index = f"{prefix}{index:02d}" if index is not None else prefix
    wall_display = wall_display_map.get(component.get("wall_id"), "W??")
    display_index = f"{wall_display}-{local_index}"
    return {
        **component,
        "source_wall_id": component.get("wall_id"),
        "wall_id": wall_id,
        "index": index,
        "display_index": display_index,
        "typology": typology,
        "display_name": f"{display_index} | {typology.title()}",
    }


def _bim_walls(spatial_index: dict) -> tuple[list[dict], dict[str, str]]:
    walls = spatial_index.get("walls", [])
    enriched_walls = []
    wall_id_map = {}
    for index, wall in enumerate(walls, start=1):
        display_index = f"W{index:02d}"
        enriched_walls.append(
            {
                **wall,
                "index": index,
                "display_index": display_index,
                "typology": "wall",
                "display_name": f"{display_index} | Wall | {wall.get('orientation', 'UNKNOWN')}",
                "source": wall.get("source", "lgtnet_scaled_wall"),
            }
        )
        wall_id_map[wall["id"]] = wall["id"]
    return enriched_walls, wall_id_map


def _create_constraints(tx) -> None:
    for statement in CONSTRAINTS:
        tx.run(statement)


def initialize_graph(settings: Settings) -> None:
    if settings.use_mock_neo4j:
        _mock_write("initialize_graph", {"constraints": len(CONSTRAINTS)})
        return

    with neo4j_session(settings) as session:
        session.execute_write(_create_constraints)


def write_spatial_graph(spatial_index: dict, settings: Settings) -> None:
    if settings.use_mock_neo4j:
        _mock_write("write_spatial_graph", spatial_index)
        return

    def _write(tx):
        building = _flat(
            {
                **spatial_index["building"],
                "index": 1,
                "display_index": "B01",
                "typology": "building",
                "display_name": "B01 | Building",
            }
        )
        room = _flat(
            {
                **spatial_index["room"],
                "index": 1,
                "display_index": "R01",
                "typology": "room",
                "display_name": f"R01 | Room | {spatial_index['room'].get('room_type', 'room')}",
            }
        )
        walls, wall_id_map = _bim_walls(spatial_index)
        wall_display_map = {}
        for wall in walls:
            for source_wall_id in wall.get("source_wall_ids", [wall["id"]]):
                wall_display_map[source_wall_id] = wall.get("display_index", wall["id"])
        tx.run("MERGE (b:Building {id: $id}) SET b += $props", id=building["id"], props=building)
        tx.run("MERGE (r:Room {id: $id}) SET r += $props", id=room["id"], props=room)
        tx.run(
            """
            MATCH (r:Room {id: $room_id})-[:HAS_WALL]->(w:Wall)
            OPTIONAL MATCH (w)-[:HAS_WINDOW|HAS_DOOR|HAS_FURNITURE]->(component)
            DETACH DELETE component, w
            """,
            room_id=room["id"],
        )
        tx.run(
            """
            MATCH (r:Room {id: $room_id})-[:HAS_DOOR|HAS_FURNITURE]->(component)
            DETACH DELETE component
            """,
            room_id=room["id"],
        )
        tx.run(
            "MATCH (b:Building {id: $building_id}), (r:Room {id: $room_id}) MERGE (b)-[:HAS_ROOM]->(r)",
            building_id=building["id"],
            room_id=room["id"],
        )
        component_sequence: dict[tuple[str | None, str], int] = {}
        for wall in walls:
            props = _flat(
                {
                    "typology": "wall",
                    **wall,
                    "display_name": wall.get(
                        "display_name",
                        f"{wall.get('display_index', wall.get('id'))} | Wall | {wall.get('orientation', '')}",
                    ),
                }
            )
            tx.run("MERGE (w:Wall {id: $id}) SET w += $props", id=props["id"], props=props)
            tx.run(
                "MATCH (r:Room {id: $room_id}), (w:Wall {id: $wall_id}) MERGE (r)-[:HAS_WALL]->(w)",
                room_id=room["id"],
                wall_id=props["id"],
            )
        for window in spatial_index.get("windows", []):
            mapped_wall_id = wall_id_map.get(window.get("wall_id"), window.get("wall_id"))
            key = (mapped_wall_id, "window")
            component_sequence[key] = component_sequence.get(key, 0) + 1
            props = _flat(
                _component_props(window, "window", "WIN", wall_id_map, wall_display_map, component_sequence[key])
            )
            tx.run("MERGE (win:Window {id: $id}) SET win += $props", id=props["id"], props=props)
            tx.run(
                "MATCH (w:Wall {id: $wall_id}), (win:Window {id: $window_id}) MERGE (w)-[:HAS_WINDOW]->(win)",
                wall_id=props["wall_id"],
                window_id=props["id"],
            )
        for door in spatial_index.get("doors", []):
            mapped_wall_id = wall_id_map.get(door.get("wall_id"), door.get("wall_id"))
            key = (mapped_wall_id, "door")
            component_sequence[key] = component_sequence.get(key, 0) + 1
            props = _flat(_component_props(door, "door", "D", wall_id_map, wall_display_map, component_sequence[key]))
            tx.run("MERGE (d:Door {id: $id}) SET d += $props", id=props["id"], props=props)
            if props.get("wall_id"):
                tx.run(
                    "MATCH (w:Wall {id: $wall_id}), (d:Door {id: $door_id}) MERGE (w)-[:HAS_DOOR]->(d)",
                    wall_id=props["wall_id"],
                    door_id=props["id"],
                )
            else:
                tx.run(
                    "MATCH (r:Room {id: $room_id}), (d:Door {id: $door_id}) MERGE (r)-[:HAS_DOOR]->(d)",
                    room_id=room["id"],
                    door_id=props["id"],
                )
        for furniture in spatial_index.get("furniture", []):
            mapped_wall_id = wall_id_map.get(furniture.get("wall_id"), furniture.get("wall_id"))
            key = (mapped_wall_id, "furniture")
            component_sequence[key] = component_sequence.get(key, 0) + 1
            props = _flat(
                _component_props(furniture, "furniture", "F", wall_id_map, wall_display_map, component_sequence[key])
            )
            tx.run("MERGE (f:Furniture {id: $id}) SET f += $props", id=props["id"], props=props)
            if props.get("wall_id"):
                tx.run(
                    "MATCH (w:Wall {id: $wall_id}), (f:Furniture {id: $furniture_id}) "
                    "MERGE (w)-[:HAS_FURNITURE]->(f)",
                    wall_id=props["wall_id"],
                    furniture_id=props["id"],
                )
            else:
                tx.run(
                    "MATCH (r:Room {id: $room_id}), (f:Furniture {id: $furniture_id}) "
                    "MERGE (r)-[:HAS_FURNITURE]->(f)",
                    room_id=room["id"],
                    furniture_id=props["id"],
                )

    with neo4j_session(settings) as session:
        session.execute_write(_write)


def write_diagnosis_graph(problem_map: dict, settings: Settings) -> None:
    if settings.use_mock_neo4j:
        _mock_write("write_diagnosis_graph", problem_map)
        return

    def _write(tx):
        room_id = problem_map["room_id"]
        for problem in problem_map.get("problems", []):
            props = _flat(problem)
            tx.run("MERGE (p:Problem {id: $id}) SET p += $props", id=props["id"], props=props)
            tx.run(
                "MATCH (r:Room {id: $room_id}), (p:Problem {id: $problem_id}) MERGE (r)-[:HAS_PROBLEM]->(p)",
                room_id=room_id,
                problem_id=props["id"],
            )
            for contributor_id in problem.get("contributors", []):
                tx.run(
                    """
                    MATCH (p:Problem {id: $problem_id})
                    MATCH (n {id: $contributor_id})
                    MERGE (n)-[:CONTRIBUTES_TO]->(p)
                    """,
                    problem_id=props["id"],
                    contributor_id=contributor_id,
                )

    with neo4j_session(settings) as session:
        session.execute_write(_write)


def write_decision_graph(user_selection: dict, settings: Settings) -> None:
    if settings.use_mock_neo4j:
        _mock_write("write_decision_graph", user_selection)
        return

    def _write(tx):
        selection = _flat(user_selection)
        tx.run("MERGE (s:UserSelection {id: $id}) SET s += $props", id=selection["id"], props=selection)
        strategy = user_selection["selected_strategy"]
        strategy_props = _flat(strategy)
        tx.run("MERGE (st:Strategy {id: $id}) SET st += $props", id=strategy_props["strategy_id"], props=strategy_props)
        tx.run(
            """
            MATCH (s:UserSelection {id: $selection_id})
            MATCH (st:Strategy {id: $strategy_id})
            MERGE (s)-[:SELECTS]->(st)
            """,
            selection_id=selection["id"],
            strategy_id=strategy["strategy_id"],
        )
        for problem_id in user_selection.get("responds_to_problem_ids", []):
            tx.run(
                """
                MATCH (s:UserSelection {id: $selection_id})
                MATCH (p:Problem {id: $problem_id})
                MATCH (st:Strategy {id: $strategy_id})
                MERGE (s)-[:RESPONDS_TO]->(p)
                MERGE (p)-[:CAN_BE_ADDRESSED_BY]->(st)
                """,
                selection_id=selection["id"],
                problem_id=problem_id,
                strategy_id=strategy["strategy_id"],
            )

    with neo4j_session(settings) as session:
        session.execute_write(_write)


def write_checkpoint_graph(checkpoint: dict, stage_result: dict, user_decision: dict, settings: Settings) -> None:
    payload = {
        "checkpoint": checkpoint,
        "stage_result": stage_result,
        "user_decision": user_decision,
    }
    if settings.use_mock_neo4j:
        _mock_write("write_checkpoint_graph", payload)
        return

    def _write(tx):
        checkpoint_id = checkpoint.get("checkpoint_name", checkpoint.get("stage", "checkpoint"))
        checkpoint_props = _flat(
            {
                "id": checkpoint_id,
                "stage": checkpoint.get("stage"),
                "status": checkpoint.get("status"),
                "primary_output": checkpoint.get("primary_output"),
                "allowed_actions": checkpoint.get("allowed_actions", []),
                "user_action": user_decision.get("action"),
                "user_reason": user_decision.get("reason"),
            }
        )
        tx.run("MERGE (c:Checkpoint {id: $id}) SET c += $props", id=checkpoint_id, props=checkpoint_props)
        room_id = stage_result.get("room_id")
        if room_id:
            tx.run(
                "MATCH (r:Room {id: $room_id}), (c:Checkpoint {id: $checkpoint_id}) "
                "MERGE (r)-[:HAS_CHECKPOINT]->(c)",
                room_id=room_id,
                checkpoint_id=checkpoint_id,
            )

        baseline = stage_result.get("baseline", {})
        for key, value in baseline.items():
            indicator_id = f"{checkpoint_id}_BASELINE_{key}"
            props = _flat({"id": indicator_id, "name": key, "value": value, "stage": checkpoint.get("stage")})
            tx.run("MERGE (i:BaselineIndicator {id: $id}) SET i += $props", id=indicator_id, props=props)
            tx.run(
                "MATCH (c:Checkpoint {id: $checkpoint_id}), (i:BaselineIndicator {id: $indicator_id}) "
                "MERGE (c)-[:HAS_BASELINE_INDICATOR]->(i)",
                checkpoint_id=checkpoint_id,
                indicator_id=indicator_id,
            )

        for option in stage_result.get("validated_options", []):
            strategy = option.get("strategy", {})
            strategy_id = strategy.get("strategy_id")
            if not strategy_id:
                continue
            strategy_props = _flat(strategy)
            validation_id = f"{checkpoint_id}_{strategy_id}_VALIDATION"
            validation_props = _flat(
                {
                    "id": validation_id,
                    "strategy_id": strategy_id,
                    "validation_rank": option.get("validation_rank"),
                    "benchmark_status": option.get("benchmark_result", {}).get("overall"),
                    "confidence_level": option.get("confidence", {}).get("level"),
                    "confidence_score": option.get("confidence", {}).get("score"),
                    "proposed_final_score": option.get("proposed", {}).get("final_score"),
                    "proposed_room_score": option.get("proposed", {}).get("composite_room_risk_score"),
                    "recommendation": option.get("recommendation"),
                    "numerical_comparison": option.get("numerical_comparison", []),
                }
            )
            tx.run(
                "MERGE (st:Strategy {id: $id}) SET st += $props",
                id=strategy_id,
                props=strategy_props,
            )
            tx.run(
                "MERGE (v:ValidationResult {id: $id}) SET v += $props",
                id=validation_id,
                props=validation_props,
            )
            tx.run(
                """
                MATCH (c:Checkpoint {id: $checkpoint_id})
                MATCH (st:Strategy {id: $strategy_id})
                MATCH (v:ValidationResult {id: $validation_id})
                MERGE (c)-[:REVIEWS_STRATEGY]->(st)
                MERGE (st)-[:HAS_VALIDATION_RESULT]->(v)
                MERGE (c)-[:HAS_VALIDATION_RESULT]->(v)
                """,
                checkpoint_id=checkpoint_id,
                strategy_id=strategy_id,
                validation_id=validation_id,
            )
            for problem_id in option.get("problem_targets", {}).keys():
                tx.run(
                    """
                    MATCH (st:Strategy {id: $strategy_id})
                    MATCH (p:Problem {id: $problem_id})
                    MERGE (st)-[:ADDRESSES]->(p)
                    """,
                    strategy_id=strategy_id,
                    problem_id=problem_id,
                )

    with neo4j_session(settings) as session:
        session.execute_write(_write)

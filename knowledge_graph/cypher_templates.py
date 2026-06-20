from __future__ import annotations


CONSTRAINTS = [
    "CREATE CONSTRAINT hvra_case_id IF NOT EXISTS FOR (n:Case) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT hvra_building_id IF NOT EXISTS FOR (n:Building) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT hvra_room_id IF NOT EXISTS FOR (n:Room) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT hvra_wall_id IF NOT EXISTS FOR (n:Wall) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT hvra_window_id IF NOT EXISTS FOR (n:Window) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT hvra_door_id IF NOT EXISTS FOR (n:Door) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT hvra_furniture_id IF NOT EXISTS FOR (n:Furniture) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT hvra_problem_id IF NOT EXISTS FOR (n:Problem) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT hvra_strategy_id IF NOT EXISTS FOR (n:Strategy) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT hvra_selection_id IF NOT EXISTS FOR (n:UserSelection) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT hvra_checkpoint_id IF NOT EXISTS FOR (n:Checkpoint) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT hvra_validation_id IF NOT EXISTS FOR (n:ValidationResult) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT hvra_indicator_id IF NOT EXISTS FOR (n:BaselineIndicator) REQUIRE n.id IS UNIQUE",
]

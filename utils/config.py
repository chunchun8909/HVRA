from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
INTERMEDIATE_DIR = DATA_DIR / "intermediate"
OUTPUT_DIR = DATA_DIR / "output"
SPATIAL_OUTPUT_DIR = OUTPUT_DIR / "spatial"
CHECKPOINT_DIR = DATA_DIR / "checkpoints"
RAG_DOCUMENTS_DIR = ROOT_DIR / "rag_engine" / "documents"
RAG_RAW_PDF_DIR = DATA_DIR / "raw_pdfs"
RAG_SOURCE_METADATA_JSON = DATA_DIR / "source_metadata.json"
RAG_PROCESSED_DIR = DATA_DIR / "processed"
RAG_PAGES_JSONL = RAG_PROCESSED_DIR / "corpus_pages.jsonl"
RAG_CHUNKS_JSONL = RAG_PROCESSED_DIR / "corpus_chunks.jsonl"
RAG_VECTOR_DB_DIR = DATA_DIR / "vector_db" / "chroma"
RAG_COLLECTION_NAME = "hvra_retrofit_guides"
RAG_CHUNK_SIZE = 900
RAG_CHUNK_OVERLAP = 150


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    use_mock_neo4j: bool
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    neo4j_database: str
    use_mock_llm: bool
    ollama_base_url: str
    ollama_model: str
    ollama_timeout_seconds: int
    ollama_retries: int
    use_mock_gemini: bool
    gemini_api_key: str
    gemini_model: str
    use_mock_lgtnet: bool
    lgtnet_root: str
    lgtnet_python: str
    use_mock_sam3: bool
    sam3_root: str
    sam3_python: str
    use_mock_risk_map: bool
    risk_map_data_root: str
    risk_map_bbox_radius_m: int
    use_synthetic_uhi: bool
    use_infrared_city: bool
    infrared_api_key: str
    infrared_base_url: str
    infrared_cache_json: str
    infrared_force_refresh: bool


def load_settings() -> Settings:
    _load_env_file(ROOT_DIR / ".env")

    return Settings(
        use_mock_neo4j=_bool_env("USE_MOCK_NEO4J", True),
        neo4j_uri=os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687"),
        neo4j_username=os.getenv("NEO4J_USERNAME", os.getenv("NEO4J_USER", "neo4j")),
        neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        use_mock_llm=_bool_env("USE_MOCK_LLM", True),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1"),
        ollama_timeout_seconds=int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180")),
        ollama_retries=int(os.getenv("OLLAMA_RETRIES", "2")),
        use_mock_gemini=_bool_env("USE_MOCK_GEMINI", True),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        use_mock_lgtnet=_bool_env("USE_MOCK_LGTNET", True),
        lgtnet_root=os.getenv("LGTNET_ROOT", r"C:\Users\Morris\OneDrive\Desktop\LGTNet"),
        lgtnet_python=os.getenv(
            "LGTNET_PYTHON",
            r"C:\Users\Morris\OneDrive\Desktop\LGTNet\.venv\Scripts\python.exe",
        ),
        use_mock_sam3=_bool_env("USE_MOCK_SAM3", True),
        sam3_root=os.getenv("SAM3_ROOT", r"C:\Users\Morris\OneDrive\Desktop\LGTNet\_sam3_test"),
        sam3_python=os.getenv(
            "SAM3_PYTHON",
            r"C:\Users\Morris\OneDrive\Desktop\LGTNet\_sam3_test\.venv-sam3\Scripts\python.exe",
        ),
        use_mock_risk_map=_bool_env("USE_MOCK_RISK_MAP", True),
        risk_map_data_root=os.getenv(
            "RISK_MAP_DATA_ROOT",
            str(ROOT_DIR / "risk_map" / "dataset"),
        ),
        risk_map_bbox_radius_m=int(os.getenv("RISK_MAP_BOUNDING_BOX_RADIUS_M", "250")),
        use_synthetic_uhi=_bool_env("USE_SYNTHETIC_UHI", True),
        use_infrared_city=_bool_env("USE_INFRARED_CITY", False),
        infrared_api_key=os.getenv("INFRARED_API_KEY", os.getenv("INFRARED_CITY_API_KEY", "")).strip(),
        infrared_base_url=os.getenv(
            "INFRARED_BASE_URL",
            os.getenv("INFRARED_CITY_BASE_URL", "https://api.infrared.city/v2"),
        ).rstrip("/"),
        infrared_cache_json=os.getenv(
            "INFRARED_CITY_CACHE_JSON",
            str(ROOT_DIR / "risk_map" / "dataset" / "infrared_city" / "infrared_city_context.json"),
        ),
        infrared_force_refresh=_bool_env("INFRARED_CITY_FORCE_REFRESH", False),
    )


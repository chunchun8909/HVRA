from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import zipfile
from pathlib import Path

zip_path = PROJECT_ROOT / "risk_map" / "dataset" / "ESP_CT_Barcelona-El.Prat.AP.081810_TMYx.2011-2025.zip"
with zipfile.ZipFile(zip_path) as z:
    files = [n for n in z.namelist() if n.endswith(".epw")]
    print(f"Found {len(files)} EPW files: {files}")
    if files:
        with z.open(files[0]) as f:
            content = f.read().decode("utf-8")
            lines = content.split("\n")
            print("\n=== EPW Header (Location & Design) ===")
            for i in range(min(3, len(lines))):
                print(f"Line {i}: {lines[i][:200]}")
            print("\n=== Sample Data Line ===")
            if len(lines) > 10:
                print(f"Data: {lines[10][:200]}")

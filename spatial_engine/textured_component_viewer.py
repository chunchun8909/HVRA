from __future__ import annotations

from pathlib import Path

from utils.config import ROOT_DIR, SPATIAL_OUTPUT_DIR
from .component_composition import write_component_composition


TEMPLATE_PATH = ROOT_DIR / "3D_test" / "one_wall_spatial_logic" / "textured_component_view_template.html"


def _production_html(html: str) -> str:
    """Strip the one-wall QA shell and let Phase 3 own option/report controls."""
    html = html.replace("<title>HVRA Textured Component Test</title>", "<title>room view</title>")
    html = html.replace(
        "#app{display:grid;grid-template-columns:280px 1fr 300px;height:100vh}",
        "#app{display:block;height:100vh}",
    )
    html = html.replace(
        ".panel{background:rgba(255,255,252,.95);border-right:1px solid var(--line);padding:16px;overflow:auto}",
        ".panel{display:none}",
    )
    html = html.replace("#stage{position:relative;min-width:0}", "#stage{position:relative;width:100vw;height:100vh;min-width:0}")
    html = html.replace(".hud{left:18px;top:18px;width:300px}", ".hud{display:none}")
    html = html.replace(".legend{right:18px;bottom:18px;width:255px}", ".legend{display:none}")
    html = html.replace("<h1>One Wall Logic</h1>", "<h1>Room Strategy Preview</h1>")
    html = html.replace("Textured wall 08 plus detailed mesh components. Host placement is read from <b>host_geometry.json</b>.", "3D retrofit components are placed from the selected Phase 3 option.")
    html = html.replace("const camera=new THREE.PerspectiveCamera(45,1,.1,80);camera.position.set(4.4,3.1,6.3);", "const camera=new THREE.PerspectiveCamera(45,1,.1,80);camera.position.set(4.4,2.8,5.6);")
    html = html.replace("clearState(composition.default_option_key||'all');", "const query=new URLSearchParams(location.search); const selectedKey=(query.get('strategy_id')||query.get('option')||composition.default_option_key||'option_1').split(',')[0]; clearState(selectedKey);")
    return html


def export_textured_component_view(output_path: Path | None = None) -> str:
    """Export the clean Phase 3 3D retrofit component view."""
    output = output_path or SPATIAL_OUTPUT_DIR / "room_3d_textured_component_test.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    write_component_composition(SPATIAL_OUTPUT_DIR / "component_composition.json")
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Missing textured component view template: {TEMPLATE_PATH}")
    html = _production_html(TEMPLATE_PATH.read_text(encoding="utf-8"))
    output.write_text(html, encoding="utf-8")
    return str(output)

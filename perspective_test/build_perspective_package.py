from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(__file__).resolve().parent
DEFAULT_IMAGE_DIR = PROJECT_ROOT / "data" / "input" / "images" / "perspective_image"
DEFAULT_OUTPUT_DIR = TEST_ROOT / "output"
CONTRACT_PATH = TEST_ROOT / "perspective_generation_contract.json"
SAMPLE_SELECTION_PATH = TEST_ROOT / "sample_selected_strategy.json"
VISUAL_CATALOGUE_PATH = PROJECT_ROOT / "3D_test" / "catalogues" / "retrofit_strategy_visual_catalogue.json"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'").strip()
    return values


def provider_config() -> dict[str, Any]:
    root_env = load_env_file(PROJECT_ROOT / ".env")
    local_env = load_env_file(TEST_ROOT / ".env")
    values = {**root_env, **local_env}
    return {
        "provider": "huggingface",
        "inference_provider": values.get("HF_IMAGE_PROVIDER", "auto"),
        "model": values.get("HF_IMAGE_EDIT_MODEL", "Qwen/Qwen-Image-Edit"),
        "token_configured": bool(values.get("HF_TOKEN") or values.get("HUGGINGFACE_TOKEN")),
        "api_reference": "https://huggingface.co/docs/inference-providers/guides/image-editor",
        "output_filename": values.get("HF_OUTPUT_FILENAME", "generated_perspective_hf.png"),
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def find_first_perspective_image(image_arg: str | None) -> Path:
    if image_arg:
        path = Path(image_arg)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if not path.exists():
            raise FileNotFoundError(f"Perspective image not found: {path}")
        return path

    candidates = [p for p in DEFAULT_IMAGE_DIR.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
    if not candidates:
        fallback_dir = PROJECT_ROOT / "data" / "input" / "images"
        candidates = [p for p in fallback_dir.iterdir() if p.is_file() and "perspective" in p.name.lower() and p.suffix.lower() in IMAGE_EXTENSIONS]
    if not candidates:
        raise FileNotFoundError("No perspective image found. Put one image in data/input/images/perspective_image/.")
    return sorted(candidates, key=lambda p: p.name.lower())[0]


def catalogue_lookup(strategy_id: str, visual_asset: str) -> dict[str, Any]:
    if not VISUAL_CATALOGUE_PATH.exists():
        return {}
    catalogue = read_json(VISUAL_CATALOGUE_PATH)
    for strategy in catalogue.get("strategies", []):
        if strategy.get("id") == strategy_id or visual_asset in strategy.get("visual_assets", []):
            return strategy
    return {}


def default_mode(strategy_id: str, visual_asset: str) -> str:
    if strategy_id == "solar_control_glazing_layer" or visual_asset == "solar_control_glazing_tint":
        return "image_edit_low_strength"
    return "image_edit_targeted_retrofit"


def build_prompt(selection: dict[str, Any], contract: dict[str, Any], catalogue_item: dict[str, Any], full_renovation: bool = False) -> dict[str, str]:
    strategy = selection["selected_strategy"]
    strategy_id = strategy["strategy_id"]
    visual_asset = strategy["visual_asset"]
    translation = contract["strategy_visual_translation"].get(
        strategy_id,
        catalogue_item.get("mounting", "show the selected retrofit intervention in the correct room zone"),
    )
    placement = selection.get("spatial_hint", {}).get("placement", catalogue_item.get("mounting", "selected target zone"))

    effects = strategy.get("expected_effect") or catalogue_item.get("screening_effects", {})
    effect_phrase = ""
    if effects:
        if "delta_t_min_c" in effects and "delta_t_max_c" in effects:
            effect_phrase = (
                f" The strategy is expected to reduce peak operative temperature by about "
                f"{effects['delta_t_min_c']} to {effects['delta_t_max_c']} C in screening terms."
            )
        elif "perceived_cooling_min_c" in effects and "perceived_cooling_max_c" in effects:
            effect_phrase = (
                f" The strategy mainly improves perceived cooling by about "
                f"{effects['perceived_cooling_min_c']} to {effects['perceived_cooling_max_c']} C."
            )

    if full_renovation:
        prompt_parts = [
            "Fully renovate the provided room perspective image into a high-quality architectural interior visualization.",
            "Keep the same camera angle, perspective, room envelope, window or sliding-door location, floor/ceiling boundaries, and main opening geometry, but redesign the visible interior finishes and atmosphere substantially.",
            "Create a coherent passive-cooling retrofit design for an older apartment: brighter clean wall finish, refined floor finish, calmer contemporary materials, improved daylight control, and a finished lived-in interior.",
            f"The renovation must clearly include this selected comfort strategy: {strategy_id} using {visual_asset}.",
            f"Place the strategy at: {placement}.",
            f"Design intent: {translation}.",
            "Make the selected strategy visually obvious but integrated into the whole room design, not pasted on top. It must be physically attached, correctly scaled, and aligned with the existing opening or host surface.",
            "You may add compatible interior elements only if they support the retrofit story: simple curtains/blinds, light natural materials, indoor plants near daylight, subtle wall finish upgrades, and uncluttered furniture. Keep circulation clear and do not block the sliding door/window operation.",
            "Use realistic contact shadows, material texture, depth, glazing reflections, daylight, and ambient occlusion. The image should look like a polished renovation photo or design-render, not a diagram.",
            "Do not add people, text, labels, arrows, heatmaps, construction drawings, split-screen before/after graphics, or unrelated decorative clutter.",
        ]
    else:
        prompt_parts = [
            "You are editing an existing interior perspective photograph for an architectural retrofit preview.",
            "Preserve at least 90 percent of the original image: same camera angle, perspective, room proportions, wall layout, floor, ceiling, window or door position, lighting direction, and existing material palette.",
            f"Selected retrofit strategy: {strategy_id}.",
            f"Visible asset to add or modify: {visual_asset}.",
            f"Target placement: {placement}.",
            f"Design intent: {translation}.",
            "Make the intervention realistic, quiet, and buildable for an older apartment. It should look like a real installed retrofit, not a concept diagram.",
            "Use correct scale, gravity, contact shadows, occlusion, and fixing details. Rails, brackets, awning arms, curtains, blinds, glazing tint, or plant supports must be attached to the correct wall/opening/ceiling surface.",
            "If the strategy is exterior but the image is taken from inside, keep the interior mostly unchanged and show only plausible visible evidence: an exterior edge, shaded daylight, softened solar glare, or a subtle shadow on the room surfaces.",
            "Do not add unrelated furniture, people, text, icons, labels, arrows, colored masks, diagnostic graphics, or decorative objects that are not part of the selected retrofit.",
        ]
    if effect_phrase:
        prompt_parts.append(effect_phrase.strip())
    if full_renovation:
        prompt_parts.append("The final image should read as a complete renovated-room proposal with the thermal retrofit strategy clearly integrated.")
    else:
        prompt_parts.append("The final image should read as a realistic before/after retrofit visualization suitable for a design report.")
    prompt = " ".join(prompt_parts).strip()

    negative_items = list(contract.get("negative_prompt_rules", []))
    negative_items.extend([
        "changed room geometry",
        "changed camera angle",
        "warped perspective",
        "extra windows or doors",
        "missing original window",
        "floating objects",
        "disconnected supports",
        "oversized retrofit components",
        "blocked sliding door operation",
        "plants or curtains passing through glass",
        "cartoon render",
        "plastic toy look",
        "low resolution",
        "blurry output",
        "text labels",
        "arrows",
        "bounding boxes",
        "heatmap overlay",
        "before and after split screen",
        "messy clutter",
        "luxury hotel style",
        "unrealistic structural demolition",
    ])
    negative = ", ".join(dict.fromkeys(item for item in negative_items if item))
    return {"prompt": prompt, "negative_prompt": negative}


def build_notes(package: dict[str, Any]) -> str:
    hf = package["huggingface"]
    return f"""# Hugging Face Perspective Generation Notes

## Source Image

`{package['source_image']}`

## Provider

`{hf['provider']}` / `{hf['inference_provider']}`

## Model

`{hf['model']}`

## Recommended Use

This test uses Hugging Face Inference Providers as the active cloud-only image-editing provider. It sends the original perspective image plus the selected retrofit prompt, then saves the returned image into `perspective_test/output/`.

## Prompt

{package['prompt']}

## Negative Guidance

{package['negative_prompt']}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Hugging Face perspective regeneration package for HVRA.")
    parser.add_argument("--image", help="Optional perspective image path. Defaults to data/input/images/perspective_image/ first image.")
    parser.add_argument("--strategy", help="Override strategy id.")
    parser.add_argument("--asset", help="Override visual asset.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output folder.")
    parser.add_argument("--full-renovation", action="store_true", help="Use a stronger prompt for full-room renovation testing.")
    args = parser.parse_args()

    contract = read_json(CONTRACT_PATH)
    selection = read_json(SAMPLE_SELECTION_PATH)
    if args.strategy:
        selection["selected_strategy"]["strategy_id"] = args.strategy
    if args.asset:
        selection["selected_strategy"]["visual_asset"] = args.asset

    strategy = selection["selected_strategy"]
    source_image = find_first_perspective_image(args.image)
    catalogue_item = catalogue_lookup(strategy["strategy_id"], strategy["visual_asset"])
    prompts = build_prompt(selection, contract, catalogue_item, full_renovation=args.full_renovation)
    hf_config = provider_config()

    package = {
        "package_id": f"HVRA_PERSPECTIVE_HUGGINGFACE_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "source_image": str(source_image),
        "room_id": selection.get("room_id", "ROOM_001"),
        "strategy": strategy,
        "spatial_hint": selection.get("spatial_hint", {}),
        "catalogue_match": catalogue_item,
        "huggingface": hf_config,
        "generation_settings": {
            "engine_target": "Hugging Face Inference Providers image-to-image",
            "mode": default_mode(strategy["strategy_id"], strategy["visual_asset"]),
            "preserve_camera": True,
            "preserve_room_geometry": True,
            "single_strategy_only": not args.full_renovation,
            "full_renovation_test": args.full_renovation,
        },
        **prompts,
    }

    out_dir = Path(args.output_dir)
    if not out_dir.is_absolute():
        out_dir = TEST_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "perspective_regeneration_package.json", package)
    (out_dir / "prompt.txt").write_text(package["prompt"], encoding="utf-8")
    (out_dir / "negative_prompt.txt").write_text(package["negative_prompt"], encoding="utf-8")
    (out_dir / "huggingface_notes.md").write_text(build_notes(package), encoding="utf-8")

    print(f"Source image: {source_image}")
    print(f"Wrote package: {out_dir / 'perspective_regeneration_package.json'}")
    print(f"Provider: {hf_config['provider']}")
    print(f"Model: {hf_config['model']}")


if __name__ == "__main__":
    main()




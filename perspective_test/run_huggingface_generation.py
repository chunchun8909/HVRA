from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path

from huggingface_hub import InferenceClient
from huggingface_hub.inference._providers import get_provider_helper
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(__file__).resolve().parent
DEFAULT_PACKAGE_PATH = TEST_ROOT / "output" / "perspective_regeneration_package.json"


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


def load_settings() -> dict[str, str]:
    root_env = load_env_file(PROJECT_ROOT / ".env")
    local_env = load_env_file(TEST_ROOT / ".env")
    values = {**root_env, **local_env}
    for key in (
        "HF_TOKEN",
        "HUGGINGFACE_TOKEN",
        "HF_IMAGE_PROVIDER",
        "HF_IMAGE_EDIT_MODEL",
        "HF_OUTPUT_FILENAME",
        "HF_TIMEOUT_SECONDS",
        "HF_GUIDANCE_SCALE",
        "HF_INFERENCE_STEPS",
        "HF_MIN_IMAGE_SIZE",
    ):
        if os.getenv(key):
            values[key] = os.getenv(key, "")
    return values


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_error(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(message, encoding="utf-8")


def prepare_provider_image(path: Path, min_size: int = 768) -> Path:
    image = Image.open(path).convert("RGB")
    width, height = image.size
    scale = max(min_size / width, min_size / height, 1.0)
    if scale > 1.0:
        new_size = (round(width * scale), round(height * scale))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    output_path = TEST_ROOT / "output" / "provider_input_image.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")
    return output_path


def image_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_prompt(package: dict) -> tuple[str, str]:
    prompt = package["prompt"]
    negative = package.get("negative_prompt", "")
    return prompt, negative


def save_image_response(response_bytes: bytes, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stripped = response_bytes[:80].lstrip()
    if stripped.startswith(b"{") or stripped.startswith(b"["):
        debug_path = output_path.with_suffix(".provider_response.json")
        debug_path.write_bytes(response_bytes)
        raise RuntimeError(f"Provider returned JSON instead of image bytes. Wrote {debug_path}")
    output_path.write_bytes(response_bytes)


def submit_to_huggingface(package: dict, settings: dict[str, str]) -> Path:
    token = settings.get("HF_TOKEN") or settings.get("HUGGINGFACE_TOKEN")
    if not token:
        raise RuntimeError("Missing HF_TOKEN. Add it to perspective_test/.env.")

    provider = settings.get("HF_IMAGE_PROVIDER", "fal-ai") or "fal-ai"
    model = settings.get("HF_IMAGE_EDIT_MODEL", "Qwen/Qwen-Image-Edit")
    timeout = float(settings.get("HF_TIMEOUT_SECONDS", "180"))
    guidance_scale = float(settings.get("HF_GUIDANCE_SCALE", "4.0"))
    steps = int(settings.get("HF_INFERENCE_STEPS", "28"))
    min_size = int(settings.get("HF_MIN_IMAGE_SIZE", "768"))

    source_image = Path(package["source_image"])
    if not source_image.exists():
        raise FileNotFoundError(f"Source image not found: {source_image}")
    provider_image = prepare_provider_image(source_image, min_size=min_size)

    prompt, negative = build_prompt(package)
    output_name = settings.get("HF_OUTPUT_FILENAME", "generated_perspective_hf.png")
    output_path = TEST_ROOT / "output" / output_name
    client = InferenceClient(provider=provider, api_key=token, timeout=timeout)

    if provider == "fal-ai" and model == "Qwen/Qwen-Image-Edit":
        helper = get_provider_helper(provider, task="image-to-image", model=model)
        data_url = image_data_url(provider_image)
        request_parameters = helper.prepare_request(
            inputs=provider_image.read_bytes(),
            parameters={
                "prompt": prompt,
                "negative_prompt": negative,
                "guidance_scale": guidance_scale,
                "num_inference_steps": steps,
            },
            headers=client.headers,
            model=model,
            api_key=token,
            extra_payload={"images": [data_url]},
        )
        response_bytes = client._inner_post(request_parameters)
        result_bytes = helper.get_response(response_bytes, request_parameters)
        save_image_response(result_bytes, output_path)
    else:
        result_image = client.image_to_image(
            image=provider_image.read_bytes(),
            prompt=prompt,
            negative_prompt=negative,
            model=model,
            guidance_scale=guidance_scale,
            num_inference_steps=steps,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result_image.save(output_path)

    metadata = {
        "provider": provider,
        "model": model,
        "source_image": str(source_image),
        "provider_input_image": str(provider_image),
        "output_image": str(output_path),
        "guidance_scale": guidance_scale,
        "num_inference_steps": steps,
        "min_image_size": min_size,
    }
    (TEST_ROOT / "output" / "huggingface_result.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a perspective retrofit preview with Hugging Face Inference Providers.")
    parser.add_argument("--package", default=str(DEFAULT_PACKAGE_PATH), help="Path to perspective_regeneration_package.json")
    parser.add_argument("--dry-run", action="store_true", help="Validate package/settings without calling Hugging Face.")
    args = parser.parse_args()

    package_path = Path(args.package)
    if not package_path.is_absolute():
        package_path = PROJECT_ROOT / package_path
    package = read_json(package_path)
    settings = load_settings()

    preview = {
        "provider": settings.get("HF_IMAGE_PROVIDER", "fal-ai"),
        "model": settings.get("HF_IMAGE_EDIT_MODEL", "Qwen/Qwen-Image-Edit"),
        "source_image": package["source_image"],
        "prompt": package["prompt"],
        "negative_prompt": package.get("negative_prompt", ""),
        "hf_token_configured": bool(settings.get("HF_TOKEN") or settings.get("HUGGINGFACE_TOKEN")),
        "min_image_size": int(settings.get("HF_MIN_IMAGE_SIZE", "768")),
    }
    preview_path = TEST_ROOT / "output" / "huggingface_request_preview.json"
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.write_text(json.dumps(preview, indent=2), encoding="utf-8")

    if args.dry_run:
        print(f"Hugging Face request preview written: {preview_path}")
        return

    try:
        output_path = submit_to_huggingface(package, settings)
    except Exception as error:
        message = f"ERROR: {error}\n"
        write_error(TEST_ROOT / "output" / "ERROR.txt", message)
        print(message)
        raise SystemExit(1) from error

    print(f"Generated image: {output_path}")


if __name__ == "__main__":
    main()

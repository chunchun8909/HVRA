# Perspective Test

This folder tests perspective-image regeneration for a selected retrofit strategy using Hugging Face Inference Providers.

This is a cloud-only fallback path. It does not download local image models.

The test keeps the existing HVRA logic simple:

1. Read the original perspective image from `data/input/images/perspective_image/`.
2. Read the selected retrofit strategy from `sample_selected_strategy.json`.
3. Build a prompt package in `output/`.
4. Send the image and prompt to Hugging Face image-to-image.
5. Save the generated image to `output/generated_perspective_hf.png`.

## Files

- `.env` - local Hugging Face token and model settings. Do not commit real keys.
- `.env.example` - safe template.
- `build_perspective_package.py` - creates the prompt package.
- `run_huggingface_generation.py` - calls Hugging Face and saves the generated image.
- `perspective_generation_contract.json` - rules for preserving geometry and visual intent.
- `sample_selected_strategy.json` - current test strategy.
- `output/` - generated prompt package, request preview, and final image.

## Token

Create a token here:

```text
https://huggingface.co/settings/tokens
```

Use a normal read token/fine-grained token that can call Inference Providers. Put it in `perspective_test/.env`:

```env
HF_TOKEN=your_token_here
HF_IMAGE_PROVIDER=auto
HF_IMAGE_EDIT_MODEL=Qwen/Qwen-Image-Edit
```

## Run

From the project root:

```powershell
.\.venv\Scripts\python.exe perspective_test\build_perspective_package.py
.\.venv\Scripts\python.exe perspective_test\run_huggingface_generation.py --dry-run
.\.venv\Scripts\python.exe perspective_test\run_huggingface_generation.py
```

The final image should appear here:

```text
perspective_test/output/generated_perspective_hf.png
```

## Notes

Hugging Face provider availability can depend on your token, model, and provider limits. If a provider fails, try `HF_IMAGE_PROVIDER=auto` first, then another provider supported by your account.

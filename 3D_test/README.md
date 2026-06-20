# LGTNet Asset Registry Test

This folder is a non-interactive smoke test for connecting LGTNet room geometry to an external web-optimized 3D asset registry.

It does not create or serve an interface. It reads LGTNet output, prepares simple placement hints, optionally calls an asset registry with an API key from `.env`, and writes a JSON manifest.

## Inputs

Default LGTNet input:

```text
data/output/spatial/lgtnet/demo1_pred.json
```

Optional `.env` values:

```text
ASSET_REGISTRY_API_URL=https://example-registry.test/search
ASSET_REGISTRY_API_KEY=your_key_here
```

## Run Dry Test

```powershell
.\.venv\Scripts\python.exe 3D_test\run_lgtnet_asset_registry_test.py --dry-run
```

## Run With Registry API

```powershell
.\.venv\Scripts\python.exe 3D_test\run_lgtnet_asset_registry_test.py
```

The script sends a simple `POST` request per asset category:

```json
{
  "query": "web optimized low poly room chair table glb",
  "category": "furniture",
  "format": "glb",
  "max_results": 1
}
```

It sends the API key in both `Authorization: Bearer ...` and `X-API-Key` headers for compatibility with simple registry APIs.

## Output

Default output:

```text
3D_test/lgtnet_asset_manifest.json
```

This output is only a manifest. The next proper integration step would be:

```text
lgtnet_asset_manifest.json -> spatial_index_with_assets.json -> room viewer / report integration
```

## Simple 3D Room HTML

A standalone visual smoke test is available at:

```text
3D_test/room_component_test.html
```

It uses directly coded component placeholders for window, shading, door, furniture, and plant. It does not call the asset registry and does not affect the main Phase 2/3 room viewer.

Recommended way to open it:

```powershell
.\.venv\Scripts\python.exe -m http.server 8123 -d .
```

Then open:

```text
http://127.0.0.1:8123/3D_test/room_component_test.html
```

The page imports Three.js from:

```text
interface/public/vendor/three/
```

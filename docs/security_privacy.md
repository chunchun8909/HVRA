# Security and Privacy Notes

HVRA should be treated as a local research/prototype repository. Do not commit API keys, local credentials, resident-identifiable case notes, raw room images, generated intermediate data, vector databases, or large GIS datasets.

## Kept Out of Git

- `.env` and `perspective_test/.env`
- `data/input/images/`, `data/raw_pdfs/`, `data/intermediate/`, `data/checkpoints/`, `data/output/`, and `data/vector_db/`
- `perspective_test/output/`
- Large local risk-map datasets under `risk_map/dataset/`, including `.pbf`, large `.zip`, and local GIS extracts

## External Keys

Configured keys should stay in local environment files only: Infrared City, Gemini, Hugging Face, asset-registry keys, and any optional graph database credentials. The default project setting uses local/generated KG HTML and mock graph writing, so no graph database credential is required for the current test setup.

## Before Push

Run a secret scan such as:

```powershell
rg -n "(API_KEY|SECRET|TOKEN|PASSWORD|Bearer|sk-|ghp_|hf_)" -g "!interface/node_modules/**" -g "!.git/**" .
```

Then confirm large files are ignored:

```powershell
Get-ChildItem -Recurse -File | Where-Object { $_.Length -gt 95MB -and $_.FullName -notmatch '\.git|node_modules' }
```

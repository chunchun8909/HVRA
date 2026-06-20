# RAG Source Inventory

This file tracks the current raw PDF sources for the HVRA RAG engine.

Canonical metadata file:

```text
data/source_metadata.json
```

Raw PDF folder:

```text
data/raw_pdfs/
```

## Validation Summary

Checked on 2026-06-02. The current folder contains 23 PDFs. All 23 sources extract successfully. `ISO-7726-1998.pdf` requires the `pdfminer.six` fallback because `pypdf` cannot parse that local copy.

The latest ingestion produced:

```text
data/processed/corpus_pages.jsonl   1,882 records
data/processed/corpus_chunks.jsonl  1,895 records
data/vector_db/chroma/              rebuilt
```

| Status | Count | Notes |
| --- | ---: | --- |
| Raw PDFs | 23 | Files currently in `data/raw_pdfs/`. |
| Extractable sources | 23 | All sources produced text for RAG ingestion. |
| Fallback extraction | 1 | `ISO-7726-1998.pdf` uses `pdfminer.six` fallback. |
| Source errors | 0 | Latest RAG rebuild completed with no source errors. |
| Metadata entries | 23 | Every current raw PDF has an entry in `data/source_metadata.json`. |
| Metadata missing | 0 | Some entries still have blank direct URLs where the PDF did not expose them clearly. |

## Current Raw PDFs

| File | Pages | Size MB | Text | Current status |
| --- | ---: | ---: | --- | --- |
| `230113-solution_booklet-building_envelope_retrofit.pdf` | 47 | 25.37 | Yes | Ready |
| `55_2017_d_20200731.pdf` | 23 | 2.13 | Yes | Ready |
| `62_1_2013_p_20150707.pdf` | 10 | 0.63 | Yes | Ready |
| `ASHRAE-Standard-55.pdf` | 76 | 5.65 | Yes | Ready |
| `assessment-of-the-first-long-term-renovation-strategies.pdf` | 191 | 3.63 | Yes | Ready |
| `CIBSE TM59 2017 Overheating.pdf` | 17 | 1.79 | Yes | Ready |
| `D.B3--Handbook.pdf` | 54 | 2.56 | Yes | Ready |
| `DBHE.pdf` | 56 | 0.51 | Yes | Ready |
| `EBC_Annex_50_Retrofit_Strategies_Design_Guide.pdf` | 109 | 5.48 | Yes | Ready |
| `edg_89_cp_edited_2.pdf` | 17 | 9.92 | Yes | Ready |
| `en_ltserb.pdf` | 476 | 20.92 | Yes | Ready |
| `enerphit_renovating_with_passive_house_components (1).pdf` | 112 | 2.62 | Yes | Ready |
| `ES2010-90036_final.pdf` | 7 | 0.29 | Yes | Ready |
| `EuroPHit_brochure_final_PHI.pdf` | 77 | 1.77 | Yes | Ready |
| `ilide.info-uni-en-16798-1-note-1-pr_df2e0b2e6672cb314bba3e706150d616.pdf` | 11 | 2.59 | Yes | Ready |
| `ISO-7243-2017.pdf` | 11 | 0.40 | Yes | Ready |
| `ISO-7726-1998.pdf` | 15 | 0.66 | Yes | Ready via pdfminer fallback |
| `lbnl-6131e.pdf` | 19 | 10.16 | Yes | Ready |
| `PassivhausDesignersManualHopfe.pdf` | 346 | 21.57 | Yes | Ready |
| `Renovation-Strategies-EU-BPIE-2014.pdf` | 68 | 2.46 | Yes | Ready |
| `Retrofit-Playbook.pdf` | 81 | 7.34 | Yes | Ready |
| `scis_solution_booklet_building_envelope_retrofit.pdf` | 47 | 5.30 | Yes | Ready |
| `ta cctp 9imc fullpaper holisticstrategies final.pdf` | 12 | 0.56 | Yes | Ready |

## Metadata Coverage

All current raw PDFs have metadata entries in `data/source_metadata.json`.

```text
230113-solution_booklet-building_envelope_retrofit.pdf
55_2017_d_20200731.pdf
62_1_2013_p_20150707.pdf
ASHRAE-Standard-55.pdf
assessment-of-the-first-long-term-renovation-strategies.pdf
CIBSE TM59 2017 Overheating.pdf
D.B3--Handbook.pdf
DBHE.pdf
EBC_Annex_50_Retrofit_Strategies_Design_Guide.pdf
edg_89_cp_edited_2.pdf
en_ltserb.pdf
enerphit_renovating_with_passive_house_components (1).pdf
ES2010-90036_final.pdf
EuroPHit_brochure_final_PHI.pdf
ilide.info-uni-en-16798-1-note-1-pr_df2e0b2e6672cb314bba3e706150d616.pdf
ISO-7243-2017.pdf
ISO-7726-1998.pdf
lbnl-6131e.pdf
PassivhausDesignersManualHopfe.pdf
Renovation-Strategies-EU-BPIE-2014.pdf
Retrofit-Playbook.pdf
scis_solution_booklet_building_envelope_retrofit.pdf
ta cctp 9imc fullpaper holisticstrategies final.pdf
```

## Required Metadata Fields

Each source should have this shape in `data/source_metadata.json`:

```json
{
  "filename.pdf": {
    "source_id": "SHORT_STABLE_ID",
    "source_title": "Full source title",
    "authors": "Author, institution, or standards body",
    "year": 2026,
    "document_type": "design_code | standard | design_guide | policy | research_paper | retrofit_manual",
    "citation": "Formal citation text.",
    "doi_or_url": "https://..."
  }
}
```

## Priority Gaps

1. Add exact source URLs where currently blank.
2. Keep sources grouped conceptually during retrieval: standards, thermal comfort, ventilation, overheating, retrofit manuals, policy, and research evidence.
3. Rebuild the RAG index after adding, replacing, or removing any raw PDF.

## Validation Commands

Validate source extraction using the same loader as the RAG indexer:

```powershell
@'
from rag_engine.source_catalog import discover_sources
from rag_engine.document_loader import extract_pages

for source in discover_sources():
    pages = extract_pages(source)
    sample = "".join(page["text"] for page in pages[:2])
    print(source["source"], len(pages), bool(sample.strip()))
'@ | .\.venv\Scripts\python.exe -
```

Rebuild RAG index:

```powershell
.\.venv\Scripts\python.exe -m rag_engine.build_index
```

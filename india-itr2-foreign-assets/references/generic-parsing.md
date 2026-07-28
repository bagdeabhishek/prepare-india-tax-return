# Generic source parsing

## Contents

1. Three-layer boundary
2. Supported formats
3. Setup and commands
4. Normalized envelope
5. Passwords and archives
6. Fallback rules
7. Extension policy

## 1. Three-layer boundary

Use `parse_source.py` for deterministic structural extraction. It opens files,
preserves locations, and emits a normalized JSON envelope. It must not decide
whether a value is salary, a dividend, a sale, foreign tax, cost, or an ITR
schedule field.

Then use `extract_standard_tax.py` for conservative, versioned semantic
extraction from recurring official documents. It may classify a value only
when a stable form label/JSON path and required control fields are present.

Use an agent only for the residual files in `semantic_queue.json`. This
three-layer separation prevents recurring one-off scripts and makes both
structural and standard-form extraction cacheable by file hash and version.

Keep `prepare_fa_csv.py` schedule-specific: it validates and serializes a
portal-import template, so it is an output adapter rather than a source parser.

## 2. Supported formats

| Input | Primary backend | Built-in fallback |
|---|---|---|
| PDF, including encrypted PDF | PyMuPDF | `pdftotext` for unencrypted files |
| JSON/AIS/prefill | Python JSON parser | — |
| CSV/TSV and delimiter variants | Python CSV parser | Encoding and delimiter detection |
| XLSX/XLSM | openpyxl | Direct OOXML parsing |
| Legacy XLS | xlrd | Clear failed-envelope diagnostic |
| DOCX | Direct OOXML parsing | — |
| XML/HTML/text | Python standard library | Encoding detection |
| ZIP | Python zipfile with safety limits | Nested supported-member parsing |
| Images/scanned pages | Tesseract when installed | Metadata and partial-envelope warning |

The parser preserves:

- PDF page text and positioned blocks.
- Spreadsheet sheet names, rows, cells, formulas/types, and coordinates.
- CSV row and column numbers.
- JSON Pointer paths for every scalar leaf.
- XML paths.
- ZIP member names, hashes, sizes, and nested envelopes.
- Parser backend, parser version, source hash, warnings, and extraction status.

## 3. Setup and commands

JSON, CSV, text, XML, HTML, DOCX, ZIP, and basic XLSX parsing work with the
Python standard library. Install the optional backends once in a private virtual
environment for full PDF, XLS/XLSX, and image coverage:

```bash
python3 -m venv /private/itr-parser-venv
/private/itr-parser-venv/bin/pip install \
  -r scripts/parser-requirements.txt
```

Parse one source:

```bash
/private/itr-parser-venv/bin/python scripts/parse_source.py --capabilities

/private/itr-parser-venv/bin/python scripts/parse_source.py \
  --input /private/sources/document.pdf \
  --output /private/workpaper/normalized/document.json
```

Run the complete queued-source pipeline:

```bash
/private/itr-parser-venv/bin/python scripts/preprocess_sources.py \
  --workspace /private/workpaper \
  --jobs 8
```

`--jobs` controls deterministic local work, not semantic agents. After it
finishes, dispatch one semantic worker per item in `semantic_queue.json`, not
per item in the original inventory.

## 4. Normalized envelope

Every output conforms to `assets/document-envelope.schema.json` and contains:

- `source`: path, exact SHA-256, byte size, and extension.
- `parser`: name, version, and timestamp.
- `status`: `COMPLETE`, `PARTIAL`, or `FAILED`.
- `document.format` and `document.backend`.
- `document.units`: pages, sheets, tables, text, or path/value records.
- `document.members`: nested archive members.
- `warnings`: missing backend, truncation, OCR, encryption, or malformed data.

Workers should cite envelope locators in claim evidence. When status is
`COMPLETE`, do not reopen the raw source unless the task requires visual layout.

Rigid standard-form records live under `deterministic-records/`. Completed
records are staged into `incoming/` for the central merge. Partial/unrecognized
records are attached to the corresponding residual queue item as a starting
point for its one-file agent.

## 5. Passwords and archives

Never pass passwords as command-line arguments or store them in envelopes.
Place the password temporarily in an environment variable and provide only the
variable name:

```bash
/private/itr-parser-venv/bin/python scripts/parse_source.py \
  --input /private/sources/encrypted.pdf \
  --output /private/workpaper/normalized/encrypted.json \
  --password-env ITR_DOCUMENT_PASSWORD
```

Clear the variable after parsing. Different passwords require separate parser
runs or grouped queues. The ZIP parser rejects unsafe paths, suspicious
compression ratios, excessive member counts, oversized members, and excessive
recursion.

## 6. Fallback rules

1. Use the normalized envelope when status is `COMPLETE`.
2. For `PARTIAL`, inspect warnings and determine whether missing content affects
   a required claim.
3. For `FAILED`, install the declared optional backend or verify the password.
4. Use OCR only for image-only pages; retain the low-confidence warning.
5. Reopen the raw source visually when tables/layout did not survive text
   extraction.
6. Never silently treat truncated or failed extraction as complete.
7. Do not mark a rigid extraction complete when its required control labels are
   missing; route it to the residual queue.

## 7. Extension policy

Before writing custom parsing code:

1. Confirm the source is not already supported.
2. Determine whether failure is a missing optional backend, password, corruption,
   or actual unsupported format.
3. For a new binary/structural format, add it to `parse_source.py` with a stable
   envelope representation.
4. For a recurring official form layout, add a conservative recognizer and
   labelled-field rules to `extract_standard_tax.py`.
5. Add synthetic success, incomplete-control, and failure-path tests.
6. Increment `PARSER_VERSION` or the standard extractor version as applicable.
7. Rescan with the combined version generated by `run_intake_pipeline.py`.

Do not add scripts named for a taxpayer, broker account, employer, or one
statement layout. Broker-specific semantic rules belong in references or
classification logic, not the structural parser.

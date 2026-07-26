# Generic source parsing

## Contents

1. Parser boundary
2. Supported formats
3. Setup and commands
4. Normalized envelope
5. Passwords and archives
6. Fallback rules
7. Extension policy

## 1. Parser boundary

Use `parse_source.py` for deterministic structural extraction. It opens files,
preserves locations, and emits a normalized JSON envelope. It must not decide
whether a value is salary, a dividend, a sale, foreign tax, cost, or an ITR
schedule field.

Use an agent only for semantic classification and reconciliation after generic
normalization. This separation prevents recurring one-off scripts and makes
source parsing cacheable by file hash and parser version.

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

Parse every queued source:

```bash
/private/itr-parser-venv/bin/python scripts/preprocess_sources.py \
  --workspace /private/workpaper \
  --jobs 4
```

`--jobs` controls deterministic file parsing, not semantic agents. After it
finishes, dispatch one semantic worker per queue item up to available agent
capacity.

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

## 7. Extension policy

Before writing custom parsing code:

1. Confirm the source is not already supported.
2. Determine whether failure is a missing optional backend, password, corruption,
   or actual unsupported format.
3. Add the new format to `parse_source.py` with a stable envelope representation.
4. Add a synthetic test fixture and a failure-path test.
5. Increment `PARSER_VERSION`.
6. Rescan with a combined extractor version such as
   `parser-1.1.0_claims-1` so dependent facts invalidate correctly.

Do not add scripts named for a taxpayer, broker account, employer, or one
statement layout. Broker-specific semantic rules belong in references or
classification logic, not the structural parser.

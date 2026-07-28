# Persistent source ledger

## Contents

1. Purpose
2. Workspace layout
3. Preprocessing sequence
4. Parallel worker contract
5. Claim and fact provenance
6. Change detection and invalidation
7. Follow-up query rules
8. Privacy and failure controls

## 1. Purpose

Parse each source version once and retain an auditable, queryable workpaper.
Do not repeatedly crawl unchanged PDFs, spreadsheets, JSON, or archives on
follow-up questions.

Use JSON rather than CSV for the central store because tax observations contain
nested values, multiple evidence locators, dependencies, and typed records. CSV
remains appropriate for flat portal-import outputs.

The store has two layers:

- `claims`: atomic observations extracted from one source version.
- `reconciled_facts`: conclusions derived from one or more claims.

A claim is not automatically a tax conclusion. For example, a dividend shown in
a broker statement and the same dividend shown on an annual tax form are two
claims that may support one reconciled fact.

## 2. Workspace layout

Create a private workspace with:

```text
itr-workpaper/
├── .gitignore
├── manifest.json
├── work_queue.json
├── semantic_queue.json
├── normalized/
│   └── <source-id>/<sha256>.json
├── deterministic-records/
│   └── <source-id>/<sha256>.json
├── incoming/
│   └── <source-id>.json
├── source-records/
│   └── <source-id>/<sha256>.json
├── reconciled_facts.json
└── central_store.json
```

`source_store.py init` writes a deny-all `.gitignore`. Keep this workspace outside
the installed skill and outside any public repository. The repository contains
only schemas, scripts, and synthetic documentation.

## 3. Preprocessing sequence

Run preprocessing before substantive tax analysis:

1. Initialize the workspace.
2. Scan all supplied files and compute SHA-256 hashes.
3. Run `run_intake_pipeline.py` to normalize changed sources and apply the
   versioned rigid standard-tax extractor.
4. Read `semantic_queue.json`; do not dispatch agents from `work_queue.json`.
5. Dispatch one semantic extraction worker for each residual queued file,
   subject to the available agent limit. Process remaining files in batches.
6. Have each worker read `normalized_output` and write its result to the exact
   `agent_output` path in its queue item.
7. Run one coordinator merge after all available workers finish.
8. Review pending sources, extraction warnings, conflicts, and control totals.
9. Reconcile claims into facts and store each fact's `depends_on` claim IDs.
10. Use `central_store.json` for schedule mapping and follow-up questions.

Commands:

```bash
python3 scripts/source_store.py init --workspace /private/itr-workpaper
python3 scripts/run_intake_pipeline.py \
  --workspace /private/itr-workpaper \
  --source-dir /private/source-documents \
  --replace-inventory \
  --jobs 8
python3 scripts/source_store.py merge --workspace /private/itr-workpaper
python3 scripts/source_store.py set-facts \
  --workspace /private/itr-workpaper \
  --input /private/reconciled-output.json
python3 scripts/source_store.py status --workspace /private/itr-workpaper
```

Scanning is incremental. An unchanged path with the same hash and requested
extractor version is not queued. Use `--replace-inventory` only when the scan
represents the complete current source set; files omitted from that scan become
inactive. Use `--force` for an intentional full re-extraction.

## 4. Parallel worker contract

Treat `one semantic_queue item = one agent task = one source file` as mandatory.
Files completed by the rigid extractor, unchanged hashes, and safely reused
exact duplicates do not receive an agent.

Scheduling rules:

1. Create all one-file tasks before semantic extraction starts.
2. Launch as many tasks concurrently as the platform permits.
3. Never group several files into one worker prompt, even when they come from
   the same broker, statement period, or archive.
4. Refill a free slot immediately with the next queued one-file task.
5. When new-agent creation is capped, reuse an idle agent with a follow-up turn;
   the follow-up still contains exactly one file.
6. Let the coordinator process at most one file itself and only when doing so
   does not delay dispatch, result collection, or the single-writer merge.
7. Perform cross-file reconciliation only after all per-file records are merged.

Give each worker only:

- One source file.
- The matching queue item.
- The normalized envelope at `normalized_output`.
- The deterministic draft at `deterministic_record`, when present.
- `assets/source-record.schema.json`.
- The relevant domain reference, if needed.
- The exact `agent_output` path.

Require the worker to:

1. Verify the envelope path and SHA-256 match the queue item.
2. Classify the document by contents rather than filename.
3. Extract atomic claims without cross-file reconciliation.
4. Retain original currency, dates, units, and signs.
5. Give every claim a unique `local_id`.
6. Include page, row, cell, statement section, or JSON path in `evidence`.
7. Record confidence and warnings; never invent missing values.
8. Exclude passwords, tokens, and unnecessary full identifiers.
9. Record `normalized_document` path, source hash, parser version, and status in
   the source record.
10. Set `extractor.version` to the queue item's
    `requested_extractor_version` so unchanged files remain cached.
11. Write only its own incoming record.

Do not re-extract claims already produced by the rigid extractor. If
normalization or deterministic extraction is partial, inspect its warnings and
follow [generic-parsing.md](generic-parsing.md). Add reusable support to the
generic parser or standard extractor instead of creating a taxpayer-specific
extractor.

Do not let parsing workers edit `manifest.json`, `central_store.json`, or another
worker's output. The coordinator is the only merge writer. This avoids lost
updates and corrupted JSON.

If agent slots are fewer than files, use rolling one-file batches. Capacity
limits reduce simultaneous execution; they do not permit multi-file tasks.

## 5. Claim and fact provenance

The merge assigns each claim a version-bound ID derived from:

```text
source_id + source_sha256 + extractor.version + local_id
```

Including `extractor.version` means a material parser upgrade invalidates facts
even when the source bytes are unchanged.

Each central claim includes:

- Claim ID and claim kind.
- Extracted values and covered period.
- Source ID, exact SHA-256, and source path.
- Detected document type.
- Local claim ID.
- Page/row/cell/JSON-path evidence.
- Confidence, notes, and extraction warnings.

Reconciled facts use `assets/reconciled-facts.schema.json`. Every fact must list
the claim IDs used in `depends_on`, plus the derivation or reconciliation rule.
Facts without source dependencies are allowed only for explicit user-supplied
assumptions and must be labelled `ASSUMPTION`.

Do not silently replace two conflicting claims with one value. Retain both
claims, create a conflict or unresolved item, and document which evidence
controls the reconciled fact.

## 6. Change detection and invalidation

SHA-256 is computed from the original file bytes. Password-protected files are
hashed while still encrypted; passwords are used only for temporary reading.

When a path's hash changes:

1. Mark the source as pending.
2. Queue only that source for re-extraction.
3. Exclude the prior version's claims from the active central store.
4. Mark facts depending on removed claim IDs as `STALE`.
5. Preserve claims and facts from unchanged sources.
6. Reconcile and replace only the stale facts.

Renaming a file creates a new source ID because the logical path changed.
Identical content hashes are flagged as possible duplicates. Resolve duplicates
by document identity and period before excluding either source.

Changing extraction logic without changing a source file also requires
reprocessing. Increment `extractor.version` and rescan with the matching
`--extractor-version`, or use `--force`.

## 7. Follow-up query rules

For every follow-up:

1. Check `status`.
2. Query `central_store.json` by claim kind, fact kind, source ID, account,
   issuer, period, or schedule mapping.
3. Cite the provenance stored with the value.
4. Reopen raw documents only when:
   - the source hash changed;
   - the requested field is absent;
   - a claim is low-confidence;
   - claims conflict;
   - visual/layout evidence is essential; or
   - the user specifically asks to recheck the source.
5. If a raw source is reopened, update its extraction record with the newly
   extracted claim so later follow-ups do not repeat the work.

Never answer from a stale reconciled fact without labelling it stale.

## 8. Privacy and failure controls

- Keep the workpaper private and git-ignored.
- Never place real taxpayer data in the public skill repository.
- Do not record source passwords.
- Mask account and taxpayer identifiers unless the complete value is required
  for filing; store complete identifiers only in the private workspace.
- Use atomic writes and one merge writer.
- Stop the merge from treating a pending source as complete.
- Reject source records whose declared hash differs from the current manifest.
- Back up the private workspace before material manual reconciliation edits.
- Treat the central store as a workpaper, not an official utility upload JSON.
- Never upload `central_store.json` to the Income Tax portal.

# Staged intake and fast processing

## Contents

1. Interaction contract
2. Phase 1 — primary checklist
3. Phase 2 — deterministic processing
4. Phase 3 — evidence-driven follow-ups
5. Phase 4 — residual parallel agents
6. Phase 5 — reconciliation
7. Performance rules

## 1. Interaction contract

Start with documents, not schedule questions or a request for every conceivable
statement.

1. State the primary checklist.
2. Ask the user to upload or list what is available.
3. Wait until the user says the initial set is ready.
4. Inventory, hash, normalize, and run rigid extractors.
5. Show the observed document types and only the next evidence-driven requests.
6. Record factual answers in the intake state and reassess.

Do not ask for foreign broker, property, capital-gain, or Schedule AL evidence
before the initial sources or taxpayer facts indicate it is relevant.

## 2. Phase 1 — primary checklist

Run:

```bash
python3 scripts/intake_manager.py start \
  --workspace /private/itr-workpaper \
  --assessment-year 2026-27
```

Present this initial list:

- Form 16 Part A and Part B for every employer; include a separate Form 12BA
  annexure if supplied.
- AIS as decrypted JSON or PDF.
- TIS PDF.
- Fresh official portal prefill JSON (recommended).
- Form 26AS/tax-credit statement (recommended).

Ask whether there are multiple employers and whether any files are encrypted.
Receive passwords separately and only through the password mechanism; never put
them in filenames, command arguments, logs, or the workpaper.

Do not call a Form 1042-S “1024S.” When the user uses that term, clarify once
that the common U.S. withholding form is Form 1042-S.

## 3. Phase 2 — deterministic processing

After the initial files are ready, run one command:

```bash
python3 scripts/run_intake_pipeline.py \
  --workspace /private/itr-workpaper \
  --source-dir /private/sources \
  --jobs 8
```

The command:

1. Hashes and queues only new/changed files.
2. Structurally normalizes files concurrently.
3. Runs the rigid standard-tax extractor.
4. Stages completed deterministic records.
5. Merges ready claims into the central store.
6. Writes only unresolved files to `semantic_queue.json`.
7. Reassesses the document requests.

Use `--password-env VARIABLE_NAME` for encrypted sources. Use as many parser
jobs as the machine can support; these are local deterministic tasks and are
not constrained by agent slots.

Rigid extraction covers stable fields from:

- Form 16 Part A/Part B and Form 12BA.
- AIS JSON rows and recognizable AIS PDF categories.
- TIS categories.
- Official portal prefill JSON.
- Official ITR-2 export JSON.
- Form 26AS totals.
- Form 1042-S gross income, rate, and withholding boxes.

The extractor skips an agent only when required labels/control fields are
present and normalization is complete. A changed layout, encrypted/unreadable
source, missing controls, or unsupported schema is never treated as complete.
An encrypted AIS export becomes a user-action request for decrypted AIS/PDF;
do not waste an agent on ciphertext. Other incomplete/unsupported layouts go to
the residual queue.

## 4. Phase 3 — evidence-driven follow-ups

Run after each new batch or factual answer:

```bash
python3 scripts/intake_manager.py assess \
  --workspace /private/itr-workpaper
```

Typical triggers:

| Extracted signal or confirmed fact | Next documents |
| --- | --- |
| Salary perquisites/equity compensation | Form 12BA, vest/ESPP reports, payroll equity detail |
| Foreign asset, remittance, income, or withholding | Apr–Mar and Jan–Dec broker statements, Form 1042-S/1099-DIV, lot history, trades, account-opening evidence |
| Actual capital-asset sale | Capital-gain report, contract notes, purchase-cost history |
| Bank interest | Interest certificate and 31 March savings/FD statements |
| House/property loan | Loan certificate, statement, agreement/title, invoices, ownership evidence |
| Under-construction property | Completion/possession or current construction-status evidence |
| Schedule AL threshold crossed | 31 March bank/FD balances, share cost, asset cost, related liabilities |

When evidence does not answer a gating fact, ask one concise factual question.
Record the answer:

```bash
python3 scripts/intake_manager.py record \
  --workspace /private/itr-workpaper \
  --fact foreign_holdings=yes \
  --basis "taxpayer confirmation"
```

Supported fact keys are open-ended. Common keys are
`foreign_holdings`, `equity_compensation`, `capital_asset_sales`, `home_loan`,
and `property_under_construction`.

## 5. Phase 4 — residual parallel agents

Read `semantic_queue.json`, not the original inventory.

- Create exactly one agent task for each queued file.
- Launch all available agent slots immediately.
- Give the worker the normalized envelope and deterministic draft record.
- Ask the worker to fill that file's `agent_output` only.
- Do not assign standard files already marked `agent_required: false`.
- Refill a slot with the next single-file task as soon as it finishes.
- Never group files into one task, even when they share an issuer or format.

After workers finish:

```bash
python3 scripts/source_store.py merge \
  --workspace /private/itr-workpaper
```

Agents must not reread the directory, rebuild inventories, edit the central
store, or re-extract deterministic claims.

## 6. Phase 5 — reconciliation

The coordinator reconciles claims across files after deterministic and residual
records are merged. Cross-file reconciliation is not a per-file extraction
task. Build facts with claim dependencies so a changed hash invalidates only
affected facts.

Continue to request documents only for unresolved material facts. Once the
source package is sufficient, freeze intake and move to schedule mapping.

## 7. Performance rules

- Script first; agent last.
- Parse each unique hash once.
- Reuse normalized and deterministic records when parser/extractor versions and
  hashes match.
- Use high local concurrency for hashing/parsing/extraction.
- Never send a deterministically completed standard form to an agent.
- Give residual agents envelopes, not raw files, unless layout/OCR failed.
- Never reread unchanged sources for follow-up questions.
- Extend the generic parser or versioned standard extractor instead of writing
  taxpayer-, employer-, or broker-specific scripts.
- Keep rigid extractors conservative: falling back is slower but safer than a
  confident wrong claim.

The Income Tax Department confirms that AIS is available as PDF, JSON, and CSV,
and that TIS contains category-level processed/accepted values. Use the current
[official AIS FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/ais%20-%20annual%20information%20statement-faqs)
when the download formats or terminology change.

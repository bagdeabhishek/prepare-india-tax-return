---
name: india-itr2-foreign-assets
description: End-to-end reconciliation and filing assistance for Indian ITR-2 returns involving Form 16, AIS/TIS, foreign brokerage or custodial accounts, RSUs, ESPP shares, foreign dividends, interest, withholding tax, Schedule OS, CG, FSI, TR, FA, AL, and Form 67. Use when Codex must analyze salary or broker PDFs/CSVs/JSON, reconcile foreign holdings and lots, convert USD income or assets to INR, prepare Schedule FA A1/A2/A3 records, fix Income Tax portal CSV-import errors, or guide a resident individual through foreign-income and foreign-asset filing.
---

# India ITR-2 Foreign Assets

Reconcile source documents into an auditable ITR-2 filing package. Treat the work as high-stakes financial assistance: verify current official rules, expose assumptions, preserve source evidence, and never fabricate unavailable account or lot data.

## Core workflow

1. Start staged intake:
   - Before inspecting files, present the primary checklist: Form 16 Part A/B for every employer, AIS, TIS, and recommended portal prefill JSON/Form 26AS.
   - Ask the user to upload or list the primary set. Do not ask for every conditional document upfront.
   - Run `scripts/intake_manager.py start` and wait until the user says the initial set is ready.
   - Read [references/staged-intake.md](references/staged-intake.md) completely.
2. Establish scope:
   - Confirm assessment year, financial year, calendar year used by Schedule FA, residential status, regime, filing status, and ITR form.
   - Confirm whether the taxpayer is resident and ordinarily resident before treating Schedule FA as applicable.
   - Do not reuse dates, exchange rates, thresholds, or form rules from another assessment year without current verification.
   - Create `filing-decisions.json` in the private workpaper and record each portal decision once with its basis and source claim IDs. Read [references/filing-decisions.md](references/filing-decisions.md).
3. Secure, inventory, and hash the supplied documents:
   - Accept passwords only for opening the supplied files; do not repeat passwords or embed them in outputs.
   - Inventory the primary set first. Add broker, Form 1042-S, vest, trade, bank, property, and loan documents only when extracted signals or confirmed facts make them relevant.
   - Detect duplicates and misleading filenames by content, period, account, opening/closing balance, and transaction identity.
   - Before tax analysis, run the preprocessing workflow in [references/source-ledger.md](references/source-ledger.md).
   - Hash every source and reuse its extraction when the SHA-256 is unchanged. Do not reopen an unchanged source merely to answer a follow-up.
4. Run the deterministic pipeline:
   - Use `scripts/run_intake_pipeline.py` to hash, normalize, rigidly extract standard documents, merge automated claims, and generate `semantic_queue.json`.
   - Use high local concurrency for deterministic parsing. Do not spend agent slots on standard documents whose required controls passed.
   - Use `scripts/extract_standard_tax.py` for Form 16/12BA, AIS, TIS, prefill/ITR JSON, Form 26AS, and Form 1042-S. If a layout is incomplete or changed, route it to an agent instead of guessing.
   - Reuse cached outputs when the file hash and parser/extractor versions are unchanged.
5. Ask evidence-driven follow-ups:
   - Run `scripts/intake_manager.py assess`.
   - Request only documents triggered by extracted facts: foreign statements/tax forms, equity-plan evidence, capital-gain reports, bank certificates, loan/property evidence, or Schedule AL balances.
   - Record unresolved gating answers with `scripts/intake_manager.py record`, reassess, and stop intake once all material facts are supported.
6. Extract residual sources in parallel:
   - Dispatch agents only from `semantic_queue.json`, never from the original inventory.
   - Treat one agent task per residual file as a scheduling invariant. Never assign two source files to the same task or ask one worker to inspect a directory.
   - Launch the maximum available agent concurrency immediately. If files exceed available slots, keep one-file tasks queued and refill each slot as soon as its prior task finishes.
   - Reuse an idle agent with a follow-up task when agent-creation limits require it, but give that turn exactly one file. The coordinator may process at most one file itself while coordinating.
   - Give each worker the normalized document envelope. Reopen the raw source only when normalization is partial/failed or visual evidence is required.
   - Never let workers concurrently edit the central store. Each worker writes only its assigned source record; the coordinator performs the single merge.
7. Build independent ledgers from the central store:
   - Salary and perquisite ledger.
   - Domestic interest/dividend/capital-gain ledger.
   - Foreign cash, dividend, interest, tax-withholding, acquisition-lot, sale, and account-balance ledgers.
   - Keep original currency, transaction date, quantity, price/FMV, tax, and source document/page.
8. Reconcile before classifying:
   - Tie quarterly openings to prior closings.
   - Tie lot quantities to closing holdings.
   - Tie dividends and withholding to annual tax forms, allowing for tax-form rounding.
   - Distinguish shares withheld for payroll tax from an actual investor-directed sale.
   - Flag unresolved discrepancies and proxy dates; never silently force totals.
   - Record each reconciled fact with the claim IDs it depends on. A changed source hash must invalidate only dependent facts.
9. Map reconciled facts to ITR schedules.
10. Apply the correct conversion rule for each field.
11. Generate import files or a manual-entry checklist.
12. Audit the official utility export, validate control totals, and explain every figure changed.

Read [references/return-workflow.md](references/return-workflow.md) for the complete document-to-schedule sequence.

Before answering filing-status, regime, salary-eligibility, house-property, or
schedule-selection questions, read
[references/filing-decisions.md](references/filing-decisions.md). Reuse the
recorded decision unless new evidence invalidates it.

## Persistent source ledger

Use `scripts/source_store.py` for document-led work:

```bash
python3 scripts/intake_manager.py start \
  --workspace /private/path/itr-workpaper \
  --assessment-year 2026-27
python3 scripts/run_intake_pipeline.py \
  --workspace /private/path/itr-workpaper \
  --source-dir /private/path/sources \
  --jobs 8
# Dispatch one semantic worker for every item remaining in semantic_queue.json.
python3 scripts/source_store.py merge --workspace /private/path/itr-workpaper
python3 scripts/intake_manager.py assess --workspace /private/path/itr-workpaper
python3 scripts/source_store.py status --workspace /private/path/itr-workpaper
```

Keep the workspace outside this skill or any public repository. The initialized workspace is deny-all git-ignored. Read [references/source-ledger.md](references/source-ledger.md) completely before preprocessing or delegating source files.

Read [references/generic-parsing.md](references/generic-parsing.md) before adding a parser dependency or writing parsing code. Extend the generic parser for reusable format support; do not accumulate taxpayer- or broker-specific scripts.

## Screen-by-screen portal mode

When the user is actively filing:

1. Identify the exact screen and visible fields.
2. Give only the entries and checks needed on that screen.
3. State the expected subtotal or validation result.
4. Wait for the next screen, screenshot, or exported JSON.
5. Do not jump ahead or repeat completed schedules.

Read [references/portal-step-by-step.md](references/portal-step-by-step.md) before guiding a live portal or offline-utility filing.

## Conditional references

- Before intake or processing a new return, read [references/staged-intake.md](references/staged-intake.md).
- For RSUs, ESPP, vesting, withholding shares, and lot construction, read [references/equity-compensation.md](references/equity-compensation.md).
- For Schedule OS, FSI, TR, DTAA relief, Rule 115, Rule 128, and Form 67, read [references/foreign-income-ftc.md](references/foreign-income-ftc.md).
- For Schedule FA A1/A2/A3, read [references/schedule-fa.md](references/schedule-fa.md).
- For Schedule AL, construction cost, bank deposits, employee shares, or joint liabilities, read [references/schedule-al.md](references/schedule-al.md).
- Before creating or debugging an FA CSV, read [references/portal-csv-import.md](references/portal-csv-import.md).
- For live utility/portal entry, tax payment, Form 67, validation, or submission, read [references/portal-step-by-step.md](references/portal-step-by-step.md).
- Before final handoff, read [references/reconciliation-controls.md](references/reconciliation-controls.md).

## Source hierarchy

Prefer evidence in this order:

1. Current official Income Tax Department form, instructions, validation rules, and user guides.
2. Broker-issued transaction statements, tax forms, vest confirmations, and account statements.
3. Employer Form 16 and payroll/perquisite schedules.
4. AIS/TIS and prefill data as reconciliation inputs, not unquestioned truth.
5. Current SBI TT buying-rate evidence and applicable Income-tax Rules.
6. Community workarounds only for undocumented portal behavior. Label them as operational workarounds, preserve a test file, and never elevate them over substantive tax law.

When online information may have changed, browse current official sources. Cite the official page used and record the applicable assessment year.

## Conversion discipline

Never use one exchange-rate convention everywhere.

- Taxable foreign income: apply Rule 115 and the specified date for the relevant income type.
- Foreign tax credit: apply Rule 128 conversion rules to the foreign tax paid or deducted.
- Schedule FA: use SBI telegraphic transfer buying rates and the relevant field date for acquisition, peak, closing, foreign-sourced income, and proceeds as directed by current Schedule FA instructions.
- Schedule FA uses the calendar year ending 31 December; income schedules use the Indian financial year. Differences between FA income and Schedule OS/FSI can therefore be valid.

Record the rate, rate type, source, date, original currency amount, unrounded INR result, and final rounded INR value in the workpaper.

## Output package

Create a filing package containing:

- Source inventory and unresolved-data list.
- Reconciled salary, income, tax, account, and lot ledgers.
- Schedule-by-schedule manual-entry checklist.
- FA A1/A2/A3 data tables and portal-ready A2/A3 CSV artifacts by default whenever Schedule FA is in scope.
- FSI/TR/Form 67 reconciliation.
- Assumptions and proxies register.
- Persisted filing-decisions record.
- Control-total report.
- Read-only final-JSON audit and, where relevant, checkpoint comparison.

Use filenames that distinguish `WORKING`, `PROVISIONAL`, `RECONCILED`, and `PORTAL_READY`. Never tell the user to import a provisional file.

## Portal CSV preparation

When Schedule FA is in scope, tell the user that A2/A3 CSV artifacts will be generated by default. Generate them without waiting for a separate request when the reconciled data and a current template are available. For each applicable table, produce a one-row `IMPORT_TEST` artifact and the complete `PORTAL_READY` artifact. If required values remain unresolved, generate clearly labelled `WORKING` artifacts and list the blockers; never label them `PORTAL_READY`.

Use `scripts/prepare_fa_csv.py` to normalize A2 or A3 CSV data:

```bash
python3 scripts/prepare_fa_csv.py \
  --table A3 \
  --input source.csv \
  --test-output Schedule_FA_A3_IMPORT_TEST_ONE_ROW.csv \
  --output Schedule_FA_A3_PORTAL_READY.csv
```

The script enforces the operational importer format documented in [references/portal-csv-import.md](references/portal-csv-import.md). Test a one-row file first when the portal version is new or the template changed.

## Final utility-export audit

Never treat visual portal totals as the only final control. Run the read-only
auditor against the latest official ITR-2 utility export:

```bash
python3 scripts/audit_itr_json.py FINAL_OFFICIAL_EXPORT.json
```

After adding a self-assessment challan, compare the before/after official
exports and require a payment-only change set:

```bash
python3 scripts/audit_itr_json.py AFTER_PAYMENT.json \
  --compare BEFORE_PAYMENT.json \
  --expect-payment-only
```

The auditor checks salary arithmetic, OS components, FSI/TR/TTI relief,
Part B-TI, Schedule IT/taxes paid, payable/refund, the foreign-assets flag, and
Schedule AL presence above the configured AY threshold. It does not edit the
JSON or replace official utility validation.

## Handoff requirements

Lead with the exact schedules and fields that change. For each change, show:

- Previous value, if known.
- Corrected value.
- Component breakup.
- Source documents.
- Conversion rule.
- Whether the number is exact, rounded, or provisional.

Explicitly identify schedules that remain unchanged. Warn about Form 67 when foreign tax credit is claimed. Recommend professional review when facts are ambiguous, documents conflict, residency is uncertain, foreign sales exist, or a substantive legal interpretation is required.

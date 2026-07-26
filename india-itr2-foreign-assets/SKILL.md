---
name: india-itr2-foreign-assets
description: End-to-end reconciliation and filing assistance for Indian ITR-2 returns involving Form 16, AIS/TIS, foreign brokerage or custodial accounts, RSUs, ESPP shares, foreign dividends, interest, withholding tax, Schedule OS, CG, FSI, TR, FA, AL, and Form 67. Use when Codex must analyze salary or broker PDFs/CSVs/JSON, reconcile foreign holdings and lots, convert USD income or assets to INR, prepare Schedule FA A1/A2/A3 records, fix Income Tax portal CSV-import errors, or guide a resident individual through foreign-income and foreign-asset filing.
---

# India ITR-2 Foreign Assets

Reconcile source documents into an auditable ITR-2 filing package. Treat the work as high-stakes financial assistance: verify current official rules, expose assumptions, preserve source evidence, and never fabricate unavailable account or lot data.

## Core workflow

1. Establish scope:
   - Confirm assessment year, financial year, calendar year used by Schedule FA, residential status, regime, filing status, and ITR form.
   - Confirm whether the taxpayer is resident and ordinarily resident before treating Schedule FA as applicable.
   - Do not reuse dates, exchange rates, thresholds, or form rules from another assessment year without current verification.
2. Secure and inventory documents:
   - Accept passwords only for opening the supplied files; do not repeat passwords or embed them in outputs.
   - Inventory Form 16 Part A/B, Annexure, AIS JSON/PDF, TIS, prefill JSON, bank statements, broker quarterly/annual statements, 1042-S or equivalent tax forms, vest notices, trade confirmations, and loan documents.
   - Detect duplicates and misleading filenames by content, period, account, opening/closing balance, and transaction identity.
3. Extract independent ledgers:
   - Salary and perquisite ledger.
   - Domestic interest/dividend/capital-gain ledger.
   - Foreign cash, dividend, interest, tax-withholding, acquisition-lot, sale, and account-balance ledgers.
   - Keep original currency, transaction date, quantity, price/FMV, tax, and source document/page.
4. Reconcile before classifying:
   - Tie quarterly openings to prior closings.
   - Tie lot quantities to closing holdings.
   - Tie dividends and withholding to annual tax forms, allowing for tax-form rounding.
   - Distinguish shares withheld for payroll tax from an actual investor-directed sale.
   - Flag unresolved discrepancies and proxy dates; never silently force totals.
5. Map reconciled facts to ITR schedules.
6. Apply the correct conversion rule for each field.
7. Generate import files or a manual-entry checklist.
8. Validate control totals and explain every figure changed.

Read [references/return-workflow.md](references/return-workflow.md) for the complete document-to-schedule sequence.

## Screen-by-screen portal mode

When the user is actively filing:

1. Identify the exact screen and visible fields.
2. Give only the entries and checks needed on that screen.
3. State the expected subtotal or validation result.
4. Wait for the next screen, screenshot, or exported JSON.
5. Do not jump ahead or repeat completed schedules.

Read [references/portal-step-by-step.md](references/portal-step-by-step.md) before guiding a live portal or offline-utility filing.

## Conditional references

- For RSUs, ESPP, vesting, withholding shares, and lot construction, read [references/equity-compensation.md](references/equity-compensation.md).
- For Schedule OS, FSI, TR, DTAA relief, Rule 115, Rule 128, and Form 67, read [references/foreign-income-ftc.md](references/foreign-income-ftc.md).
- For Schedule FA A1/A2/A3 and Schedule AL, read [references/schedule-fa.md](references/schedule-fa.md).
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
- FA A1/A2/A3 data tables and portal-ready CSVs when requested.
- FSI/TR/Form 67 reconciliation.
- Assumptions and proxies register.
- Control-total report.

Use filenames that distinguish `WORKING`, `PROVISIONAL`, `RECONCILED`, and `PORTAL_READY`. Never tell the user to import a provisional file.

## Portal CSV preparation

Use `scripts/prepare_fa_csv.py` to normalize A2 or A3 CSV data:

```bash
python3 scripts/prepare_fa_csv.py --table A3 --input source.csv --output portal_ready.csv
```

The script enforces the operational importer format documented in [references/portal-csv-import.md](references/portal-csv-import.md). Test a one-row file first when the portal version is new or the template changed.

## Handoff requirements

Lead with the exact schedules and fields that change. For each change, show:

- Previous value, if known.
- Corrected value.
- Component breakup.
- Source documents.
- Conversion rule.
- Whether the number is exact, rounded, or provisional.

Explicitly identify schedules that remain unchanged. Warn about Form 67 when foreign tax credit is claimed. Recommend professional review when facts are ambiguous, documents conflict, residency is uncertain, foreign sales exist, or a substantive legal interpretation is required.

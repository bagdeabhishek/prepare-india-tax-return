# Return workflow

## Contents

1. Intake and scoping
2. Persist filing decisions
3. Document inventory
4. Extraction ledgers
5. Reconciliation
6. Schedule selection
7. Filing sequence
8. Handoff

## 1. Intake and scoping

Start with the staged primary checklist and wait for the user to supply or list
the initial set. Then run the deterministic pipeline and generate conditional
requests. Follow [staged-intake.md](staged-intake.md); do not request the entire
possible document universe at once.

Record:

- Assessment year and previous year.
- Calendar year ending 31 December for Schedule FA.
- ITR form and filing mode.
- Residential status, especially ROR/RNOR/NR.
- Tax regime and any option form.
- Due date, original/revised/belated status, and whether Form 67 has been filed.
- Whether salary includes RSU/ESPP perquisites.
- Whether foreign shares were sold, transferred, withheld, or merely vested.

Do not infer residency from citizenship or employer location.

## 2. Persist filing decisions

Create `filing-decisions.json` using
`assets/filing-decisions.schema.json`. Record the evidence and status for
filing section, regime, residency, FA/AL applicability, foreign-tax credit,
house-completion status, and joint ownership/liability shares.

Read [filing-decisions.md](filing-decisions.md). Reuse confirmed decisions
instead of asking the user the same question at each dependent schedule.

## 3. Document inventory

Initialize the persistent source ledger and create one row per file with:

- Original filename.
- Stable source ID and SHA-256 of the exact file bytes.
- Detected document type.
- Issuer/account.
- Covered dates.
- Password/encryption status without recording the password.
- Pages.
- Key figures.
- Duplicate group.
- Extraction confidence.

Run the preprocessing and selective-invalidation workflow in
[source-ledger.md](source-ledger.md). On follow-ups, inspect `central_store.json`
before opening source documents. Reopen a source only when its hash changed, an
essential field was not extracted, or a conflict requires checking the evidence.

Common documents:

- Form 16 Part A, Part B, Annexure, 12BA.
- AIS JSON and PDF, TIS, prefill JSON.
- Domestic bank interest certificates.
- Capital-gain statements from mutual funds or brokers.
- Foreign quarterly statements, annual statements, vest reports, 1042-S, 1099, trade confirmations.
- Home-loan certificate and property completion/possession evidence.

Misleading filenames are common. Classify by document contents, not filename.

## 4. Extraction ledgers

### Salary ledger

Capture employer, TAN, gross salary components, perquisites, exempt allowances, standard deduction, professional tax, employer NPS under 80CCD(2), taxable salary, and TDS.

### Other-source ledger

Capture payer, income type, gross amount, tax withheld, transaction/credit date, domestic/foreign flag, and applicable conversion.

### Capital-gain ledger

Capture security, domestic/foreign, acquisition and sale dates, quantity, cost, sale proceeds, expenses, STT, corporate actions, and holding-period classification.

### Foreign-account ledger

Capture institution, account number, status, opening date, peak date/value, closing value, cash, securities, credits by nature, and source evidence.

### Foreign-equity lot ledger

Capture issuer, acquisition type, date, gross/net shares, FMV/purchase price, acquisition value, peak value while held, closing value, dividends while held, sale/redemption proceeds, and tax-withheld shares.

## 5. Reconciliation

Use both flow and stock controls:

- Prior closing shares + acquisitions - actual disposals = current closing shares.
- Prior cash + cash credits - withdrawals/fees/tax = current cash.
- Quarterly dividends sum to annual dividend.
- Withholding transactions sum to tax form, allowing documented rounding.
- Employer RSU perquisite should broadly reconcile to vest-date gross shares × FMV × payroll conversion, subject to payroll conventions.
- A2 closing custodial balance should reconcile to securities plus cash.
- A3 closing lots should reconcile to issuer shares and securities value.

Preserve discrepancies. Prefer quarterly detail over a rounded annual tax form for exact transaction values.

## 6. Schedule selection

Typical ITR-2 mapping:

- Salary and perquisites: Schedule Salary.
- House property: Schedule HP.
- Domestic equity/equity-fund sales: Schedule CG and Schedule 112A where applicable.
- Foreign-share sales: Schedule CG; do not assume section 112A.
- Dividend and interest: Schedule OS.
- Current-year loss setoff: CYLA/BFLA.
- Carry-forward losses: CFL.
- Chapter VI-A deductions: VI-A.
- Special-rate income: SI.
- Foreign income: FSI in addition to its head-wise schedule.
- Foreign tax relief: TR and Form 67.
- Foreign assets/accounts: FA.
- Assets and liabilities when applicable: AL, even if also disclosed in FA.

## 7. Filing sequence

Recommended entry order:

1. Part A General and filing status.
2. Salary.
3. House property.
4. Capital gains and 112A.
5. Other Sources and accrual table.
6. CYLA, BFLA, CFL.
7. VI-A and SI.
8. FSI.
9. TR.
10. FA.
11. AL.
12. Tax-paid schedules and self-assessment challan, if applicable.
13. Part B-TI and TTI refresh.
14. Form 67 reconciliation, submission, and verification.
15. Export the official JSON and run `scripts/audit_itr_json.py`.
16. Final official validation and e-verification.

Refresh dependent schedules after upstream edits.

During live filing, give only the current screen's entries and one control total. Use
[portal-step-by-step.md](portal-step-by-step.md) for payment, validation, and submission.

## 8. Handoff

Provide:

- Exact row-by-row changes.
- Expected schedule totals before statutory rounding.
- Files safe to import.
- Fields requiring manual dropdown selection.
- Proxies requiring replacement.
- Documents to retain or attach.
- Filing decisions and their evidence.
- Final JSON audit result and any before/after diff classification.
- Final validation checklist.

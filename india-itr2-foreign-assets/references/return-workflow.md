# Return workflow

## Contents

1. Intake and scoping
2. Document inventory
3. Extraction ledgers
4. Reconciliation
5. Schedule selection
6. Filing sequence
7. Handoff

## 1. Intake and scoping

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

## 2. Document inventory

Create one row per file with:

- Original filename.
- Detected document type.
- Issuer/account.
- Covered dates.
- Password/encryption status without recording the password.
- Pages.
- Key figures.
- Duplicate group.
- Extraction confidence.

Common documents:

- Form 16 Part A, Part B, Annexure, 12BA.
- AIS JSON and PDF, TIS, prefill JSON.
- Domestic bank interest certificates.
- Capital-gain statements from mutual funds or brokers.
- Foreign quarterly statements, annual statements, vest reports, 1042-S, 1099, trade confirmations.
- Home-loan certificate and property completion/possession evidence.

Misleading filenames are common. Classify by document contents, not filename.

## 3. Extraction ledgers

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

## 4. Reconciliation

Use both flow and stock controls:

- Prior closing shares + acquisitions - actual disposals = current closing shares.
- Prior cash + cash credits - withdrawals/fees/tax = current cash.
- Quarterly dividends sum to annual dividend.
- Withholding transactions sum to tax form, allowing documented rounding.
- Employer RSU perquisite should broadly reconcile to vest-date gross shares × FMV × payroll conversion, subject to payroll conventions.
- A2 closing custodial balance should reconcile to securities plus cash.
- A3 closing lots should reconcile to issuer shares and securities value.

Preserve discrepancies. Prefer quarterly detail over a rounded annual tax form for exact transaction values.

## 5. Schedule selection

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

## 6. Filing sequence

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
15. Final validation and e-verification.

Refresh dependent schedules after upstream edits.

During live filing, give only the current screen's entries and one control total. Use
[portal-step-by-step.md](portal-step-by-step.md) for payment, validation, and submission.

## 7. Handoff

Provide:

- Exact row-by-row changes.
- Expected schedule totals before statutory rounding.
- Files safe to import.
- Fields requiring manual dropdown selection.
- Proxies requiring replacement.
- Documents to retain or attach.
- Final validation checklist.

# Filing decisions and schedule selection

## Contents

1. Persist decisions once
2. Filing basis and Seventh Proviso
3. Tax-regime wording
4. Schedule-selection matrix
5. Salary questions
6. House-property questions
7. Final decision controls

## 1. Persist decisions once

Create `filing-decisions.json` in the private workpaper using
`assets/filing-decisions.schema.json`. Record the answer, status, basis, supporting
claim IDs, and verification date. Consult this file before asking a filing
question again.

Do not silently change a confirmed decision. When new evidence changes one,
record the prior answer in the workpaper notes, update dependent schedules, and
mark their checkpoints `needs refresh`.

Minimum decisions:

- AY/PY, ITR form, original/revised/belated return, and filing section.
- Residential status and whether Schedule FA applies.
- Tax regime and the answer to the portal's opt-out question.
- Salary exemptions, perquisites, employer NPS, and Agnipath eligibility.
- Foreign income, foreign assets, FTC, and Form 67.
- Actual share sales versus payroll-withheld shares.
- House completion status, co-ownership share, and loan share.
- Schedule AL applicability.

## 2. Filing basis and Seventh Proviso

Use ordinary section 139(1) when the taxpayer is already required to file, such
as because taxable income exceeds the applicable basic exemption limit. Do not
select Seventh Proviso conditions merely because the return contains those
questions.

The Seventh Proviso block is for a person who is otherwise not required to
furnish a return under section 139(1), but must file because a listed threshold
or prescribed condition applies. Test each condition from evidence:

- More than the current statutory threshold deposited in one or more current
  accounts.
- Foreign-travel expenditure over the current threshold.
- Electricity expenditure over the current threshold.
- Another currently prescribed clause (iv) condition.

If ordinary section 139(1) already applies, mark the Seventh Proviso block
`NOT_APPLICABLE`, not `No evidence reviewed`.

## 3. Tax-regime wording

Parse the question literally:

> Do you wish to exercise the option under section 115BAC to opt out of the new
> tax regime?

- `No` means remain in the new/default regime.
- `Yes` means opt out and use the old regime, subject to current eligibility and
  timing rules.

For AY 2026-27, the official ITR-2 manual states that the new regime is the
default and the portal auto-selects `No`. Reverify this for later AYs.

Never infer regime from deductions alone. Record the selected regime first,
then enable only deductions the current form permits.

## 4. Schedule-selection matrix

Select a schedule only when facts support it:

| Facts | Schedule/action |
| --- | --- |
| Salary or pension | Salary and TDS1 |
| House owned/let/self-occupied | HP |
| Actual capital-asset transfer | CG; 112A only when its conditions apply |
| Dividend or interest | OS |
| Current or brought-forward losses | CYLA/BFLA/CFL |
| Chapter VI-A claim permitted by regime | VI-A |
| Special-rate income | SI |
| Foreign-source income for a resident | FSI plus the normal head schedule |
| Foreign tax credit | TR plus separately filed Form 67 |
| Applicable foreign asset/account disclosure | FA |
| Total income above the current AL threshold | AL |
| Advance/self-assessment tax | Schedule IT / Tax Paid |

Refresh CYLA, BFLA, CFL, SI, Part B-TI, and Part B-TTI after an upstream
salary/HP/CG/OS/VI-A change.

## 5. Salary questions

Use Form 16 Part B and Form 12BA:

- `Salary` is salary excluding separately reported perquisites and profit in
  lieu.
- Put equity compensation already taxed by the employer in `Value of
  perquisites`; do not add it a second time.
- Use `Profit in lieu of salary` only when section 17(3) income is actually
  reported. Zero is valid when the supporting salary documents report none.
- Classify a non-enumerated perquisite under the portal's supported `Other
  benefits` row and preserve a description such as the plan/security and source
  statement. The value must reconcile to Form 12BA/Form 16.
- Schedule TDS1 `Income chargeable under Salaries` is the Form 16 income
  chargeable figure, not gross salary.

Answer allowance questions from the exemption rows in Form 16:

- Rule 2BB(1)(a)-(c) official-duty allowances: `Yes` only when actually received
  and eligible.
- Disabled transport allowance: `Yes` only when the statutory disability facts
  and allowance are present.
- Other salary exemption: `Yes` only for a supported exemption.

Under the new regime, Schedule VI-A commonly leaves only employer NPS under
section 80CCD(2) and eligible Agnipath contribution under section 80CCH enabled.
Claim neither merely because the portal asks; reconcile 80CCD(2) to Form 16 and
80CCH to actual eligibility/contribution.

## 6. House-property questions

Separate three issues:

1. Current Schedule HP income/loss.
2. Pre-construction interest tracking.
3. Schedule AL asset cost/liability.

Do not claim construction-period interest as current self-occupied interest
while construction remains incomplete. Preserve lender certificates and a
year-wise pre-construction ledger for the treatment available after completion.
This does not prevent reporting the supported construction cost and related
loan liability in Schedule AL when AL applies.

For joint property/loan, record legal ownership and liability shares from the
agreement and loan documents. Do not default to 50% merely because two names
appear; use 50% only when equal ownership/liability is supportable.

## 7. Final decision controls

Before submission:

- Every portal answer is `CONFIRMED`, `NOT_APPLICABLE`, or visibly unresolved.
- Regime answer and enabled deductions agree.
- Filing section and Seventh Proviso answers agree.
- Residency, FSI/TR/FA, and foreign-assets question agree.
- Completion status agrees with Schedule HP interest treatment.
- Ownership shares agree across HP, FA/AL, and liabilities.
- Schedule AL applicability uses the current AY threshold.

For AY 2026-27, verify these decisions against the official
[ITR-2 user manual](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/file-itr-2-online/itr-2-UM)
and the current portal/utility version.

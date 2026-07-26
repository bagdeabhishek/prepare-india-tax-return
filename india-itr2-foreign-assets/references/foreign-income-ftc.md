# Foreign income and foreign tax credit

## Contents

1. Separate disclosure from taxation
2. Schedule OS
3. Accrual/receipt table
4. Schedule FSI
5. Schedule TR
6. Form 67
7. Conversion controls

## 1. Separate disclosure from taxation

Schedule FA discloses calendar-year foreign assets and specified credits. Schedule OS and FSI report taxable income for the Indian previous year. Never force the values to match when dates or conversion rules differ.

Report foreign income twice in the return structure, not twice in taxable income:

- Once under the relevant head, such as Schedule OS or CG.
- Again as informational foreign-source detail in FSI.

## 2. Schedule OS

Typical classifications:

- Ordinary foreign dividends: dividend income other than deemed-dividend categories.
- Foreign deposit/broker interest: the appropriate interest sub-row; use “others” where it is not savings-bank or bank-deposit interest as defined by the form.
- Do not net foreign withholding tax from gross income.

Create a payer-level workpaper:

`gross foreign currency × applicable Rule 115 rate = taxable INR`

Round only at the field level required by the utility. Preserve unrounded totals.

## 3. Accrual/receipt table

When quarterly computation under section 234C is relevant, allocate dividend income into the exact portal date buckets using credit/payment dates. Confirm that the bucket total equals Schedule OS dividend income.

Do not place regular interest into a dividend-only row.

## 4. Schedule FSI

For each country and income head capture:

- Country code and taxpayer identification number.
- Foreign income included in Part B-TI.
- Foreign tax paid/deducted.
- Indian tax payable on that income.
- Relief, capped at the lower applicable amount.
- Section 90, 90A, or 91 as applicable.

If several sources share a country and income head, aggregate only when the form permits and the workpaper retains source-level detail. Where the utility requires separate rows, split dividends, interest, and capital gains.

Compute Indian tax attributable using the current applicable method, including surcharge and cess where required. Do not blindly multiply by a marginal rate if the return has special-rate income or other complicating factors.

## 5. Schedule TR

TR is the country-level summary of FSI:

- Total foreign tax must equal country total column (c) of FSI.
- Total relief must equal country total column (e) of FSI.
- Select the correct relief section.
- Supply the relevant DTAA article when required.

For US dividends, review Article 10. For interest, review Article 11. Use the article actually relevant to the taxed income.

## 6. Form 67

When claiming foreign tax credit:

- Verify the current filing deadline and official instructions.
- File and verify Form 67 before final ITR validation when possible; the portal may block validation until it exists.
- File Form 67 through the portal.
- Reconcile Form 67 income, foreign tax, country, section, and relief to FSI/TR.
- Retain or attach the broker tax form, withholding statement, proof of deduction/payment, and income statement as required.
- Do not claim rounded annual-form tax when detailed statements establish a different exact amount without documenting why.
- Use source-level taxed income in Form 67. Do not force zero-tax foreign interest into a dividend row merely to match consolidated FSI.
- Preserve the Form 67 acknowledgement and verification status.

If the ITR was e-verified before Form 67, check the current Rule 128 deadline. Do not revise solely to reverse the order when Form 67 was validly filed within the permitted deadline and matches the claimed credit.

## 7. Conversion controls

Maintain separate conversion columns for:

- Rule 115 taxable income.
- Rule 128 foreign tax.
- Schedule FA acquisition/peak/closing/income/proceeds.

For each conversion record source URL/file, date, SBI rate type, and arithmetic. Confirm:

- OS foreign income = FSI foreign income by head, subject only to documented form mechanics.
- Foreign tax workpaper = FSI tax = TR tax = Form 67 tax.
- Relief in TR/TTI does not exceed the permitted cap.

# Schedule FA portal CSV imports

## Contents

1. General rule
2. Verified A3 workaround
3. A3 field map
4. A2 handling
5. Debugging
6. Safety

## 1. General rule

Always download a fresh template from the exact schedule and portal version. Preserve a copy. Compare the template header with the generated output, but do not assume the template’s trailing delimiter reflects the importer’s actual parser.

Portal messages such as “some rows did not follow the template and were skipped” are generic. Isolate failures with a one-row file.

## 2. Verified A3 workaround

The AY 2026-27 portal accepted the following operational format when its downloaded A3 template caused skipped rows:

- Exactly 12 fields, not 13.
- Delete the template’s stray trailing comma/blank field.
- No trailing comma on any line.
- No empty rows at the bottom.
- No CSV quoting.
- Column 1, misleadingly labelled `Country/Region name`, contains serial numbers `1,2,3...`.
- Column 2 contains the numeric country code; USA is `2` in that portal list.
- For listed A3 holdings, column 3 uses `Company Name (TICKER)`, with one space before the opening parenthesis and no commas. Do not invent a ticker for an unlisted entity.
- Remove commas from entity names and addresses.
- Use plain ASCII.
- Use `Company`, not `COMPANY` or `LISTED COMPANY`.
- Use ISO dates `YYYY-MM-DD` with leading zeros.
- Use whole INR numbers without commas, currency symbols, or decimals unless the portal explicitly accepts otherwise.
- Keep ZIP code at no more than 8 characters.

This is an operational workaround for importer behavior, not a substantive tax rule. Retest when the portal version changes.

## 3. A3 field map

Working order:

1. Serial number: although the downloaded header says `Country/Region name`,
   enter `1`, `2`, `3`, and so on.
2. Country code only: do not enter the country name. For the portal's AY 2026-27
   list, USA was `2`.
3. Listed entity name without commas, followed by ticker in parentheses:
   `NVIDIA CORPORATION (NVDA)`. For an unlisted entity, enter only its supported
   legal name.
4. Address without commas.
5. ZIP code with a maximum of 8 characters.
6. Nature of entity: use the exact dropdown label `Company`.
7. Acquisition date as literal `YYYY-MM-DD` text with leading zeros. For
   example, 5 September 2024 is `2024-09-05`. Merely formatting a spreadsheet
   cell to look this way is insufficient if its stored/exported CSV value is
   different.
8. Initial investment value INR.
9. Peak investment value INR.
10. Closing value INR.
11. Gross amount paid/credited INR.
12. Gross sale/redemption proceeds INR.

Generate the CSV directly with `prepare_fa_csv.py` where possible. Inspect the
raw CSV date text after generation and avoid reopening/resaving the
`PORTAL_READY` artifact in spreadsheet software that may change the stored date.

## 4. A2 handling

Manual entry can be more reliable because status and credit-nature dropdowns may reject undocumented CSV values.

Confirmed visible labels in the AY 2026-27 UI included:

- Status: `Owner`.
- Nature: `Other income`.
- Nature: `Dividend`.

When generating an A2 CSV, use the same 12-field/no-trailing-delimiter strategy only after a one-row test. Normalize account numbers to plain alphanumeric characters if punctuation causes rejection. Retain the downloaded template and record which values the current dropdown displays.

## 5. Debugging

1. Clear partially imported rows to avoid duplicates.
2. Create a single valid A3 row.
3. Remove all quotes, commas inside text, currency symbols, thousands separators, non-ASCII characters, and final blank columns.
4. Confirm exactly 12 fields with a CSV parser.
5. Confirm date is literal ISO text.
6. Confirm nature label matches the UI.
7. Upload the one-row file.
8. If accepted, upload the combined file after removing the test row or clearing the schedule.
9. If rejected, enter the same row manually and compare every displayed value.

## 6. Safety

Do not weaken substantive data merely to satisfy the importer. If the portal cannot import a correct record, enter it manually. After import, open several rows and verify that dates, amounts, country, and nature were not silently altered.

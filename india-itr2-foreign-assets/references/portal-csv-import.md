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
- Remove commas from entity names and addresses.
- Use plain ASCII.
- Use `Company`, not `COMPANY` or `LISTED COMPANY`.
- Use ISO dates `YYYY-MM-DD` with leading zeros.
- Use whole INR numbers without commas, currency symbols, or decimals unless the portal explicitly accepts otherwise.
- Keep ZIP code at no more than the portal-supported length.

This is an operational workaround for importer behavior, not a substantive tax rule. Retest when the portal version changes.

## 3. A3 field map

Working order:

1. Serial number.
2. Country code.
3. Entity name without commas.
4. Address without commas.
5. ZIP.
6. Nature of entity, such as `Company`.
7. Acquisition date `YYYY-MM-DD`.
8. Initial investment value INR.
9. Peak investment value INR.
10. Closing value INR.
11. Gross amount paid/credited INR.
12. Gross sale/redemption proceeds INR.

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

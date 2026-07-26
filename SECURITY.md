# Security and Privacy

## Supported versions

Security and privacy fixes apply to the latest version on the default branch.

## Reporting a security issue

Do not open a public issue containing taxpayer information, credentials, financial records, or an unredacted document.

Use GitHub private vulnerability reporting if it is available for this repository. Otherwise, send the maintainer a minimal, non-sensitive notice through their GitHub profile and wait for a private channel before sharing details.

## Sensitive-data handling

This repository must never contain:

- Real PAN, Aadhaar, passport, TIN, bank, broker, demat, or loan identifiers
- Passwords, tokens, OTPs, API keys, cookies, or authentication files
- Taxpayer addresses, contact details, statements, returns, or acknowledgements
- Unredacted screenshots or generated artifacts derived from real filings

Rotate or revoke any credential accidentally exposed. If personal tax data is committed, treat repository-history removal as urgent; deleting the current file alone is insufficient.

## Local use

- Keep taxpayer source documents outside the repository.
- Use passwords only in memory for opening supplied files.
- Do not embed passwords or taxpayer identifiers in scripts, output filenames, logs, or examples.
- Review generated CSV and JSON files before sharing them.
- Prefer synthetic fixtures for testing.

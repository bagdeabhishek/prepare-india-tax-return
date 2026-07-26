# India ITR-2 Foreign Assets Skill

A Codex skill for reconciling and filing Indian ITR-2 returns involving salary, RSUs, ESPP shares, foreign brokerage accounts, dividends, foreign tax credit, Schedule FA, Schedule AL, and Form 67.

The skill supports both document-led reconciliation and live, screen-by-screen filing assistance in the Income Tax Department portal or offline utility.

> [!IMPORTANT]
> This project provides educational filing assistance, not legal, tax, or investment advice. Tax rules, schemas, portal behavior, deadlines, exchange-rate requirements, and treaty interpretations can change. Verify current official guidance and consult a qualified tax professional when facts are uncertain or material.

## What it covers

- Form 16, AIS, TIS, and prefill reconciliation
- Salary and equity-compensation perquisites
- Domestic and foreign dividends and interest
- Capital gains and the distinction between actual sales and tax-withheld shares
- Schedule OS, CG, FSI, TR, FA, AL, SI, and tax-paid schedules
- Rule 115 and Rule 128 conversion controls
- Foreign custodial accounts and foreign equity lots
- Schedule FA A1/A2/A3 CSV preparation
- Self-assessment tax, Schedule IT, and challan verification
- Form 67 preparation, evidence, validation, and acknowledgement checks
- Final ITR JSON reconciliation without unsafe direct editing
- Incremental per-file preprocessing with SHA-256 provenance
- A persistent central JSON ledger for fast follow-up questions
- Selective invalidation when a source file changes
- Generic PDF, JSON, CSV, spreadsheet, text, DOCX, image, and ZIP preprocessing
- One-screen-at-a-time portal guidance

## Privacy first

Indian tax documents contain highly sensitive information. Never commit or post:

- PAN, Aadhaar, passport, or taxpayer-identification numbers
- Bank, broker, loan, or demat account numbers
- Passwords, OTPs, tokens, or credentials
- Addresses, phone numbers, or personal email addresses
- Form 16, AIS/TIS, ITR JSON, acknowledgements, statements, or tax certificates
- Real taxpayer screenshots unless fully redacted

Use synthetic or thoroughly redacted examples in issues and pull requests. The skill instructs Codex to use document passwords only for opening supplied files and never persist them in outputs.

## Installation

Clone the repository:

```bash
git clone https://github.com/bagdeabhishek/india-itr2-foreign-assets-skill.git
```

Copy the skill folder into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
cp -R india-itr2-foreign-assets-skill/india-itr2-foreign-assets ~/.codex/skills/
```

Restart or refresh Codex so the skill is discovered.

You can also ask Codex to install the skill from the repository path:

```text
Install the india-itr2-foreign-assets skill from
https://github.com/bagdeabhishek/india-itr2-foreign-assets-skill/tree/main/india-itr2-foreign-assets
```

## Usage

Invoke the skill explicitly:

```text
Use $india-itr2-foreign-assets to reconcile my Form 16, AIS, broker
statements, foreign income, and Schedule FA for ITR-2.
```

For live filing:

```text
Use $india-itr2-foreign-assets and guide me one portal screen at a time.
I am currently at Schedule Other Sources.
```

For foreign-asset CSV work:

```text
Use $india-itr2-foreign-assets to prepare portal-ready Schedule FA A2
and A3 CSV files from my redacted broker statements.
```

## How the workflow behaves

The skill:

1. Establishes the assessment year, residency, regime, form, and filing basis.
2. Inventories and reconciles source documents before classifying income.
3. Hashes every source and preprocesses only new or changed file versions.
4. Uses isolated per-file worker outputs and one deterministic central-store merge.
5. Builds separate salary, income, foreign-tax, cash, account, and equity-lot ledgers.
6. Applies schedule-specific dates and conversion rules.
7. Maps reconciled facts into the ITR-2 schedules.
8. Guides live filing one screen at a time with a control total at each checkpoint.
9. Reconciles Form 67, self-assessment tax, Schedule IT, and the final utility export.
10. Preserves unresolved items instead of inventing values.

The detailed live-filing sequence is in
[`portal-step-by-step.md`](india-itr2-foreign-assets/references/portal-step-by-step.md).

## Incremental source preprocessing

For a document-heavy return, initialize a private workpaper:

```bash
python3 india-itr2-foreign-assets/scripts/source_store.py init \
  --workspace /private/path/itr-workpaper

python3 india-itr2-foreign-assets/scripts/source_store.py scan \
  --workspace /private/path/itr-workpaper \
  --source-dir /private/path/source-documents \
  --replace-inventory \
  --extractor-version parser-1.0.0_claims-1

python3 india-itr2-foreign-assets/scripts/preprocess_sources.py \
  --workspace /private/path/itr-workpaper \
  --jobs 4
```

The generic preprocessor normalizes PDF pages, spreadsheet cells, CSV rows, JSON
paths, archive members, text and other supported structures. The generated work
queue then contains one isolated semantic-classification job per new or changed
file. Workers write per-source records; a single coordinator performs the atomic
merge:

```bash
python3 india-itr2-foreign-assets/scripts/source_store.py merge \
  --workspace /private/path/itr-workpaper
```

Every extracted claim records the exact file hash and page, row, cell, or JSON
path that supports it. Reconciled facts depend on claim IDs, so changing one
source makes only dependent facts stale. Follow-up questions use the central
store instead of rereading every source.

The private workspace is initialized with a deny-all `.gitignore`. Never create
it inside this public repository. See
[`source-ledger.md`](india-itr2-foreign-assets/references/source-ledger.md).

## Schedule FA CSV utility

Normalize an A2 or A3 CSV using the bundled script:

```bash
python3 india-itr2-foreign-assets/scripts/prepare_fa_csv.py \
  --table A3 \
  --input source.csv \
  --output portal_ready.csv
```

Always download a fresh template from the current portal version and test a single redacted row before importing a full file.

## Repository layout

```text
.
├── README.md
├── LICENSE
├── SECURITY.md
├── CONTRIBUTING.md
└── india-itr2-foreign-assets/
    ├── SKILL.md
    ├── agents/openai.yaml
    ├── assets/
    ├── references/
    └── scripts/
```

## Scope and limitations

- Designed for individuals using ITR-2, not business or professional income returns.
- Schedule FA usually requires resident-and-ordinarily-resident analysis; residency must be established from facts.
- Foreign-share sales, disputed foreign tax, complex treaty positions, uncertain ownership, or conflicting documents merit professional review.
- AY-specific portal codes and payment routes included in the skill are examples that must be reverified for later years.
- The project is not affiliated with the Income Tax Department, CBDT, OpenAI, GitHub, any broker, bank, employer, or tax-preparation provider.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or pull request, especially the rules against posting taxpayer data.

## License

Released under the [MIT License](LICENSE).

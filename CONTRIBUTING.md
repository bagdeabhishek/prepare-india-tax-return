# Contributing

Thank you for helping improve the Prepare India Tax Return skill.

## Protect taxpayer data

Do not include real taxpayer information in an issue, discussion, commit, test fixture, screenshot, or pull request. This includes:

- Tax identifiers and identity documents
- Account numbers and financial statements
- Addresses and contact details
- Passwords, tokens, OTPs, or document-opening credentials
- ITR JSON, Form 16, AIS/TIS, acknowledgements, or challans

Use synthetic data or irreversible redaction. If a bug can only be reproduced with sensitive material, describe the behavior without attaching the source document.

## Before proposing a change

1. Check current official Income Tax Department forms, rules, validation guidance, and portal behavior.
2. Identify the assessment year to which the change applies.
3. Separate substantive tax treatment from an operational portal workaround.
4. Preserve unresolved ambiguity instead of inventing an account value, date, lot, or exchange rate.

## Skill changes

- Keep `SKILL.md` focused and concise.
- Put detailed workflows in `references/`.
- Keep references one level below `SKILL.md`.
- Use imperative instructions.
- Update `agents/openai.yaml` if the skill scope changes.
- Do not add public-facing repository documentation inside the skill folder.

Validate the skill:

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  prepare-india-tax-return
```

Test the CSV normalizer when modifying it:

```bash
python3 prepare-india-tax-return/scripts/prepare_fa_csv.py --help
```

## Pull requests

Describe:

- What changed
- Why it changed
- Applicable assessment year or portal version
- Official sources used
- Validation performed
- Any unresolved limitation

By contributing, you agree that your contribution is licensed under the repository's MIT License.

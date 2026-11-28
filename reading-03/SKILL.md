---
name: aligned-scientific-translation
description: Translate supplied scientific literature as aligned source and target passages, with terminology locks and verification of numbers, formulas, citations, and scope. Use for scientific paper translation and bilingual passage alignment.
---

# Aligned scientific translation

## Read the case and map the text

Read `/input/case.json` and the supplied `task.md` before opening the actual source files. Identify the target language, requested span, terminology requirements, and the original `output_contract`. Work in `/app/work`. Write `/app/output/result.json` with the actual `case_id` and every contract field. Put requested bilingual or editable artifacts beside it, with real previews where required.

Create a source passage list in reading order, using original JATS paragraph IDs or PDF page and block references. Include in-scope headings, captions, table headers and formula labels. Inspect the page image wherever the extracted text shows a broken line, a missing character or a cross-column join. Treat unreadable scans and unavailable figures as gaps. If there is no real page number, keep the native locator instead. Preserve the source verbatim in the bilingual output when the case requests it.

## Translate with an explicit terminology ledger

1. Before translating, resolve abbreviations and record the source form, chosen translation, and spelling variations. Share this ledger across passages. Keep terms distinct when context changes their meaning and document the reason for any case-specific override.
2. Work in section-sized batches. Translate each passage under its original ID. Preserve units, quantities, signs, formulas, symbols, figure numbers and citations. Where the output allows, retain scientific notation literally and standardize whitespace only. Record split or joined source layout at the passage boundary.
3. For important statements, read back source and translation side by side. Verify who did what, comparisons, scope, negation, uncertainty, and cause versus association. In a separate review pass, check that captions and source conditions survive. If context is unavailable, mark the affected passage and the reason for manual review.

## Check alignment and protected tokens

Python 3.9+ standard library. Create a work file with `segments` (ordered objects with `id`, `source`, and optional `protected` list of exact symbol strings), `translations` (ordered objects with `id` and `target`), and optional `glossary` (objects with `source` and `target`). Copy exact reference, equation or unit labels needing protection to `protected`. The checker verifies ordered coverage, numeric literals and counts, protected strings, and glossary target occurrences per passage. Use distinct literal source forms only. It flags valid paraphrasing or locale-specific number preservation for review, and cannot evaluate semantic fidelity. Correct the translation or document an adjudicated exception in the case's review fields. Keep the work file separate from the required output schema.

```sh
python3 scripts/check_translation.py /app/work/alignment.json
```

An unavailable check is a gap, never a pass. Use `python` on Windows if that is the installed command.

### Illustrative example

Input passage `P4` reads “At 25 °C, the concentration did not exceed 2 mM [3].” A target field can read “在 25 °C 下，浓度未超过 2 mM [3]。” Use protected strings `°C`, `mM` and `[3]`, and keep the same passage ID so the range, negation and reference can be reviewed.

When checking thresholds, keep the operator attached to its value. The checker flags a reversed or dropped symbolic inequality and accepts equivalent ASCII and Unicode forms. Review a comparator translated into words in context.

Review each flagged measurement in its own aligned passage. The checker pairs common printed units with their numerical values, so swapping mg and mL between two values produces a review item. Unicode micro signs µ and μ are equivalent. For a translated unit name or valid unit conversion, verify the full dimension and record the equivalence in the review.

---
name: evidence-linked-paper-notes
description: Produce section-aligned notes or a structured paper card from supplied research papers, with verifiable source passages for findings, numbers, conditions, and limitations. Use for paper summarization, literature reading notes, or evidence-linked literature review preparation.
---

# Evidence-linked paper notes

## Read the case contract

In Harbor, read `/input/case.json` and the supplied `task.md` first. Inspect the actual materials, `case_id`, requested scope, and `output_contract`. The case contract defines the final JSON keys, value types, and any requested artifacts. Use `/app/work` for intermediate files and save the completed `result.json` and requested deliverables under `/app/output`. In a standalone run, use the supplied paper and requested output path. The fallback fields below apply when the caller supplies no schema.

## Map the paper before summarizing

1. Identify the paper, versions, source files, and requested coverage. Preserve each source's identity. Different formats of one paper are alternate representations of that source.
2. Prefer publisher paragraph IDs, actual PDF pages, or labeled tables and figures. For JATS XML, Markdown, plain text, or a searchable PDF, run the indexer from this skill directory with Python 3.9+. PDF indexing uses `pdftotext` when available. Use the directory and command names available in the execution environment.

   ```sh
   python3 scripts/evidence.py index /input/paper.xml --source-id paper --out /app/work/paper.index.json
   ```

3. Scan the index for section order and any extraction warnings. Keep the paper's actual headings and order. Open the source at any ambiguous column break, formula, caption, unit, or table cell. For scanned pages, use the available PDF renderer or OCR and verify key passages against the rendered page. For structured JSON materials, use their original paragraph IDs or field paths and verify against their text directly. Remember which pages or artifacts were unreadable.

## Build the notes

Fill the fields requested by the case. For a standalone paper card use `research_question`, `data`, `method`, `findings`, `conclusion`, `limitations`, and `sections` in document order. Retain the source title and identifier. Keep details that change interpretation, including material or population, comparator, measured quantity, unit, conditions, time point, and uncertainty. Distinguish a measured result, an author interpretation, and the reader's inference. Attribute prior work to its cited source.

Write one checkable proposition per note. Give each substantive proposition a source identifier, a precise locator, and a short exact quote. A locator can be a JATS paragraph ID, a marked section and paragraph, physical PDF page and block, or a figure label or table cell. Use the smallest excerpt that supports the proposition and its conditions. If support spans two passages, cite both and explain which supports each part. When material is missing, conflicting, or unreadable, use the case's status and uncertainty fields to explain the gap and any manual check. Use `not_reported` only when the supplied material was sufficiently readable to check the requested fact.

## Verify before writing the final result

For notes based on the index, record each checked claim in a temporary JSON list with `id`, `claim`, and `evidence`. Each evidence item contains `source_id`, `anchor_id` from the index, and an exact `quote` within that anchor. Pass multiple indexes when a claim uses multiple files.

```sh
python3 scripts/evidence.py check /app/work/evidence.json /app/work/paper.index.json
```

Resolve missing anchors, inaccurate quotes, and unsupported numeric tokens. Then reread each key citation for units, comparator, scope, negation, and whether it actually supports the claim. Review manual anchors against their original artifact. The script verifies text and numeric tokens. Scientific interpretation, unit equivalence, and table alignment require inspecting the source. Check the final file against the case contract, including `case_id`, evidence, and partial or incomplete status where applicable.

## Minimal example — illustrative input and output

Given an illustrative `paper.md` with a `Results` heading and a paragraph reading `At 25 °C, the test recorded a 12% decrease after 5 min.`, run `python3 scripts/evidence.py index paper.md --source-id paper --out paper.index.json`. A finding may read `A 12% decrease was recorded after 5 min at 25 °C.` with the index locator for that paragraph and the original sentence as evidence. The example demonstrates the interface using invented input. Use the actual paper wherever the skill is run.

Verify the full printed value: a quote beginning “5 mg” does not establish that value inside “15 mg” or “0.5 mg”. Include the sign, decimal and unit in the supporting passage.

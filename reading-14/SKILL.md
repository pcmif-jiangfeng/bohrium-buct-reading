---
name: atomic-paper-assertions
description: Extract independently verifiable scientific assertions, bind them to exact source passages, and export them as machine-readable nanopublication records. Use for assertion decomposition, evidence anchoring, and provenance review of supplied papers.
---

# Atomic paper assertions

Read `/input/case.json`, `task.md`, and the actual supplied papers. Determine the required `case_id`, `output_contract`, expected serialization, and requested scope. Save intermediate ledgers under `/app/work` and contract-shaped `result.json` plus required artifacts under `/app/output`.

1. Create a source record per work. Capture actual title, authors, year, version, and DOI or stable supplied identifier, then build a passage index using original paragraph IDs, actual PDF pages with blocks, or explicit table/caption labels. Record when an input only has OCR text or when a table provides headers, units, or footnotes separately. Different representations of the same work share attribution.
2. Split each passage into claims that can be judged independently. Record one subject, directed predicate, and object/value, with measurement units, comparator, population/material, method or time as needed. Attach negation and qualification to the particular assertion they govern. Distinguish results measured in the paper from background cited studies, author interpretations and your inferences. Preserve discrepant findings, source conditions and version differences.
3. Bind the smallest passage that supports the claim and its conditions. Use additional quotes for a table header, baseline, or method. Mark the role of each evidence item and state why the evidence is direct, indirect, conflicting or insufficient. Preserve the scope of the author’s statement. Remove claims that have no available support from the set of established results and record the reason.
4. Check and export. Use the ledger checker below for duplicate claims, unique IDs, declared sources and exact quotation alignment. Read each approved claim with its citations again to inspect subject/object direction, qualifiers, units and reference scope. Use the case-requested format. A JSON claim ledger can carry assertion, provenance and publication metadata distinctly. For requested RDF/TriG, use distinct named head, assertion, provenance and publication-info graphs as in the [Nanopublication Guidelines](https://nanopub.net/docs/guidelines/). Attribution of the scientific claim belongs in provenance, and creation metadata about the extracted record belongs in publication info. Keep local IDs local. Include a version or supersession link only when known.

## Local work ledger and check

Python 3.9+ standard library. The checker accepts a JSON object with `sources` (objects containing `id`, `title` and `passages`, a locator-to-source-text mapping) and `assertions` (objects containing `id`, `subject`, `predicate`, `object`, optional string `scope`, and `evidence`). Each evidence entry contains `source_id`, `locator`, and a short literal `quote`. Maintain the case’s richer fields and actual bibliography in the final result. The checker detects string and structural errors. Adjudication of scientific meaning and qualification stays in the source review.

```sh
python3 scripts/check_assertions.py /app/work/assertions.json
```

Use `python` where that is the installed command. If the material is unavailable, document the affected claims and return the contract’s partial or undetermined status.

### Illustrative example

For source `paper-a`, locator `P9`, and the line “At 20 °C, membrane B retained 95% after 30 cycles,” record `membrane B → retained → 95%` with scope `20 °C; after 30 cycles` and cite the quoted line. A separate mechanism sentence from the discussion is a separately attributed interpretation.

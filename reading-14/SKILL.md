---
name: atomic-paper-assertions
description: Extract independently verifiable scientific assertions, bind them to exact source passages, and export them as machine-readable nanopublication records. Use for assertion decomposition, evidence anchoring, and provenance review of supplied papers.
---

# Atomic paper assertions

Read `/input/case.json`, `task.md`, and the actual supplied papers. Determine the required `case_id`, `output_contract`, expected serialization, and requested scope. Save intermediate ledgers under `/app/work` and contract-shaped `result.json` plus required artifacts under `/app/output`.

1. Create a source record per work. Capture actual title, authors, year, version, and DOI or stable supplied identifier. Index evidence against the original JATS paragraph IDs, original UTF-8 text lines, or physical PDF pages and visual blocks. For a PDF, retain a page-indexed text extraction generated directly from the input and verify ambiguous snippets, symbols and table headers on the rendered page. Distinguish the original PDF location from the derived text line used in the automatic check. Different representations of the same work share attribution.
2. Split each passage into claims that can be judged independently. Record one subject, directed predicate, and object/value, with measurement units, comparator, population/material, method or time as needed. Attach negation and qualification to the particular assertion they govern. Classify measured results, cited studies, author interpretations and your own inferences distinctly. Preserve discrepant findings, source conditions and version differences.
3. Bind the shortest passage that supports the claim and its conditions. Attach extra locators when the evidence depends on a table header, baseline, or method. Record each item's role and why it is direct, indirect, conflicting or insufficient. Assign a reason for each unresolved claim and leave it out of established results. A quotation can be present while the claim is still unsupported, for example if the text reports a different timepoint or attributes the result to a cited study.
4. Check and export. Use the ledger checker below for duplicate claims, unique IDs, declared sources and exact quotation alignment. Read each approved claim with its citations again to inspect subject/object direction, qualifiers, units and reference scope. Use the case-requested format. A JSON claim ledger can carry assertion, provenance and publication metadata distinctly. For requested RDF/TriG, use distinct named head, assertion, provenance and publication-info graphs as in the [Nanopublication Guidelines](https://nanopub.net/docs/guidelines/). Attribution of the scientific claim belongs in provenance, and creation metadata about the extracted record belongs in publication info. Keep local IDs local. Include a version or supersession link only when known.

## Local work ledger and check

Python 3.9+ standard library. Create a JSON object with `sources` and `assertions`. Each source supplies `id`, `title`, `path` relative to the selected source directory, and a `passages` map. Use `{"jats_id":"Par21"}` for a unique paragraph, table cell or caption ID and `{"lines":[12,14]}` for one-based inclusive lines in a UTF-8 source. Each assertion supplies `id`, `subject`, `predicate`, `object`, optional string `scope`, and `evidence` entries with `source_id`, `locator`, and a short literal `quote`. The `locator` is a key in that source's `passages` map. Keep the case's richer provenance and bibliography in the final result.

```sh
python3 /skills/weekly-skill/scripts/check_assertions.py /app/work/assertions.json --source-root /input
```

For structured JSON materials, locate the text field in the actual supplied file and use an anchor such as `{"json_pointer":"/paragraphs/0/text"}`. The checker resolves a single string in the source, including in compact one-line JSON. Keep the original paragraph ID alongside the pointer for human review. Check the paragraph identity and claim scope before approval.

For tables with an identified JATS table-wrap but no cell IDs, use a selector such as `{"table_id":"T1","cell":[2,3]}`. Both coordinates start at one. Count XML rows including header rows, then the actual th/td children in that row. For spans, positions count stored cells; verify visual column membership separately. Cite the value, its header and any qualifying footnote using separate anchors.

Use the root containing the actual input files. For a PDF text extraction, use the directory containing that generated file and cite the physical PDF page in the final evidence. `source_files` records the relative path and SHA-256 of each material read. Fix `invalid_source_anchor`, `unresolved_locator`, and `quote_mismatch` entries against the source. If a source remains unavailable, preserve other verified claims and report the affected records as partial or undetermined. Running without `--source-root` accepts older ledgers with copied source strings and provides a preliminary consistency check. Before delivery, reopen `result.json` and each requested export, check all `output_contract` keys, and verify that every assertion refers to the intended source and qualifier.

### Illustrative example

For source `paper-a`, locator `P9`, and the line “At 20 °C, membrane B retained 95% after 30 cycles,” record `membrane B → retained → 95%` with scope `20 °C; after 30 cycles` and cite the quoted line. A separate mechanism sentence from the discussion is a separately attributed interpretation.

If a table result is qualified by a linked JATS footnote, cite the value and the footnote as separate evidence entries. A jats_id selector can resolve an original fn ID and its paragraph text. Follow the actual callout to establish that the qualification belongs to that row.
